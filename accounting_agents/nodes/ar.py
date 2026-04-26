"""
AR Agent node — Accounts Receivable (Phase 3).

Responsibilities (UC04):
  1. Fetch open QBO invoices:
     AR_MODE=mock: reads state["ar_invoices"] if populated, else uses
                   built-in fixture (computed relative to today).
     AR_MODE=mcp (Phase 4): will query QBO MCP for live receivables.
  2. Filter: overdue invoices only (days_overdue > 0).
  3. No overdue invoices → routing_signal: "nothing_to_collect".
  4. For each overdue invoice, classify and act:
     N1: days_overdue ≤ 30 AND amount_cad < $5,000  → reminder_sent        → "completed"
     N2: 31–60 days overdue                          → second_reminder_sent → "completed"
     N3: days_overdue > 60 OR amount_cad ≥ $5,000   → hitl_required        → "hitl_pending"
     N4: disputed or unrecognized client             → unrecognized_client  → "unrecognized"
  5. N1/N2: write reminder to hitl_emails/ (mock) or Gmail MCP (Phase 4).
  6. Return delta only (never full state).

Signal priority across multiple invoices: hitl_pending > unrecognized > completed.
AR flows are terminal — AR does NOT route to AP or reconciliation.
"""

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from accounting_agents.state import AccountingAgentsState, ARAction

# ── Thresholds ───────────────────────────────────────────────────
N1_MAX_DAYS   = 30
N2_MAX_DAYS   = 60
N3_AMOUNT_CAD = 5000.00

# ── Output dir for mock reminder emails ─────────────────────────
AR_EMAILS_DIR = "hitl_emails"

# ── Signal priority — highest wins across all invoices ───────────
_SIGNAL_PRIORITY: dict[str, int] = {
    "hitl_pending":      4,
    "unrecognized":      3,
    "completed":         2,
    "nothing_to_collect": 1,
}


# ── Mock fixture ─────────────────────────────────────────────────

def _default_mock_invoices() -> list[dict]:
    """
    Built-in fixture for AR_MODE=mock when no invoices are injected via state.
    Due dates are computed relative to today so days_overdue is always accurate.
    """
    today = date.today()
    return [
        {
            "invoice_id": "AR-MOCK-001",
            "client": "Constructions Dubois Inc.",
            "amount_cad": 2000.00,
            "due_date": (today - timedelta(days=28)).isoformat(),
            "currency": "CAD",
            "disputed": False,
        },
        {
            "invoice_id": "AR-MOCK-002",
            "client": "Services Tremblay Ltée",
            "amount_cad": 1500.00,
            "due_date": (today - timedelta(days=45)).isoformat(),
            "currency": "CAD",
            "disputed": False,
        },
        {
            "invoice_id": "AR-MOCK-003",
            "client": "Groupe Lafontaine",
            "amount_cad": 6000.00,
            "due_date": (today - timedelta(days=75)).isoformat(),
            "currency": "CAD",
            "disputed": False,
        },
    ]


def _fetch_invoices(state: AccountingAgentsState) -> list[dict]:
    """
    Return the invoice list to process.

    None in state  → use built-in mock fixture (default AR_MODE=mock behavior)
    [] in state    → explicitly empty; returns [] so caller yields nothing_to_collect
    [...] in state → use the provided list (test injection or future MCP result)

    In AR_MODE=mcp (Phase 4), this will call QBO MCP regardless of state field.
    """
    ar_mode = os.getenv("AR_MODE", "mock")

    if ar_mode == "mcp":
        raise NotImplementedError("AR_MODE=mcp not implemented yet — Phase 4")

    injected = state.get("ar_invoices")
    return _default_mock_invoices() if injected is None else injected


# ── Escalation helpers ───────────────────────────────────────────

def _compute_days_overdue(due_date: str) -> int:
    due = date.fromisoformat(due_date)
    return max(0, (date.today() - due).days)


def _is_unrecognized_client(client: str, disputed: bool) -> bool:
    """N4: disputed flag set, or client name is empty/too short to identify."""
    if disputed:
        return True
    normalized = client.strip().lower()
    return not normalized or normalized == "unknown" or len(normalized) < 3


def _escalation(days_overdue: int, amount_cad: float) -> str:
    """Return escalation level string for the given days/amount."""
    if days_overdue > N2_MAX_DAYS or amount_cad >= N3_AMOUNT_CAD:
        return "N3"
    if days_overdue > N1_MAX_DAYS:
        return "N2"
    return "N1"


