"""
Unit tests for the real HITL node.
Tests Phase A (notification + interrupt) and Phase B (decision handling).
HITL_MODE=mock — no Gmail MCP required.
"""

import os
import json
import sqlite3
import uuid

os.environ["HITL_MODE"] = "mock"
os.environ["HITL_WEBHOOK_BASE_URL"] = "http://localhost:5000"
os.environ["HITL_NOTIFY_EMAIL"] = "test@lafleur-cpa.example.com"

from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph
from accounting_agents.state import initial_state
from tests.fixtures.scenarios import scenario_gap_n3


def _build_state_from_scenario(scenario: dict, thread_id: str) -> dict:
    state = initial_state(thread_id)
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


def test_hitl_full_cycle_approve():
    """
    Full cycle test:
    1. Run graph → reaches interrupt() after HITL notification
    2. Simulate webhook → inject approve decision
    3. Resume graph → verify clean completion
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    scenario = scenario_gap_n3()
    state = _build_state_from_scenario(scenario, thread_id)

    print(f"\nThread ID: {thread_id}")
    print("Phase A — running graph until interrupt()...")

    # Phase A: graph runs until interrupt()
    result_a = graph.invoke(state, config=config)

    print(f"Graph state after interrupt: {result_a.get('__interrupt__', 'suspended')}")

    # Simulate webhook delivering approve decision
    print("Simulating webhook → decision: approve")
    result_b = graph.invoke(
        {
            "hitl_decision": "approve",
            "hitl_pending": False,
            "hitl_comment": None,
        },
        config=config,
    )

    # Assertions
    assert result_b.get("hitl_decision") == "approve", \
        f"Expected approve, got {result_b.get('hitl_decision')}"
    assert result_b.get("hitl_pending") == False
    assert result_b.get("timeout_at") is None
    assert result_b.get("error_log") == []

    # Verify mock email was written
    email_files = [
        f for f in os.listdir("hitl_emails")
        if f.startswith(f"hitl_{thread_id[:8]}")
    ]
    assert len(email_files) == 1, \
        f"Expected 1 email file, found {len(email_files)}"

    with open(f"hitl_emails/{email_files[0]}") as f:
        email = json.load(f)

    assert email["gap"]["vendor_or_client"] == "Hydro-Québec"
    assert email["gap"]["escalation_level"] == "N3"

    print("✅ test_hitl_full_cycle_approve passed")
    print(f"   Email saved: hitl_emails/{email_files[0]}")
    print(f"   Gap: {email['gap']['vendor_or_client']} "
          f"delta=${email['gap']['delta']} {email['gap']['escalation_level']}")


if __name__ == "__main__":
    test_hitl_full_cycle_approve()
    print("\nAll HITL tests passed.")
