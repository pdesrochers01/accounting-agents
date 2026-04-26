"""
Unit tests for the AP Agent node (UC05).
No MCP, no LangGraph graph execution — pure node logic.

Test coverage:
  - N1: known vendor, $300 CAD → auto_approved, routing_signal: completed
  - N2: known vendor, $1,200 CAD → flagged, routing_signal: completed
  - N3 (amount): known vendor, $3,500 CAD → hitl_required, routing_signal: hitl_pending
  - N3 (unknown vendor): unknown vendor, $800 CAD → hitl_required, routing_signal: hitl_pending
  - N4: unrecognized vendor pattern → hitl_required, routing_signal: unrecognized
  - Duplicate bill detection → routing_signal: duplicate_bill
  - No invoices in state → routing_signal: completed, ap_actions unchanged
"""

import uuid

from accounting_agents.nodes.ap import ap_node
from accounting_agents.state import initial_state, APAction


# ── Helpers ──────────────────────────────────────────────────────

def _make_invoice(vendor: str, amount: float, doc_type: str = "supplier_invoice") -> dict:
    return {
        "document_id": str(uuid.uuid4()),
        "document_type": doc_type,
        "date": "2026-04-01",
        "amount": amount,
        "currency": "CAD",
        "vendor_or_client": vendor,
        "document_number": f"INV-{uuid.uuid4().hex[:6].upper()}",
        "qbo_entry_id": "",
        "source_email_id": "gmail-test",
    }


def _state_with_invoice(vendor: str, amount: float, thread_id: str = "test-ap-001") -> dict:
    state = initial_state(thread_id)
    state["documents_ingested"] = [_make_invoice(vendor, amount)]
    return state


# ── Tests ────────────────────────────────────────────────────────

def test_ap_n1_auto_approve():
    """Known vendor, $300 CAD → N1 auto-approved, terminal (completed)."""
    state = _state_with_invoice("Telus", 300.00, "test-ap-n1")
    result = ap_node(state)

    assert result["routing_signal"] == "completed"
    assert result["hitl_pending"] is False
    assert len(result["ap_actions"]) == 1
    action = result["ap_actions"][0]
    assert action["decision"] == "auto_approved"
    assert action["escalation_level"] == "N1"
    assert action["vendor"] == "Telus"
    assert action["amount"] == 300.00
    assert result["error_log"] == []
    print(f"✅ test_ap_n1_auto_approve passed — {action['notes']}")


def test_ap_n2_flagged():
    """Known vendor, $1,200 CAD → N2 flagged, terminal (completed)."""
    state = _state_with_invoice("Bell Canada", 1200.00, "test-ap-n2")
    result = ap_node(state)

    assert result["routing_signal"] == "completed"
    assert result["hitl_pending"] is False
    assert len(result["ap_actions"]) == 1
    action = result["ap_actions"][0]
    assert action["decision"] == "flagged"
    assert action["escalation_level"] == "N2"
    assert action["vendor"] == "Bell Canada"
    assert action["amount"] == 1200.00
    assert result["error_log"] == []
    print(f"✅ test_ap_n2_flagged passed — {action['notes']}")


def test_ap_n3_amount_exceeds_threshold():
    """Known vendor, $3,500 CAD → N3 hitl_required (amount > $2,000)."""
    state = _state_with_invoice("Hydro-Québec", 3500.00, "test-ap-n3-amount")
    result = ap_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert len(result["ap_actions"]) == 1
    action = result["ap_actions"][0]
    assert action["decision"] == "hitl_required"
    assert action["escalation_level"] == "N3"
    assert "amount exceeds $2,000 CAD" in action["notes"]
    assert result["error_log"] == []
    print(f"✅ test_ap_n3_amount_exceeds_threshold passed — {action['notes']}")


def test_ap_n3_unknown_vendor():
    """Unknown vendor, $800 CAD → N3 hitl_required (vendor not in QBO)."""
    state = _state_with_invoice("Acme Corp Inconnu", 800.00, "test-ap-n3-vendor")
    result = ap_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert len(result["ap_actions"]) == 1
    action = result["ap_actions"][0]
    assert action["decision"] == "hitl_required"
    assert action["escalation_level"] == "N3"
    assert "vendor not in QBO" in action["notes"]
    assert result["error_log"] == []
    print(f"✅ test_ap_n3_unknown_vendor passed — {action['notes']}")


def test_ap_n4_unrecognized_vendor():
    """Vendor field is 'Unknown' → N4, routing_signal: unrecognized."""
    state = _state_with_invoice("Unknown", 500.00, "test-ap-n4")
    result = ap_node(state)

    assert result["routing_signal"] == "unrecognized"
    assert len(result["ap_actions"]) == 1
    action = result["ap_actions"][0]
    assert action["decision"] == "hitl_required"
    assert action["escalation_level"] == "N4"
    assert result["error_log"] == []
    print(f"✅ test_ap_n4_unrecognized_vendor passed — {action['notes']}")


def test_ap_duplicate_detection():
    """Second invoice with same vendor + amount → duplicate_bill."""
    vendor = "Vidéotron"
    amount = 650.00
    thread_id = "test-ap-dup"

    # Pre-populate ap_actions with a prior processed action
    prior_action = APAction(
        action_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        vendor=vendor,
        amount=amount,
        decision="flagged",
        escalation_level="N2",
        timestamp="2026-04-01T10:00:00+00:00",
        notes="Prior processing.",
    )

    state = _state_with_invoice(vendor, amount, thread_id)
    state["ap_actions"] = [prior_action]

    result = ap_node(state)

    assert result["routing_signal"] == "duplicate_bill"
    assert result["hitl_pending"] is False
    # ap_actions grows: prior + new duplicate action
    assert len(result["ap_actions"]) == 2
    dup_action = result["ap_actions"][-1]
    assert dup_action["decision"] == "duplicate"
    assert dup_action["escalation_level"] == "N1"
    assert "Duplicate" in dup_action["notes"]
    assert result["error_log"] == []
    print(f"✅ test_ap_duplicate_detection passed — {dup_action['notes']}")


def test_ap_no_invoices():
    """No supplier_invoice in documents_ingested → completed, no new actions."""
    state = initial_state("test-ap-empty")
    state["documents_ingested"] = [_make_invoice("Telus", 300.00, doc_type="bank_statement")]

    result = ap_node(state)

    assert result["routing_signal"] == "completed"
    assert result["hitl_pending"] is False
    assert result["ap_actions"] == []
    assert result["error_log"] == []
    print("✅ test_ap_no_invoices passed")


if __name__ == "__main__":
    test_ap_n1_auto_approve()
    test_ap_n2_flagged()
    test_ap_n3_amount_exceeds_threshold()
    test_ap_n3_unknown_vendor()
    test_ap_n4_unrecognized_vendor()
    test_ap_duplicate_detection()
    test_ap_no_invoices()
    print("\nAll AP Agent tests passed.")
