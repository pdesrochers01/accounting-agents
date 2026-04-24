"""
End-to-end test using real node implementations.
Full pipeline: ingestion → reconciliation → hitl (interrupt + resume)
No MCP — uses mock email and injected fixtures.
"""

import json
import os
import sqlite3
import uuid

os.environ["HITL_MODE"] = "mock"
os.environ["HITL_WEBHOOK_BASE_URL"] = "http://localhost:5000"
os.environ["HITL_NOTIFY_EMAIL"] = "test@lafleur-cpa.example.com"
os.environ["QBO_MODE"] = "mock"

from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph
from accounting_agents.state import initial_state
from tests.fixtures.scenarios import scenario_clean, scenario_gap_n3


def _build_state(scenario: dict, thread_id: str) -> dict:
    """
    Build full initial state for real end-to-end test.
    Injects input_document (for Ingestion Agent) with
    qbo_transactions and bank_statement embedded
    (passed through to Reconciliation Agent).
    """
    state = initial_state(thread_id)
    state["input_document"] = {
        "raw_text": (
            "Relevé bancaire — Banque Nationale du Canada\n"
            "Période: Mars 2026\n"
            "Client: Lafleur & Associés CPA\n"
            "Solde: $4,152.44 CAD\n"
            "Date: 2026-03-31"
        ),
        "source_email_id": "gmail-bnq-march-2026",
        "filename": "releve_bnq_mars2026.pdf",
        "qbo_transactions": scenario["qbo_transactions"],
        "bank_statement": scenario["bank_statement"],
    }
    return state


def test_e2e_clean():
    """
    scenario_clean: all transactions match.
    Expected: ingestion → reconciliation → completed (no HITL).
    """
    print("\n" + "=" * 60)
    print("TEST: test_e2e_clean")
    print("=" * 60)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = _build_state(scenario_clean(), thread_id)

    result = graph.invoke(state, config=config)

    print(f"routing_signal: {result.get('routing_signal')}")
    print(f"hitl_pending:   {result.get('hitl_pending')}")
    print(f"hitl_decision:  {result.get('hitl_decision')}")
    print(f"gaps:           {len(result.get('reconciliation_gaps', []))}")
    print(f"error_log:      {result.get('error_log')}")

    assert result.get("routing_signal") == "completed", \
        f"Expected completed, got {result.get('routing_signal')}"
    assert result.get("hitl_pending") == False
    assert result.get("hitl_decision") is None
    assert result.get("reconciliation_gaps") == []
    assert result.get("error_log") == []
    assert len(result.get("documents_ingested", [])) == 1

    print("✅ test_e2e_clean passed")


def test_e2e_gap_n3_approve():
    """
    scenario_gap_n3: Hydro-Québec gap $2,450 CAD → N3 HITL.
    Expected: ingestion → reconciliation → hitl (interrupt)
              → webhook approve → completed.
    """
    print("\n" + "=" * 60)
    print("TEST: test_e2e_gap_n3_approve")
    print("=" * 60)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = _build_state(scenario_gap_n3(), thread_id)

    # Phase A — runs until interrupt()
    print("Phase A — running until interrupt()...")
    result_a = graph.invoke(state, config=config)

    print(f"routing_signal: {result_a.get('routing_signal')}")
    print(f"hitl_pending:   {result_a.get('hitl_pending')}")
    print(f"gaps detected:  {len(result_a.get('reconciliation_gaps', []))}")

    gaps = result_a.get("reconciliation_gaps", [])
    assert len(gaps) == 1
    assert gaps[0]["vendor_or_client"] == "Hydro-Québec"
    assert gaps[0]["escalation_level"] == "N3"
    assert gaps[0]["delta"] == 2450.00

    # Verify mock email was written
    email_files = [
        f for f in os.listdir("hitl_emails")
        if f.startswith(f"hitl_{thread_id[:8]}")
    ]
    assert len(email_files) == 1, \
        f"Expected 1 email file, found {len(email_files)}"

    with open(f"hitl_emails/{email_files[0]}") as f:
        email = json.load(f)

    print(f"Email saved:    hitl_emails/{email_files[0]}")
    print(f"Email to:       {email['to']}")
    print(f"Approve URL:    "
          f"...?thread_id={thread_id[:8]}...&decision=approve")

    # Phase B — simulate webhook approve
    print("Phase B — simulating webhook approve...")
    result_b = graph.invoke(
        {
            "hitl_decision": "approve",
            "hitl_pending": False,
            "hitl_comment": None,
        },
        config=config,
    )

    print(f"hitl_decision:  {result_b.get('hitl_decision')}")
    print(f"hitl_pending:   {result_b.get('hitl_pending')}")
    print(f"timeout_at:     {result_b.get('timeout_at')}")
    print(f"error_log:      {result_b.get('error_log')}")

    assert result_b.get("hitl_decision") == "approve"
    assert result_b.get("hitl_pending") == False
    assert result_b.get("timeout_at") is None
    assert result_b.get("error_log") == []

    print("✅ test_e2e_gap_n3_approve passed")


def test_e2e_gap_n3_modify():
    """
    scenario_gap_n3: accountant clicks Modify with a comment.
    Expected: hitl → reconciliation re-run → completed.
    """
    print("\n" + "=" * 60)
    print("TEST: test_e2e_gap_n3_modify")
    print("=" * 60)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = _build_state(scenario_gap_n3(), thread_id)

    # Phase A
    print("Phase A — running until interrupt()...")
    graph.invoke(state, config=config)

    # Phase B — simulate webhook modify
    print("Phase B — simulating webhook modify...")
    result_b = graph.invoke(
        {
            "hitl_decision": "modify",
            "hitl_pending": False,
            "hitl_comment": "Hydro-Québec split invoice — correct amount is $312.45",
        },
        config=config,
    )

    print(f"hitl_decision:  {result_b.get('hitl_decision')}")
    print(f"hitl_comment:   {result_b.get('hitl_comment')}")
    print(f"routing_signal: {result_b.get('routing_signal')}")
    print(f"error_log:      {result_b.get('error_log')}")

    # After modify, graph re-routes to reconciliation then completes
    assert result_b.get("hitl_decision") == "modify"
    assert result_b.get("hitl_comment") is not None
    assert result_b.get("error_log") == []

    print("✅ test_e2e_gap_n3_modify passed")


if __name__ == "__main__":
    test_e2e_clean()
    test_e2e_gap_n3_approve()
    test_e2e_gap_n3_modify()
    print("\n" + "=" * 60)
    print("All end-to-end real tests passed.")
    print("=" * 60)
