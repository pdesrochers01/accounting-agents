# Ingestion Agent node — stub (MCP integration in Phase 2)
from accounting_agents.state import AccountingAgentsState


def ingestion_node(state: AccountingAgentsState) -> dict:
    """Stub: simulates a successful document ingestion."""
    return {
        "routing_signal": "to_reconciliation",
        "error_log": state.get("error_log", []),
    }
