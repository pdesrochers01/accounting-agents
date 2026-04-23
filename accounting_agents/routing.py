from accounting_agents.state import AccountingAgentsState


def route_after_ingestion(state: AccountingAgentsState) -> str:
    """Route after ingestion_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "to_reconciliation":
        return "reconciliation"
    # covers: "unrecognized", None, any error
    return "end"


def route_after_reconciliation(state: AccountingAgentsState) -> str:
    """Route after reconciliation_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed", "nothing_to_reconcile"
    return "end"


def route_after_hitl(state: AccountingAgentsState) -> str:
    """Route after hitl_node based on hitl_decision."""
    decision = state.get("hitl_decision")
    if decision == "modify":
        return "reconciliation"
    # covers: "approve", "block", "timeout"
    return "end"
