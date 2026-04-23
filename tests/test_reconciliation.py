"""
Unit tests for the real Reconciliation Agent node.
Uses fixture scenarios — no MCP, no LangGraph graph execution.
"""

from accounting_agents.nodes.reconciliation import reconciliation_node
from accounting_agents.state import initial_state
from tests.fixtures.scenarios import scenario_clean, scenario_gap_n3


def _build_state(scenario: dict) -> dict:
    """Inject scenario data into SharedState via first document metadata."""
    state = initial_state("test-thread-001")
    state["documents_ingested"] = [
        {
            "document_id": "test-doc-001",
            "document_type": "bank_statement",
            "date": "2026-03-31",
            "amount": 0.0,
            "currency": "CAD",
            "vendor_or_client": "Banque Nationale",
            "document_number": "BNQ-MARCH-2026",
            "qbo_entry_id": "",
            "source_email_id": "",
            "qbo_transactions": scenario["qbo_transactions"],
            "bank_statement": scenario["bank_statement"],
        }
    ]
    return state


def test_scenario_clean():
    s = scenario_clean()
    state = _build_state(s)
    result = reconciliation_node(state)

    assert result["routing_signal"] == "completed", \
        f"Expected completed, got {result['routing_signal']}"
    assert result["hitl_pending"] == False
    assert result["reconciliation_gaps"] == []
    print("✅ test_scenario_clean passed")


def test_scenario_gap_n3():
    s = scenario_gap_n3()
    state = _build_state(s)
    result = reconciliation_node(state)

    assert result["routing_signal"] == "hitl_pending", \
        f"Expected hitl_pending, got {result['routing_signal']}"
    assert result["hitl_pending"] == True

    gaps = result["reconciliation_gaps"]
    assert len(gaps) == 1, f"Expected 1 gap, got {len(gaps)}"

    gap = gaps[0]
    assert gap["vendor_or_client"] == "Hydro-Québec"
    assert gap["escalation_level"] == "N3"
    assert gap["delta"] == 2450.00
    print(f"✅ test_scenario_gap_n3 passed — gap: {gap['vendor_or_client']} "
          f"delta=${gap['delta']} {gap['escalation_level']}")


if __name__ == "__main__":
    test_scenario_clean()
    test_scenario_gap_n3()
    print("All reconciliation tests passed.")
