from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from accounting_agents.state import AccountingAgentsState
from accounting_agents.nodes.ingestion import ingestion_node
from accounting_agents.nodes.reconciliation import reconciliation_node
from accounting_agents.nodes.hitl import hitl_node
from accounting_agents.nodes.ap import ap_node
from accounting_agents.nodes.ar import ar_node
from accounting_agents.nodes.reporting import reporting_node
from accounting_agents.nodes.compliance import compliance_node
from accounting_agents.nodes.onboarding import onboarding_node
from accounting_agents.routing import (
    route_after_ingestion,
    route_after_reconciliation,
    route_after_hitl,
    route_after_ap,
    route_after_ar,
    route_after_reporting,
    route_after_compliance,
    route_after_onboarding,
)


def build_graph(checkpointer: SqliteSaver):
    """Build and compile the AccountingAgents LangGraph StateGraph."""

    graph = StateGraph(AccountingAgentsState)

    # --- Nodes ---
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("reconciliation", reconciliation_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("ap", ap_node)
    graph.add_node("ar", ar_node)
    graph.add_node("reporting", reporting_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("onboarding", onboarding_node)

    # --- Edges ---
    graph.add_edge(START, "ingestion")

    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "reconciliation": "reconciliation",
            "ap": "ap",
            "ar": "ar",
            "reporting": "reporting",
            "compliance": "compliance",
            "onboarding": "onboarding",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "reconciliation",
        route_after_reconciliation,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {
            "reconciliation": "reconciliation",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "ap",
        route_after_ap,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "ar",
        route_after_ar,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "reporting",
        route_after_reporting,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "compliance",
        route_after_compliance,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    graph.add_conditional_edges(
        "onboarding",
        route_after_onboarding,
        {
            "hitl": "hitl",
            "end": END,
        }
    )

    return graph.compile(checkpointer=checkpointer)
