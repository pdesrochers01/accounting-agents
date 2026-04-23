# HITL node — stub (Gmail MCP + interrupt() in Phase 2)
from accounting_agents.state import AccountingAgentsState


def hitl_node(state: AccountingAgentsState) -> dict:
    """Stub: simulates a human approval decision."""
    return {
        "hitl_decision": "approve",
        "hitl_pending": False,
        "error_log": state.get("error_log", []),
    }
