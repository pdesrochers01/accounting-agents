from accounting_agents.state import AccountingAgentsState


def route_after_ingestion(state: AccountingAgentsState) -> str:
    """Route after ingestion_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "to_reconciliation":
        return "reconciliation"
    if signal == "to_ap":
        return "ap"
    if signal == "to_ar":
        return "ar"
    if signal == "to_reporting":
        return "reporting"
    if signal == "to_compliance":
        return "compliance"
    if signal == "to_onboarding":
        return "onboarding"
    # covers: "unrecognized", None, any error
    return "end"


def route_after_reporting(state: AccountingAgentsState) -> str:
    """Route after reporting_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed" (N1/N2), "no_report_data", "unrecognized" (N4)
    return "end"


def route_after_ar(state: AccountingAgentsState) -> str:
    """Route after ar_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed" (N1/N2), "nothing_to_collect", "unrecognized"
    return "end"


def route_after_ap(state: AccountingAgentsState) -> str:
    """Route after ap_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed" (N1/N2), "duplicate_bill", "unrecognized"
    return "end"


def route_after_reconciliation(state: AccountingAgentsState) -> str:
    """Route after reconciliation_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed", "nothing_to_reconcile"
    return "end"


def route_after_compliance(state: AccountingAgentsState) -> str:
    """Route after compliance_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # covers: "completed" (N1 — all ok)
    return "end"


def route_after_onboarding(state: AccountingAgentsState) -> str:
    """Route after onboarding_node based on routing_signal."""
    signal = state.get("routing_signal")
    if signal == "hitl_pending":
        return "hitl"
    # onboarding always routes to hitl (N2 or N4) — this is a safety fallback
    return "end"


def route_after_hitl(state: AccountingAgentsState) -> str:
    """Route after hitl_node based on hitl_decision."""
    decision = state.get("hitl_decision")
    if decision == "modify":
        return "reconciliation"
    # covers: "approve", "block", "timeout"
    return "end"
