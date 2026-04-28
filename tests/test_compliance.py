"""
Tests for the Compliance Agent node (Phase 4).
Run: PYTHONPATH=. .venv/bin/python tests/test_compliance.py
"""

import sys
from datetime import date, timedelta

from accounting_agents.nodes.compliance import compliance_node
from accounting_agents.state import ComplianceInput, ComplianceItem, initial_state


# ── Helpers ──────────────────────────────────────────────────────

def _make_item(
    obligation_type: str,
    jurisdiction: str,
    days_offset: int,
    amount_due: float | None = None,
) -> ComplianceItem:
    """Build a ComplianceItem with days_remaining computed from days_offset."""
    today = date.today()
    deadline_date = today + timedelta(days=days_offset)
    days_remaining = (deadline_date - today).days
    if days_remaining > 30:
        status, level = "ok", "N1"
    elif days_remaining >= 8:
        status, level = "upcoming", "N2"
    elif days_remaining >= 1:
        status, level = "urgent", "N3"
    else:
        status, level = "overdue", "N4"

    return ComplianceItem(
        obligation_type=obligation_type,
        jurisdiction=jurisdiction,
        deadline=deadline_date.isoformat(),
        amount_due=amount_due,
        days_remaining=days_remaining,
        status=status,
        escalation_level=level,
    )


def _state_with(
    compliance_input: ComplianceInput | None = None,
    compliance_items: list[ComplianceItem] | None = None,
) -> dict:
    """Build a minimal state dict for compliance_node injection."""
    base = dict(initial_state("test-thread"))
    base["compliance_input"] = compliance_input
    if compliance_items is not None:
        base["compliance_results"] = compliance_items
    return base


def _run(state: dict) -> dict:
    return compliance_node(state)


# ── Tests ─────────────────────────────────────────────────────────

def test_compliance_fixture_default():
    """compliance_input=None → uses fixture; expect 6 items, at least one 'ok'."""
    result = _run(_state_with(compliance_input=None))
    items = result["compliance_results"]
    assert len(items) == 6, f"Expected 6 items, got {len(items)}"
    assert any(i["status"] == "ok" for i in items), "Expected at least one 'ok' item"
    print("✅ test_compliance_fixture_default passed")


def test_compliance_n1_all_ok():
    """All deadlines > 30 days → routing_signal='completed', hitl_pending=False."""
    compliance_input = ComplianceInput(
        client_id="TEST-001", fiscal_period="2026-Q1", jurisdiction="CA"
    )
    # Override by injecting pre-classified N1 items directly via compliance_input=CA
    # with all deadlines forced far in the future.
    # We patch via a custom compliance_input that drives _default_mock_deadlines
    # but all items must be N1 — so we inject a state with compliance_items manually.
    items = [
        _make_item("gst_remittance", "CA", +45, 3200.00),   # N1
        _make_item("t4_filing",      "CA", +60, None),        # N1
    ]
    state = _state_with(compliance_input=None)
    # Inject the compliance_node call with a synthetic "all N1" input via items only.
    # Since the node re-fetches from input, we set compliance_input to CA jurisdiction
    # and trust the fixture. But fixture includes N2/N3/N4 items.
    # So instead: directly verify the routing logic by building a custom test state
    # where we use compliance_items that are all N1 — and call compliance_node with a
    # mock-mode-safe workaround: inject compliance_items in result manually.
    #
    # The cleanest approach: test with compliance_input=CA+far-future by temporarily
    # monkey-patching _fetch_deadlines. We avoid that; instead test via injected items
    # through a wrapper.
    from accounting_agents.nodes import compliance as compliance_module
    original_fetch = compliance_module._fetch_deadlines

    def mock_fetch(inp):
        return items

    compliance_module._fetch_deadlines = mock_fetch
    try:
        result = _run(_state_with(compliance_input=ComplianceInput(
            client_id="TEST-N1", fiscal_period="2026-Q1", jurisdiction="CA"
        )))
    finally:
        compliance_module._fetch_deadlines = original_fetch

    assert result["routing_signal"] == "completed", (
        f"Expected 'completed', got {result['routing_signal']!r}"
    )
    assert result["hitl_pending"] is False
    print("✅ test_compliance_n1_all_ok passed")


