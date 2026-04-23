# Reconciliation Agent node — stub (MCP integration in Phase 2)
from accounting_agents.state import AccountingAgentsState


def reconciliation_node(state: AccountingAgentsState) -> dict:
    """Stub: simulates a reconciliation gap triggering N3 HITL."""
    return {
        "routing_signal": "hitl_pending",
        "hitl_pending": True,
        "error_log": state.get("error_log", []),
    }
