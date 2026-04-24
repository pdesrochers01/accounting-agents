"""
AccountingAgents Phase 2 — Live HITL demo script.
Full pipeline: QBO MCP fetch → Hydro-Québec N3 gap → real Gmail → interrupt → webhook resume.

Phase 2 bank_statement is aligned to the real QBO sandbox CA bills:
  - Fournisseur Général Inc.  $1,200.00 CAD  → exact match (no gap)
  - Vidéotron                 $  185.00 CAD  → exact match (no gap)
  - Bell Canada               $  320.00 CAD  → exact match (no gap)
  - Hydro-Québec              $4,900.00 CAD  → QBO has $2,450.00 → delta $2,450.00 → N3 ✅
  Jennifer Hargreaves / Kristina Gibson: not in bank_statement → unmatched N1 (no HITL)
  Hall's Promotional International: HKD → excluded by CAD filter (no HITL)
"""

import json
import os
import sqlite3
import uuid

os.environ["QBO_MODE"] = "mcp"

from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph
from accounting_agents.state import initial_state

DB_PATH = "demo_accounting_agents.db"

PHASE2_BANK_STATEMENT = [
    {
        "entry_id": "bnq-2026-03-001",
        "date": "2026-03-05",
        "vendor_or_client": "Fournisseur Général Inc.",
        "amount": 1200.00,
    },
    {
        "entry_id": "bnq-2026-03-002",
        "date": "2026-03-10",
        "vendor_or_client": "Vidéotron",
        "amount": 185.00,
    },
    {
        "entry_id": "bnq-2026-03-003",
        "date": "2026-03-15",
        "vendor_or_client": "Bell Canada",
        "amount": 320.00,
    },
    {
        "entry_id": "bnq-2026-03-004",
        "date": "2026-03-22",
        "vendor_or_client": "Hydro-Québec",
        "amount": 4900.00,  # QBO has $2,450.00 → delta $2,450.00 → N3
    },
]


def run_demo():
    print("\n" + "=" * 60)
    print("AccountingAgents Phase 2 — Live HITL Demo")
    print("QBO_MODE=mcp | HITL_MODE=gmail")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

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
        "qbo_transactions": [],          # unused in QBO_MODE=mcp
        "bank_statement": PHASE2_BANK_STATEMENT,
    }

    print(f"\nThread ID: {thread_id}")
    print("\nPhase A — fetching real QBO bills and running pipeline until interrupt()...")
    print("-" * 60)

    result_a = graph.invoke(state, config=config)

    gaps = result_a.get("reconciliation_gaps", [])
    print(f"\nGaps detected: {len(gaps)}")
    for gap in gaps:
        print(f"  → {gap['vendor_or_client']}: "
              f"expected ${gap['expected_amount']:,.2f} | "
              f"actual ${gap['actual_amount']:,.2f} | "
              f"delta ${gap['delta']:,.2f} [{gap['escalation_level']}]")

    hitl_mode = os.getenv("HITL_MODE", "mock")
    if hitl_mode == "gmail":
        print(f"\n📧 Real Gmail notification sent to {os.getenv('HITL_NOTIFY_EMAIL')}")
    else:
        email_files = [
            f for f in os.listdir("hitl_emails")
            if f.startswith(f"hitl_{thread_id[:8]}")
        ]
        if email_files:
            with open(f"hitl_emails/{email_files[0]}") as f:
                email = json.load(f)
            print(f"\nMock notification email:")
            print(f"  To:      {email['to']}")
            print(f"  Subject: {email['subject']}")

    base_url = os.getenv(
        "HITL_WEBHOOK_BASE_URL",
        "http://localhost:5001"
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
    print("(Flask logs in Terminal 1 will confirm receipt)")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    run_demo()
