"""
AP Agent node — Accounts Payable (Phase 3).

Responsibilities (UC05):
  1. Read documents_ingested — filter for supplier_invoice only
  2. Check vendor against QBO (AP_MODE=mock: fixture list; AP_MODE=mcp: Phase 4)
  3. Classify by escalation level and emit routing_signal:
     N1: known vendor, amount < $500 CAD  → auto_approved  → "completed"
     N2: known vendor, $500–$2,000 CAD    → flagged        → "completed"
     N3: amount > $2,000 OR unknown vendor → hitl_required → "hitl_pending"
     N4: unrecognized vendor pattern       → hitl_required → "unrecognized"
  4. Duplicate detection: vendor + amount already in ap_actions → "duplicate_bill"
  5. Return delta only (never full state)

AP flows are terminal — AP does NOT route to reconciliation.
Reconciliation is triggered independently by bank statement ingestion.

AP_MODE=mock (default): hardcoded fixture vendor registry
AP_MODE=mcp (Phase 4):  query QBO MCP for live vendor lookup
"""

import os
import uuid
from datetime import datetime, timezone

from accounting_agents.state import (
    AccountingAgentsState,
    APAction,
    EscalationLevel,
)

# ── Thresholds ───────────────────────────────────────────────────
N1_MAX = 500.00
N2_MAX = 2000.00

# ── Mock vendor registry (AP_MODE=mock) ─────────────────────────
KNOWN_VENDORS: frozenset[str] = frozenset({
    "hydro-québec",
    "hydro-quebec",
    "vidéotron",
    "videotron",
    "bell canada",
    "bell",
    "bureau en gros",
    "telus",
    "rogers",
})

# ── Signal priority — highest-priority signal wins across invoices
_SIGNAL_PRIORITY: dict[str, int] = {
    "hitl_pending":   4,
    "unrecognized":   3,
    "duplicate_bill": 2,
    "completed":      1,
}


def _normalize_vendor(vendor: str) -> str:
    return vendor.strip().lower()


def _is_unrecognized_vendor(vendor: str) -> bool:
    """N4: vendor field is empty, 'Unknown', or too short to be a real name."""
    normalized = _normalize_vendor(vendor)
    return not normalized or normalized == "unknown" or len(normalized) < 3


def _is_known_vendor_mock(vendor: str) -> bool:
    return _normalize_vendor(vendor) in KNOWN_VENDORS


def _escalation_level(is_known: bool, amount: float) -> EscalationLevel:
    if amount > N2_MAX or not is_known:
        return "N3"
    if amount < N1_MAX:
        return "N1"
    return "N2"


def _is_duplicate(vendor: str, amount: float, actions: list[APAction]) -> bool:
    """True if vendor + amount already processed with a non-duplicate decision."""
    norm = _normalize_vendor(vendor)
    for action in actions:
        if (
            _normalize_vendor(action["vendor"]) == norm
            and abs(action["amount"] - amount) < 0.01
            and action["decision"] != "duplicate"
        ):
            return True
    return False


def _pick_signal(current: str, candidate: str) -> str:
    if _SIGNAL_PRIORITY.get(candidate, 0) > _SIGNAL_PRIORITY.get(current, 0):
        return candidate
    return current


# ── Main node ────────────────────────────────────────────────────

def ap_node(state: AccountingAgentsState) -> dict:
    """
    AP Agent node. Processes all supplier invoices in documents_ingested.
    Returns delta only — never the full state.
    """
    error_log = list(state.get("error_log", []))
    documents_ingested = state.get("documents_ingested", [])
    existing_actions = list(state.get("ap_actions", []))

    invoices = [
        doc for doc in documents_ingested
        if doc.get("document_type") == "supplier_invoice"
    ]

    if not invoices:
        return {
            "routing_signal": "completed",
            "hitl_pending": False,
            "ap_actions": existing_actions,
            "error_log": error_log,
        }

    new_actions: list[APAction] = []
    routing_signal = "completed"
    hitl_pending = False

    for invoice in invoices:
        vendor  = invoice.get("vendor_or_client", "Unknown")
        amount  = invoice.get("amount", 0.0)
        doc_id  = invoice.get("document_id", "")
        now_iso = datetime.now(timezone.utc).isoformat()

        # N4 — unrecognized vendor pattern
        if _is_unrecognized_vendor(vendor):
            new_actions.append(APAction(
                action_id=str(uuid.uuid4()),
                document_id=doc_id,
                vendor=vendor,
                amount=amount,
                decision="hitl_required",
                escalation_level="N4",
                timestamp=now_iso,
                notes="Unrecognized vendor pattern — cannot classify.",
            ))
            routing_signal = _pick_signal(routing_signal, "unrecognized")
            print(f"[ap_node] UNRECOGNIZED vendor pattern: '{vendor}'")
            continue

        # Duplicate detection
        if _is_duplicate(vendor, amount, existing_actions + new_actions):
            new_actions.append(APAction(
                action_id=str(uuid.uuid4()),
                document_id=doc_id,
                vendor=vendor,
                amount=amount,
                decision="duplicate",
                escalation_level="N1",
                timestamp=now_iso,
                notes=f"Duplicate: {vendor} ${amount:,.2f} CAD already processed.",
            ))
            routing_signal = _pick_signal(routing_signal, "duplicate_bill")
            print(f"[ap_node] DUPLICATE: {vendor} ${amount:,.2f} CAD")
            continue

        # Escalation (mock vendor lookup)
        is_known = _is_known_vendor_mock(vendor)
        level    = _escalation_level(is_known, amount)

        if level == "N1":
            decision = "auto_approved"
            notes    = f"Known vendor. ${amount:,.2f} CAD below N1 threshold — auto-approved."
        elif level == "N2":
            decision = "flagged"
            notes    = f"Known vendor. ${amount:,.2f} CAD flagged for notification (N2)."
        else:  # N3
            decision = "hitl_required"
            reason   = "amount exceeds $2,000 CAD" if amount > N2_MAX else "vendor not in QBO"
            notes    = f"HITL required ({reason}). Amount: ${amount:,.2f} CAD."

        new_actions.append(APAction(
            action_id=str(uuid.uuid4()),
            document_id=doc_id,
            vendor=vendor,
            amount=amount,
            decision=decision,
            escalation_level=level,
            timestamp=now_iso,
            notes=notes,
        ))
        print(f"[ap_node] {decision.upper()}: {vendor} ${amount:,.2f} CAD ({level})")

        if level == "N3":
            routing_signal = _pick_signal(routing_signal, "hitl_pending")
            hitl_pending = True

    return {
        "ap_actions": existing_actions + new_actions,
        "routing_signal": routing_signal,
        "hitl_pending": hitl_pending,
        "error_log": error_log,
    }
