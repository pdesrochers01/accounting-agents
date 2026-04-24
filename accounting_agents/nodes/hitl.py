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

import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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


def _send_gmail(email: dict) -> None:
    """Send HITL notification via Gmail API using stored OAuth credentials."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = os.getenv("GMAIL_TOKEN_FILE", "token.json")
    secret_file = os.getenv("GMAIL_CLIENT_SECRET_FILE", "client_secret.json")
    scopes = ["https://www.googleapis.com/auth/gmail.send"]

    creds = Credentials.from_authorized_user_file(token_file, scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())

    gap = email["gap"]
    thread_id = email["thread_id"]
    subject = f"[HITL] Reconciliation gap requires approval — {thread_id}"

    base_url = HITL_WEBHOOK_BASE_URL.rstrip("/")

    def action_url(decision: str) -> str:
        return f"{base_url}/webhook?thread_id={thread_id}&decision={decision}"

    html_body = f"""
<html><body>
<h2>AccountingAgents — Human Approval Required</h2>
<table>
  <tr><td><b>Vendor</b></td><td>{gap['vendor_or_client']}</td></tr>
  <tr><td><b>Expected</b></td><td>${gap['expected_amount']:,.2f} CAD</td></tr>
  <tr><td><b>Actual</b></td><td>${gap['actual_amount']:,.2f} CAD</td></tr>
  <tr><td><b>Gap</b></td><td>${abs(gap['delta']):,.2f} CAD ({gap['escalation_level']} — approval required)</td></tr>
  <tr><td><b>Date expected</b></td><td>{gap['date_expected']}</td></tr>
  <tr><td><b>Date actual</b></td><td>{gap['date_actual'] or 'not found'}</td></tr>
</table>
<br>
<p><b>ACTION REQUIRED — click one link below:</b></p>
<p>
  <a href="{action_url('approve')}">✅ APPROVE</a> &nbsp;|&nbsp;
  <a href="{action_url('modify')}">✏️ MODIFY</a> &nbsp;|&nbsp;
  <a href="{action_url('block')}">🚫 BLOCK</a>
</p>
<p>This request expires in {HITL_TIMEOUT_HOURS} hours.<br>Thread ID: {thread_id}</p>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"me"
    msg["To"] = email["to"]
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    print(f"[hitl_node] Gmail sent to {email['to']} (thread {thread_id[:8]})")


def _send_notification(email: dict) -> None:
    """Dispatch notification — mock or Gmail API."""
    if HITL_MODE == "mock":
        _send_mock(email)
    elif HITL_MODE == "gmail":
        _send_gmail(email)
    else:
        raise NotImplementedError(
            f"Unknown HITL_MODE={HITL_MODE!r}. Use 'mock' or 'gmail'."
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
    try:
        _send_notification(email)
    except Exception as exc:
        error_log.append(f"[hitl_node] Notification failed: {exc}")

    # Set timeout
    timeout_at = datetime.now(timezone.utc) + timedelta(hours=HITL_TIMEOUT_HOURS)

    # Suspend thread — LangGraph persists state via SqliteSaver
    interrupt("awaiting_hitl_decision")

    # Code below never executes on Phase A — only after resume
    return {
        "timeout_at": timeout_at,
        "error_log": error_log,
    }
