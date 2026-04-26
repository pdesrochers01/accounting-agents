"""
Unit tests for the AR Agent node (UC04).
No MCP, no LangGraph graph execution — pure node logic.

Invoices are injected via state["ar_invoices"] so tests are deterministic
regardless of when they run. Due dates are computed relative to today.

Test coverage:
  - N1: 28 days overdue, $2,000 CAD → reminder_sent, routing: completed
  - N2: 45 days overdue, $1,500 CAD → second_reminder_sent, routing: completed
  - N3 (days): 75 days overdue, $3,000 CAD → hitl_required, routing: hitl_pending
  - N3 (amount): 20 days overdue, $6,000 CAD → hitl_required, routing: hitl_pending
  - N4 (disputed): disputed invoice → unrecognized_client, routing: unrecognized
  - nothing_to_collect: empty invoice list → nothing_to_collect
  - Signal priority: N3 wins over N1 when multiple invoices are present
"""

from datetime import date, timedelta

from accounting_agents.nodes.ar import ar_node
from accounting_agents.state import initial_state


# ── Helpers ──────────────────────────────────────────────────────

def _days_ago(n: int) -> str:
    """Return an ISO 8601 date string for n days before today."""
    return (date.today() - timedelta(days=n)).isoformat()


def _invoice(
    invoice_id: str,
    client: str,
    amount_cad: float,
    days_overdue: int,
    disputed: bool = False,
) -> dict:
    return {
        "invoice_id": invoice_id,
        "client": client,
        "amount_cad": amount_cad,
        "due_date": _days_ago(days_overdue),
        "currency": "CAD",
        "disputed": disputed,
    }


def _state_with(invoices: list[dict], thread_id: str = "test-ar") -> dict:
    state = initial_state(thread_id)
    state["ar_invoices"] = invoices
    return state


# ── Tests ────────────────────────────────────────────────────────

def test_ar_n1_auto_reminder():
    """28 days overdue, $2,000 CAD → N1 reminder_sent, terminal (completed)."""
    state = _state_with(
        [_invoice("AR-N1-001", "Constructions Dubois Inc.", 2000.00, 28)],
        "test-ar-n1",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "completed"
    assert result["hitl_pending"] is False
    assert len(result["ar_actions"]) == 1
    action = result["ar_actions"][0]
    assert action["action_taken"] == "reminder_sent"
    assert action["escalation_level"] == "N1"
    assert action["days_overdue"] == 28
    assert action["amount_cad"] == 2000.00
    assert action["client"] == "Constructions Dubois Inc."
    assert result["error_log"] == []
    print(f"✅ test_ar_n1_auto_reminder passed — {action['action_taken']} ({action['escalation_level']})")


def test_ar_n2_second_reminder():
    """45 days overdue, $1,500 CAD → N2 second_reminder_sent, terminal (completed)."""
    state = _state_with(
        [_invoice("AR-N2-001", "Services Tremblay Ltée", 1500.00, 45)],
        "test-ar-n2",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "completed"
    assert result["hitl_pending"] is False
    assert len(result["ar_actions"]) == 1
    action = result["ar_actions"][0]
    assert action["action_taken"] == "second_reminder_sent"
    assert action["escalation_level"] == "N2"
    assert action["days_overdue"] == 45
    assert action["amount_cad"] == 1500.00
    assert result["error_log"] == []
    print(f"✅ test_ar_n2_second_reminder passed — {action['action_taken']} ({action['escalation_level']})")


def test_ar_n3_days_overdue():
    """75 days overdue, $3,000 CAD → N3 hitl_required (> 60 days threshold)."""
    state = _state_with(
        [_invoice("AR-N3-001", "Groupe Lafontaine", 3000.00, 75)],
        "test-ar-n3-days",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert len(result["ar_actions"]) == 1
    action = result["ar_actions"][0]
    assert action["action_taken"] == "hitl_required"
    assert action["escalation_level"] == "N3"
    assert action["days_overdue"] == 75
    assert result["error_log"] == []
    print(f"✅ test_ar_n3_days_overdue passed — {action['action_taken']} ({action['escalation_level']})")


def test_ar_n3_large_amount():
    """20 days overdue, $6,000 CAD → N3 hitl_required (amount ≥ $5,000)."""
    state = _state_with(
        [_invoice("AR-N3-002", "Immeubles Côté", 6000.00, 20)],
        "test-ar-n3-amount",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert len(result["ar_actions"]) == 1
    action = result["ar_actions"][0]
    assert action["action_taken"] == "hitl_required"
    assert action["escalation_level"] == "N3"
    assert action["amount_cad"] == 6000.00
    assert result["error_log"] == []
    print(f"✅ test_ar_n3_large_amount passed — {action['action_taken']} ({action['escalation_level']})")


def test_ar_n4_disputed_client():
    """Disputed invoice → N4 unrecognized_client, routing: unrecognized."""
    state = _state_with(
        [_invoice("AR-N4-001", "Industries XYZ", 1800.00, 40, disputed=True)],
        "test-ar-n4",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "unrecognized"
    assert result["hitl_pending"] is False
    assert len(result["ar_actions"]) == 1
    action = result["ar_actions"][0]
    assert action["action_taken"] == "unrecognized_client"
    assert action["escalation_level"] == "N4"
    assert result["error_log"] == []
    print(f"✅ test_ar_n4_disputed_client passed — {action['action_taken']} ({action['escalation_level']})")


def test_ar_nothing_to_collect():
    """No invoices injected → nothing_to_collect, no actions added."""
    state = _state_with([], "test-ar-empty")
    result = ar_node(state)

    assert result["routing_signal"] == "nothing_to_collect"
    assert result["hitl_pending"] is False
    assert result["ar_actions"] == []
    assert result["error_log"] == []
    print("✅ test_ar_nothing_to_collect passed")


def test_ar_signal_priority_n3_wins():
    """N1 + N3 invoices together → routing_signal is hitl_pending (N3 wins)."""
    state = _state_with(
        [
            _invoice("AR-PRI-001", "Constructions Dubois Inc.", 2000.00, 28),   # N1
            _invoice("AR-PRI-002", "Groupe Lafontaine", 3000.00, 75),           # N3
        ],
        "test-ar-priority",
    )
    result = ar_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["hitl_pending"] is True
    assert len(result["ar_actions"]) == 2

    n1_action = next(a for a in result["ar_actions"] if a["invoice_id"] == "AR-PRI-001")
    n3_action = next(a for a in result["ar_actions"] if a["invoice_id"] == "AR-PRI-002")
    assert n1_action["escalation_level"] == "N1"
    assert n3_action["escalation_level"] == "N3"
    print("✅ test_ar_signal_priority_n3_wins passed — hitl_pending prevails over completed")


if __name__ == "__main__":
    test_ar_n1_auto_reminder()
    test_ar_n2_second_reminder()
    test_ar_n3_days_overdue()
    test_ar_n3_large_amount()
    test_ar_n4_disputed_client()
    test_ar_nothing_to_collect()
    test_ar_signal_priority_n3_wins()
    print("\nAll AR Agent tests passed.")