def test_compliance_n2_upcoming():
    """One deadline at 12 days (N2), rest > 30 → routing_signal='hitl_pending', highest N2."""
    items = [
        _make_item("gst_remittance", "CA", +45, 3200.00),   # N1
        _make_item("qst_remittance", "QC", +12, 1850.00),   # N2
        _make_item("t4_filing",      "CA", +60, None),        # N1
    ]

    from accounting_agents.nodes import compliance as compliance_module
    original_fetch = compliance_module._fetch_deadlines

    def mock_fetch(inp):
        return items

    compliance_module._fetch_deadlines = mock_fetch
    try:
        result = _run(_state_with(compliance_input=ComplianceInput(
            client_id="TEST-N2", fiscal_period="2026-Q1", jurisdiction="QC+CA"
        )))
    finally:
        compliance_module._fetch_deadlines = original_fetch

    assert result["routing_signal"] == "hitl_pending", (
        f"Expected 'hitl_pending', got {result['routing_signal']!r}"
    )
    result_items = result["compliance_results"]
    highest = max(result_items, key=lambda i: {"N1": 1, "N2": 2, "N3": 3, "N4": 4}[i["escalation_level"]])
    assert highest["escalation_level"] == "N2", (
        f"Expected highest N2, got {highest['escalation_level']}"
    )
    print("✅ test_compliance_n2_upcoming passed")


def test_compliance_n3_urgent():
    """One deadline at 3 days (N3) → routing_signal='hitl_pending', N3 present."""
    items = [
        _make_item("payroll_deductions", "CA", +3, 4100.00),  # N3
        _make_item("t4_filing",          "CA", +60, None),     # N1
    ]

    from accounting_agents.nodes import compliance as compliance_module
    original_fetch = compliance_module._fetch_deadlines

    def mock_fetch(inp):
        return items

    compliance_module._fetch_deadlines = mock_fetch
    try:
        result = _run(_state_with(compliance_input=ComplianceInput(
            client_id="TEST-N3", fiscal_period="2026-Q1", jurisdiction="CA"
        )))
    finally:
        compliance_module._fetch_deadlines = original_fetch

    assert result["routing_signal"] == "hitl_pending"
    result_items = result["compliance_results"]
    assert any(i["escalation_level"] == "N3" for i in result_items), (
        "Expected at least one N3 item"
    )
    print("✅ test_compliance_n3_urgent passed")


def test_compliance_n4_overdue():
    """One deadline at -2 days (overdue) → routing_signal='hitl_pending', status='overdue'."""
    items = [
        _make_item("corporate_tax", "CA", -2, 8500.00),  # N4 overdue
        _make_item("t4_filing",     "CA", +60, None),     # N1
    ]

    from accounting_agents.nodes import compliance as compliance_module
    original_fetch = compliance_module._fetch_deadlines

    def mock_fetch(inp):
        return items

    compliance_module._fetch_deadlines = mock_fetch
    try:
        result = _run(_state_with(compliance_input=ComplianceInput(
            client_id="TEST-N4", fiscal_period="2026-Q1", jurisdiction="CA"
        )))
    finally:
        compliance_module._fetch_deadlines = original_fetch

    assert result["routing_signal"] == "hitl_pending"
    result_items = result["compliance_results"]
    assert any(i["status"] == "overdue" for i in result_items), (
        "Expected at least one 'overdue' item"
    )
    print("✅ test_compliance_n4_overdue passed")


def test_compliance_jurisdiction_ca():
    """Jurisdiction CA-only → all results have jurisdiction=='CA'."""
    compliance_input = ComplianceInput(
        client_id="TEST-CA", fiscal_period="2026-Q1", jurisdiction="CA"
    )
    result = _run(_state_with(compliance_input=compliance_input))
    result_items = result["compliance_results"]
    assert len(result_items) > 0, "Expected at least one item for CA"
    assert all(i["jurisdiction"] == "CA" for i in result_items), (
        f"Expected all CA items; got: {[i['jurisdiction'] for i in result_items]}"
    )
    print("✅ test_compliance_jurisdiction_ca passed")


def test_compliance_jurisdiction_qc_ca():
    """Jurisdiction QC+CA → results contain both QC and CA items."""
    compliance_input = ComplianceInput(
        client_id="TEST-QCCA", fiscal_period="2026-Q1", jurisdiction="QC+CA"
    )
    result = _run(_state_with(compliance_input=compliance_input))
    result_items = result["compliance_results"]
    jurisdictions = {i["jurisdiction"] for i in result_items}
    assert "QC" in jurisdictions, "Expected at least one QC item"
    assert "CA" in jurisdictions, "Expected at least one CA item"
    print("✅ test_compliance_jurisdiction_qc_ca passed")


# ── Runner ────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_compliance_fixture_default,
        test_compliance_n1_all_ok,
        test_compliance_n2_upcoming,
        test_compliance_n3_urgent,
        test_compliance_n4_overdue,
        test_compliance_jurisdiction_ca,
        test_compliance_jurisdiction_qc_ca,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"❌ {test.__name__} FAILED: {exc}")
            failed += 1

    print(f"\n{'All' if failed == 0 else f'{passed}/{len(tests)}'} compliance tests passed.")
    if failed:
        sys.exit(1)
