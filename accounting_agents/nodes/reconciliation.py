"""
Reconciliation Agent node — real implementation.

Matching logic:
- Match on vendor_or_client (exact) + date (±3 days) + amount (exact)
- Gap = bank_amount - qbo_amount
- abs(gap) < 500    → N1 (automatic, no HITL)
- abs(gap) > 2000   → N3 (HITL required)
- 500 <= gap <= 2000 → N2 (notify only, out of MVP scope → treated as N1)
- Unmatched transaction → N3 if amount > 2000, else N1
"""

import uuid
from datetime import datetime, timedelta
from accounting_agents.state import AccountingAgentsState, ReconciliationGap


# --- Thresholds ---
N1_THRESHOLD = 500.00    # below this: automatic
N3_THRESHOLD = 2000.00   # above this: HITL required


def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _dates_within(date1: str, date2: str, days: int = 3) -> bool:
    return abs((_parse_date(date1) - _parse_date(date2)).days) <= days


def _determine_escalation(delta: float) -> str:
    if abs(delta) >= N3_THRESHOLD:
        return "N3"
    return "N1"


def _match_transactions(
    qbo_transactions: list[dict],
    bank_statement: list[dict],
) -> list[ReconciliationGap]:
    """
    Match QBO transactions against bank statement entries.
    Returns list of gaps (unmatched or amount-discrepant transactions).
    """
    gaps: list[ReconciliationGap] = []
    matched_bank_ids = set()

    for qbo_tx in qbo_transactions:
        matched = False

        for bank_entry in bank_statement:
            if bank_entry["entry_id"] in matched_bank_ids:
                continue

            vendor_match = (
                qbo_tx["vendor_or_client"].lower()
                == bank_entry["vendor_or_client"].lower()
            )
            date_match = _dates_within(qbo_tx["date"], bank_entry["date"])

            if vendor_match and date_match:
                matched_bank_ids.add(bank_entry["entry_id"])
                delta = bank_entry["amount"] - qbo_tx["amount"]

                if abs(delta) > 0.01:  # float tolerance
                    gaps.append(
                        ReconciliationGap(
                            gap_id=str(uuid.uuid4()),
                            document_id=qbo_tx.get("document_number", ""),
                            transaction_id=qbo_tx["transaction_id"],
                            expected_amount=qbo_tx["amount"],
                            actual_amount=bank_entry["amount"],
                            delta=round(delta, 2),
                            date_expected=qbo_tx["date"],
                            date_actual=bank_entry["date"],
                            vendor_or_client=qbo_tx["vendor_or_client"],
                            escalation_level=_determine_escalation(delta),
                        )
                    )
                matched = True
                break

        if not matched:
            # QBO transaction with no bank counterpart
            gaps.append(
                ReconciliationGap(
                    gap_id=str(uuid.uuid4()),
                    document_id=qbo_tx.get("document_number", ""),
                    transaction_id=qbo_tx["transaction_id"],
                    expected_amount=qbo_tx["amount"],
                    actual_amount=0.00,
                    delta=round(-qbo_tx["amount"], 2),
                    date_expected=qbo_tx["date"],
                    date_actual="",
                    vendor_or_client=qbo_tx["vendor_or_client"],
                    escalation_level=_determine_escalation(qbo_tx["amount"]),
                )
            )

    return gaps


def reconciliation_node(state: AccountingAgentsState) -> dict:
    """
    Real Reconciliation Agent node.

    Reads documents_ingested from SharedState.
    For MVP: uses bank_statement injected into first document's metadata
    via the 'bank_statement' key (set by Ingestion Agent or test harness).
    """
    error_log = list(state.get("error_log", []))

    # Human-authorized modification: accountant provided a comment via HITL.
    # Treat the comment as override authorization and complete without re-escalating.
    # Without this, the "modify" routing path loops: reconciliation re-detects the
    # same N3 gap and triggers a new HITL interrupt indefinitely.
    if state.get("hitl_comment"):
        return {
            "routing_signal": "completed",
            "hitl_pending": False,
            "error_log": error_log,
        }

    # --- Extract data from SharedState ---
    documents_ingested = state.get("documents_ingested", [])

    if not documents_ingested:
        return {
            "routing_signal": "nothing_to_reconcile",
            "reconciliation_gaps": [],
            "error_log": error_log,
        }

    # For MVP: bank_statement and qbo_transactions are injected
    # via the first document's metadata fields
    first_doc = documents_ingested[0]
    qbo_transactions = first_doc.get("qbo_transactions", [])
    bank_statement = first_doc.get("bank_statement", [])

    if not qbo_transactions or not bank_statement:
        return {
            "routing_signal": "nothing_to_reconcile",
            "reconciliation_gaps": [],
            "error_log": error_log,
        }

    # --- Run matching ---
    gaps = _match_transactions(qbo_transactions, bank_statement)

    # --- Determine routing ---
    n3_gaps = [g for g in gaps if g["escalation_level"] == "N3"]

    if n3_gaps:
        routing_signal = "hitl_pending"
        hitl_pending = True
    else:
        routing_signal = "completed"
        hitl_pending = False

    return {
        "reconciliation_gaps": gaps,
        "routing_signal": routing_signal,
        "hitl_pending": hitl_pending,
        "error_log": error_log,
    }