def _pick_signal(current: str, candidate: str) -> str:
    if _SIGNAL_PRIORITY.get(candidate, 0) > _SIGNAL_PRIORITY.get(current, 0):
        return candidate
    return current


# ── Reminder dispatch ────────────────────────────────────────────

def _send_reminder_mock(invoice: dict, action_taken: str, days_overdue: int) -> None:
    """Write AR reminder to hitl_emails/ (mock mode)."""
    os.makedirs(AR_EMAILS_DIR, exist_ok=True)
    inv_id_short = invoice["invoice_id"].replace("/", "-")[:12]
    filename = f"{AR_EMAILS_DIR}/ar_reminder_{inv_id_short}.json"

    payload = {
        "type": "ar_reminder",
        "invoice_id": invoice["invoice_id"],
        "client": invoice["client"],
        "amount_cad": invoice["amount_cad"],
        "days_overdue": days_overdue,
        "action_taken": action_taken,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        f"[ar_node] Reminder written → {filename} "
        f"({invoice['client']}, {days_overdue}d overdue, "
        f"${invoice['amount_cad']:,.2f} CAD)"
    )


def _dispatch_reminder(invoice: dict, action_taken: str, days_overdue: int) -> None:
    """Dispatch reminder — mock writes to file; gmail mode would call Gmail MCP."""
    hitl_mode = os.getenv("HITL_MODE", "mock")
    if hitl_mode in ("mock", ""):
        _send_reminder_mock(invoice, action_taken, days_overdue)
    else:
        # Phase 4: Gmail MCP call goes here
        raise NotImplementedError(
            f"HITL_MODE={hitl_mode!r} not supported for AR reminders — Phase 4"
        )


# ── Main node ────────────────────────────────────────────────────

def ar_node(state: AccountingAgentsState) -> dict:
    """
    AR Agent node. Processes overdue QBO invoices.
    Returns delta only — never the full state.
    """
    error_log = list(state.get("error_log", []))
    existing_actions = list(state.get("ar_actions", []))

    all_invoices = _fetch_invoices(state)
    overdue = [
        inv for inv in all_invoices
        if _compute_days_overdue(inv.get("due_date", "")) > 0
    ]

    if not overdue:
        print("[ar_node] No overdue invoices found.")
        return {
            "routing_signal": "nothing_to_collect",
            "hitl_pending": False,
            "ar_actions": existing_actions,
            "error_log": error_log,
        }

    new_actions: list[ARAction] = []
    routing_signal = "completed"
    hitl_pending = False

    for invoice in overdue:
        client      = invoice.get("client", "Unknown")
        amount_cad  = invoice.get("amount_cad", 0.0)
        invoice_id  = invoice.get("invoice_id", str(uuid.uuid4()))
        disputed    = invoice.get("disputed", False)
        due_date    = invoice.get("due_date", "")
        days_overdue = _compute_days_overdue(due_date)
        now_iso      = datetime.now(timezone.utc).isoformat()

        # N4 — disputed or unrecognized client
        if _is_unrecognized_client(client, disputed):
            new_actions.append(ARAction(
                invoice_id=invoice_id,
                client=client,
                amount_cad=amount_cad,
                days_overdue=days_overdue,
                action_taken="unrecognized_client",
                escalation_level="N4",
                timestamp=now_iso,
            ))
            routing_signal = _pick_signal(routing_signal, "unrecognized")
            print(f"[ar_node] UNRECOGNIZED client: '{client}' (disputed={disputed})")
            continue

        level = _escalation(days_overdue, amount_cad)

        if level == "N1":
            action_taken = "reminder_sent"
        elif level == "N2":
            action_taken = "second_reminder_sent"
        else:  # N3
            action_taken = "hitl_required"

        new_actions.append(ARAction(
            invoice_id=invoice_id,
            client=client,
            amount_cad=amount_cad,
            days_overdue=days_overdue,
            action_taken=action_taken,
            escalation_level=level,
            timestamp=now_iso,
        ))

        if level in ("N1", "N2"):
            _dispatch_reminder(invoice, action_taken, days_overdue)
            print(f"[ar_node] {action_taken.upper()}: {client} "
                  f"${amount_cad:,.2f} CAD ({days_overdue}d overdue, {level})")
        else:  # N3
            routing_signal = _pick_signal(routing_signal, "hitl_pending")
            hitl_pending = True
            print(f"[ar_node] HITL_REQUIRED: {client} "
                  f"${amount_cad:,.2f} CAD ({days_overdue}d overdue, {level})")

    return {
        "ar_actions": existing_actions + new_actions,
        "routing_signal": routing_signal,
        "hitl_pending": hitl_pending,
        "error_log": error_log,
    }
