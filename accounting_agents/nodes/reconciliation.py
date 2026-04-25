"""
Reconciliation Agent node — Phase 2 real implementation.

Matching logic:
- Match on vendor_or_client (exact) + date (±3 days) + amount (exact)
- Gap = bank_amount - qbo_amount
- abs(gap) < 500    → N1 (automatic, no HITL)
- abs(gap) > 2000   → N3 (HITL required)
- 500 <= gap <= 2000 → N2 (notify only, out of MVP scope → treated as N1)
- Unmatched transaction → N3 if amount > 2000, else N1

QBO_MODE=mock : uses qbo_transactions + bank_statement injected via input_document
QBO_MODE=mcp  : fetches real bills from QBO sandbox via Intuit MCP stdio server
                 bank_statement still injected via input_document (Phase 2)
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv

from accounting_agents.state import AccountingAgentsState, ReconciliationGap

load_dotenv()


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


# ── QBO MCP integration (Phase 2) ───────────────────────────────

async def _fetch_qbo_bills_mcp() -> list[dict]:
    """
    Fetch all open bills from QBO sandbox via the Intuit MCP stdio server.
    Returns a list of dicts: {vendor_name, amount, currency, qbo_bill_id, date}
    """
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession

    mcp_path = os.getenv("QBO_MCP_SERVER_PATH", "")
    if not mcp_path:
        raise RuntimeError("QBO_MCP_SERVER_PATH not set in environment")

    token_file = os.getenv("QBO_TOKEN_FILE", "qbo_token.json")
    with open(token_file) as f:
        token = json.load(f)

    qbo_env = {
        "QUICKBOOKS_CLIENT_ID":     os.getenv("QBO_CLIENT_ID", ""),
        "QUICKBOOKS_CLIENT_SECRET":  os.getenv("QBO_CLIENT_SECRET", ""),
        "QUICKBOOKS_REALM_ID":       os.getenv("QBO_REALM_ID", ""),
        "QUICKBOOKS_ENVIRONMENT":    os.getenv("QBO_ENVIRONMENT", "sandbox"),
        "QUICKBOOKS_REFRESH_TOKEN":  token["refresh_token"],
    }

    params = StdioServerParameters(command="node", args=[mcp_path], env={**qbo_env, "NODE_NO_WARNINGS": "1"})
    bills: list[dict] = []

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_bills", {"params": {"criteria": []}}
            )

            if result.isError:
                raise RuntimeError(f"search_bills MCP error: {result.content}")

            for block in result.content:
                text = getattr(block, "text", "")
                if not text.startswith("{"):
                    continue  # skip summary line
                try:
                    bill = json.loads(text)
                    vendor_ref = bill.get("VendorRef", {})
                    currency_ref = bill.get("CurrencyRef", {})
                    lines = bill.get("Line", [])
                    amount = float(lines[0]["Amount"]) if lines else 0.0
                    bills.append({
                        "vendor_name": vendor_ref.get("name", "Unknown"),
                        "amount":      amount,
                        "currency":    currency_ref.get("value", "CAD"),
                        "qbo_bill_id": bill["Id"],
                        "date":        bill.get("TxnDate", ""),
                    })
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    print(f"[reconciliation_node] Fetched {len(bills)} bills via QBO MCP")
    return bills


def _compare_with_bank_statement(
    qbo_bills: list[dict],
    bank_statement: list[dict],
) -> list[ReconciliationGap]:
    """
    Convert MCP bill format to the transaction format expected by
    _match_transactions(), then run the existing matching logic.
    Only CAD bills are compared — non-CAD transactions belong to separate
    foreign-currency accounts and must not pollute a CAD bank reconciliation.
    """
    cad_bills = [b for b in qbo_bills if b.get("currency") == "CAD"]
    qbo_transactions = [
        {
            "transaction_id":   bill["qbo_bill_id"],
            "date":             bill["date"],
            "vendor_or_client": bill["vendor_name"],
            "amount":           bill["amount"],
            "document_number":  bill["qbo_bill_id"],
        }
        for bill in cad_bills
    ]
    return _match_transactions(qbo_transactions, bank_statement)


# ── Main node ────────────────────────────────────────────────────

def reconciliation_node(state: AccountingAgentsState) -> dict:
    """
    Real Reconciliation Agent node.

    QBO_MODE=mock: reads qbo_transactions + bank_statement from first
                   document's injected metadata (fixtures / test harness).
    QBO_MODE=mcp:  fetches real bills from QBO sandbox via MCP stdio server;
                   bank_statement still injected via input_document (Phase 2).
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

    documents_ingested = state.get("documents_ingested", [])

    if not documents_ingested:
        return {
            "routing_signal": "nothing_to_reconcile",
            "reconciliation_gaps": [],
            "error_log": error_log,
        }

    first_doc = documents_ingested[0]
    bank_statement = first_doc.get("bank_statement", [])
    qbo_mode = os.getenv("QBO_MODE", "mock")

    # --- QBO data source ---
    if qbo_mode == "mcp":
        if not bank_statement:
            return {
                "routing_signal": "nothing_to_reconcile",
                "reconciliation_gaps": [],
                "error_log": error_log,
            }
        try:
            qbo_bills = asyncio.run(_fetch_qbo_bills_mcp())
        except RuntimeError:
            # asyncio.run() raises RuntimeError if a loop is already running.
            # Fall back to a fresh loop to handle nested async contexts.
            loop = asyncio.new_event_loop()
            try:
                qbo_bills = loop.run_until_complete(_fetch_qbo_bills_mcp())
            finally:
                loop.close()
        except Exception as exc:
            error_log.append(f"[reconciliation_node] MCP fetch failed: {exc}")
            return {
                "routing_signal": "nothing_to_reconcile",
                "reconciliation_gaps": [],
                "error_log": error_log,
            }
        gaps = _compare_with_bank_statement(qbo_bills, bank_statement)

    else:
        # Mock mode: fixture injection via first document's metadata
        qbo_transactions = first_doc.get("qbo_transactions", [])
        if not qbo_transactions or not bank_statement:
            return {
                "routing_signal": "nothing_to_reconcile",
                "reconciliation_gaps": [],
                "error_log": error_log,
            }
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
