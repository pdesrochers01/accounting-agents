"""
AccountingAgents MVP — Live HITL demo script.
Runs the full pipeline with real nodes and live ngrok webhook.
Prints the approve/modify/block URLs for mobile testing.
"""

import json
import os
import sqlite3
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph
from accounting_agents.state import initial_state
from tests.fixtures.scenarios import scenario_gap_n3

DB_PATH = "demo_accounting_agents.db"

def run_demo():
    print("\n" + "=" * 60)
    print("AccountingAgents MVP — Live HITL Demo")
    print("=" * 60)

    # Setup persistent SQLite (survives between Phase A and B)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    scenario = scenario_gap_n3()
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

    print(f"\nThread ID: {thread_id}")
    print("\nPhase A — running pipeline until interrupt()...")
    print("-" * 60)

    # Phase A — runs until interrupt()
    result_a = graph.invoke(state, config=config)

    gaps = result_a.get("reconciliation_gaps", [])
    print(f"\nGaps detected: {len(gaps)}")
    for gap in gaps:
        print(f"  → {gap['vendor_or_client']}: "
              f"expected ${gap['expected_amount']:,.2f} | "
              f"actual ${gap['actual_amount']:,.2f} | "
              f"delta ${gap['delta']:,.2f} [{gap['escalation_level']}]")

    # Print email content
    email_files = [
        f for f in os.listdir("hitl_emails")
        if f.startswith(f"hitl_{thread_id[:8]}")
    ]
    if email_files:
        with open(f"hitl_emails/{email_files[0]}") as f:
            email = json.load(f)
        print(f"\nNotification email:")
        print(f"  To:      {email['to']}")
        print(f"  Subject: {email['subject']}")

    base_url = os.getenv(
        "HITL_WEBHOOK_BASE_URL",
        "http://localhost:5000"
    ).rstrip("/")

    print(f"\n{'=' * 60}")
    print("ACTION LINKS — open from your iPhone:")
    print(f"{'=' * 60}")
    print(f"\n  APPROVE:")
    print(f"  {base_url}/webhook?thread_id={thread_id}&decision=approve&ngrok-skip-browser-warning=true")
    print(f"\n  MODIFY:")
    print(f"  {base_url}/webhook?thread_id={thread_id}&decision=modify&ngrok-skip-browser-warning=true")
    print(f"\n  BLOCK:")
    print(f"  {base_url}/webhook?thread_id={thread_id}&decision=block&ngrok-skip-browser-warning=true")
    print(f"\n{'=' * 60}")
    print("Waiting for webhook decision...")
    print("(check Terminal 1 Flask logs after clicking a link)")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_demo()
