from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from accounting_agents.state import AccountingAgentsState
from accounting_agents.nodes.ingestion import ingestion_node
from accounting_agents.nodes.reconciliation import reconciliation_node
from accounting_agents.nodes.hitl import hitl_node
from accounting_agents.routing import (
    route_after_ingestion,
    route_after_reconciliation,
    route_after_hitl,
)


def build_graph(checkpointer: SqliteSaver):
    """Build and compile the AccountingAgents LangGraph StateGraph."""

    graph = StateGraph(AccountingAgentsState)

    # --- Nodes ---
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("reconciliation", reconciliation_node)
    graph.add_node("hitl", hitl_node)

    # --- Edges ---
    graph.add_edge(START, "ingestion")

    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "reconciliation": "reconciliation",
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

    return graph.compile(checkpointer=checkpointer)
