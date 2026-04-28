"""
Tests for the Onboarding Agent node (Phase 4).
Run: PYTHONPATH=. .venv/bin/python tests/test_onboarding.py
"""

import sys

from accounting_agents.nodes.onboarding import onboarding_node
from accounting_agents.state import OnboardingInput, initial_state


# ── Helpers ──────────────────────────────────────────────────────

_VALID_INPUT = OnboardingInput(
    client_name="Gestion Tremblay inc.",
    legal_form="corporation",
    address="123 rue Principale, Saint-Jérôme, QC J7Z 1X1",
    contact_email="info@gestiontremblay.qc.ca",
    fiscal_year_end="12-31",
    jurisdiction="QC+CA",
    neq="123456789",
    gst_number="123456789RT0001",
    qst_number="1234567890TQ0001",
)


def _state_with(onboarding_input: OnboardingInput | None) -> dict:
    base = dict(initial_state("test-thread"))
    base["onboarding_input"] = onboarding_input
    return base


def _run(onboarding_input: OnboardingInput | None) -> dict:
    return onboarding_node(_state_with(onboarding_input))


# ── Tests ─────────────────────────────────────────────────────────

def test_onboarding_fixture_default():
    """
    onboarding_input=None → uses fixture; fixture NEQ is invalid (10 digits) →
    status=='validation_failed', 'neq' mentioned in validation_errors.
    """
    result = _run(None)
    draft = result["onboarding_draft"]
    assert draft["status"] == "validation_failed", (
        f"Expected 'validation_failed', got {draft['status']!r}"
    )
    errors_text = " ".join(draft["validation_errors"]).lower()
    assert "neq" in errors_text, (
        f"Expected 'neq' in validation errors; got: {draft['validation_errors']}"
    )
    print("✅ test_onboarding_fixture_default passed")


def test_onboarding_valid_all_fields():
    """
    Valid input → status=='draft_ready', escalation_level=='N2',
    routing_signal=='hitl_pending', hitl_pending==True.
    """
    result = _run(_VALID_INPUT)
    draft = result["onboarding_draft"]
    assert draft["status"] == "draft_ready", (
        f"Expected 'draft_ready', got {draft['status']!r}"
    )
    assert draft["escalation_level"] == "N2", (
        f"Expected 'N2', got {draft['escalation_level']!r}"
    )
    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert draft["validation_errors"] == []
    print("✅ test_onboarding_valid_all_fields passed")


def test_onboarding_missing_mandatory_field():
    """Missing contact_email → validation_failed, escalation_level=='N4'."""
    inp = OnboardingInput(
        client_name="Gestion Tremblay inc.",
        legal_form="corporation",
        address="123 rue Principale, Saint-Jérôme, QC J7Z 1X1",
        contact_email="",           # missing
        fiscal_year_end="12-31",
        jurisdiction="QC+CA",
        neq="123456789",
        gst_number="123456789RT0001",
        qst_number="1234567890TQ0001",
    )
    result = _run(inp)
    draft = result["onboarding_draft"]
    assert draft["status"] == "validation_failed", (
        f"Expected 'validation_failed', got {draft['status']!r}"
    )
    assert draft["escalation_level"] == "N4"
    print("✅ test_onboarding_missing_mandatory_field passed")


def test_onboarding_invalid_neq():
    """NEQ '12345' (5 digits) → validation error mentioning 'neq'."""
    inp = OnboardingInput(**{**dict(_VALID_INPUT), "neq": "12345"})
    result = _run(inp)
    draft = result["onboarding_draft"]
    errors_text = " ".join(draft["validation_errors"]).lower()
    assert "neq" in errors_text, (
        f"Expected 'neq' error; got: {draft['validation_errors']}"
    )
    print("✅ test_onboarding_invalid_neq passed")


def test_onboarding_invalid_gst():
    """GST '123456789' (missing RT suffix) → validation error mentioning 'gst'."""
    inp = OnboardingInput(**{**dict(_VALID_INPUT), "gst_number": "123456789"})
    result = _run(inp)
    draft = result["onboarding_draft"]
    errors_text = " ".join(draft["validation_errors"]).lower()
    assert "gst" in errors_text, (
        f"Expected 'gst' error; got: {draft['validation_errors']}"
    )
    print("✅ test_onboarding_invalid_gst passed")


def test_onboarding_invalid_qst():
    """QST 'ABCDEFGHIJ' (non-numeric) → validation error mentioning 'qst'."""
    inp = OnboardingInput(**{**dict(_VALID_INPUT), "qst_number": "ABCDEFGHIJ"})
    result = _run(inp)
    draft = result["onboarding_draft"]
    errors_text = " ".join(draft["validation_errors"]).lower()
    assert "qst" in errors_text, (
        f"Expected 'qst' error; got: {draft['validation_errors']}"
    )
    print("✅ test_onboarding_invalid_qst passed")


def test_onboarding_no_identifiers():
    """
    neq=None, gst_number=None, qst_number=None with valid mandatory fields →
    status=='draft_ready', escalation_level=='N2'.
    Missing optional identifiers are NOT a validation error.
    """
    inp = OnboardingInput(
        client_name="Gestion Tremblay inc.",
        legal_form="sole_proprietorship",
        address="123 rue Principale, Saint-Jérôme, QC J7Z 1X1",
        contact_email="info@gestiontremblay.qc.ca",
        fiscal_year_end="12-31",
        jurisdiction="QC",
        neq=None,
        gst_number=None,
        qst_number=None,
    )
    result = _run(inp)
    draft = result["onboarding_draft"]
    assert draft["status"] == "draft_ready", (
        f"Expected 'draft_ready', got {draft['status']!r}"
    )
    assert draft["escalation_level"] == "N2"
    assert draft["validation_errors"] == []
    print("✅ test_onboarding_no_identifiers passed")


# ── Runner ────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_onboarding_fixture_default,
        test_onboarding_valid_all_fields,
        test_onboarding_missing_mandatory_field,
        test_onboarding_invalid_neq,
        test_onboarding_invalid_gst,
        test_onboarding_invalid_qst,
        test_onboarding_no_identifiers,
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

    print(f"\n{'All' if failed == 0 else f'{passed}/{len(tests)}'} onboarding tests passed.")
    if failed:
        sys.exit(1)
