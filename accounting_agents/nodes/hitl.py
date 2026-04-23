"""
HITL node — real implementation.

Two-phase execution within a single LangGraph node:

  Phase A (first entry):
    1. Build structured notification email
    2. Send via Gmail MCP or write to hitl_emails/ (mock mode)
    3. Write timeout_at to SharedState
    4. Call interrupt() — thread suspended here

  Phase B (after webhook resume):
    1. hitl_decision is already in SharedState (injected by webhook)
    2. Clear hitl_pending, clear timeout_at
    3. Return routing delta for Supervisor

Detection: if hitl_decision is not None → we are in Phase B.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from langgraph.types import interrupt

from accounting_agents.state import AccountingAgentsState, ReconciliationGap

load_dotenv()

HITL_MODE = os.getenv("HITL_MODE", "mock")
HITL_WEBHOOK_BASE_URL = os.getenv("HITL_WEBHOOK_BASE_URL", "http://localhost:5000")
HITL_NOTIFY_EMAIL = os.getenv("HITL_NOTIFY_EMAIL", "accountant@example.com")
HITL_TIMEOUT_HOURS = 4
HITL_EMAILS_DIR = "hitl_emails"


# ── Email builder ────────────────────────────────────────────────

def _build_email(
    thread_id: str,
    gap: ReconciliationGap,
) -> dict:
    """Build structured HITL notification email."""

    base_url = HITL_WEBHOOK_BASE_URL.rstrip("/")

    def action_url(decision: str) -> str:
        return f"{base_url}/webhook?thread_id={thread_id}&decision={decision}"

    subject = (
        f"[AccountingAgents] Action required — "
        f"Reconciliation gap detected"
    )

    body = f"""AccountingAgents — Human Approval Required
{'=' * 50}

Vendor:   {gap['vendor_or_client']}
Expected: ${gap['expected_amount']:,.2f} CAD
Actual:   ${gap['actual_amount']:,.2f} CAD
Gap:      ${abs(gap['delta']):,.2f} CAD ({gap['escalation_level']} — approval required)

Date expected: {gap['date_expected']}
Date actual:   {gap['date_actual'] or 'not found in bank statement'}

ACTION REQUIRED — please click one link below:

  APPROVE : {action_url('approve')}
  MODIFY  : {action_url('modify')}
  BLOCK   : {action_url('block')}

This request expires in {HITL_TIMEOUT_HOURS} hours.
Thread ID: {thread_id}
"""

    return {
        "to": HITL_NOTIFY_EMAIL,
        "subject": subject,
        "body": body,
        "thread_id": thread_id,
        "gap": gap,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Notification dispatch ────────────────────────────────────────

def _send_mock(email: dict) -> None:
    """Write email to hitl_emails/ and log to console."""
    os.makedirs(HITL_EMAILS_DIR, exist_ok=True)
    filename = f"{HITL_EMAILS_DIR}/hitl_{email['thread_id'][:8]}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(email, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("HITL NOTIFICATION (mock mode)")
    print(f"{'=' * 60}")
    print(f"To:      {email['to']}")
    print(f"Subject: {email['subject']}")
    print(f"\n{email['body']}")
    print(f"Saved to: {filename}")
    print(f"{'=' * 60}\n")


def _send_notification(email: dict) -> None:
    """Dispatch notification — mock or Gmail MCP."""
    if HITL_MODE == "mock":
        _send_mock(email)
    else:
        # Gmail MCP integration — Phase 2
        raise NotImplementedError(
            "Gmail MCP not yet configured. Set HITL_MODE=mock in .env"
        )


# ── Decision handler (Phase B) ───────────────────────────────────

def _handle_decision(state: AccountingAgentsState) -> dict:
    """Phase B: process decision received via webhook."""
    decision = state.get("hitl_decision")
    comment = state.get("hitl_comment", "")

    print(f"\n[HITL] Thread resumed — decision: {decision}")
    if comment:
        print(f"[HITL] Comment: {comment}")

    return {
        "hitl_pending": False,
        "timeout_at": None,
        "error_log": state.get("error_log", []),
    }


# ── Main node ────────────────────────────────────────────────────

def hitl_node(state: AccountingAgentsState) -> dict:
    """
    HITL node — two-phase execution.
    Phase A: send notification + interrupt().
    Phase B: process decision after webhook resume.
    """

    # Phase B — resuming after webhook delivered decision
    if state.get("hitl_decision") is not None:
        return _handle_decision(state)

    # Phase A — first entry, no decision yet
    thread_id = state.get("thread_id", str(uuid.uuid4()))
    gaps = state.get("reconciliation_gaps", [])
    error_log = list(state.get("error_log", []))

    if not gaps:
        error_log.append("[hitl_node] hitl_pending=True but no gaps found")
        return {
            "hitl_pending": False,
            "error_log": error_log,
        }

    # Use first N3 gap as the primary escalation subject
    n3_gaps = [g for g in gaps if g["escalation_level"] == "N3"]
    primary_gap = n3_gaps[0] if n3_gaps else gaps[0]

    # Build and send notification
    email = _build_email(thread_id, primary_gap)
    _send_notification(email)

    # Set timeout
    timeout_at = datetime.now(timezone.utc) + timedelta(hours=HITL_TIMEOUT_HOURS)

    # Suspend thread — LangGraph persists state via SqliteSaver
    interrupt("awaiting_hitl_decision")

    # Code below never executes on Phase A — only after resume
    return {
        "timeout_at": timeout_at,
        "error_log": error_log,
    }
