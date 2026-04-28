"""
Compliance Agent node — Tax & Regulatory Obligations (Phase 4).

Responsibilities:
  1. Read compliance_input from state; use fixture if None.
  2. Fetch upcoming tax/regulatory deadlines (mock or MCP).
  3. Classify each deadline by days_remaining:
     > 30 days  → ok       / N1
     8–30 days  → upcoming / N2
     1–7 days   → urgent   / N3
     ≤ 0 days   → overdue  / N4
  4. Determine highest escalation level across all items.
  5. Route to hitl if highest >= N2; otherwise completed.
  6. Write hitl_emails/compliance_{client_id}_{fiscal_period}.json (mock mode).
  7. Return delta only — never full state.

COMPLIANCE_MODE=mock (default): hardcoded fixture deadlines relative to today
COMPLIANCE_MODE=mcp (Phase 4+):  query QBO / RevenuQuebec MCP
"""

import json
import os
from datetime import date, datetime, timedelta, timezone

from accounting_agents.state import (
    AccountingAgentsState,
    ComplianceInput,
    ComplianceItem,
)

# ── Constants ────────────────────────────────────────────────────
COMPLIANCE_EMAILS_DIR = "hitl_emails"

_ESCALATION_PRIORITY: dict[str, int] = {"N4": 4, "N3": 3, "N2": 2, "N1": 1}


# ── Escalation classifier ────────────────────────────────────────

def _classify_deadline(days_remaining: int) -> tuple[str, str]:
    """Return (status, escalation_level) based on days_remaining."""
    if days_remaining > 30:
        return "ok", "N1"
    if days_remaining >= 8:
        return "upcoming", "N2"
    if days_remaining >= 1:
        return "urgent", "N3"
    return "overdue", "N4"


def _highest_escalation(items: list[ComplianceItem]) -> str:
    """Return the highest escalation level across all items."""
    best = "N1"
    for item in items:
        if _ESCALATION_PRIORITY.get(item["escalation_level"], 0) > _ESCALATION_PRIORITY.get(best, 0):
            best = item["escalation_level"]
    return best


# ── Mock fixture ─────────────────────────────────────────────────

def _default_mock_deadlines(jurisdiction: str) -> list[ComplianceItem]:
    """
    Fixture deadlines computed relative to today.
    Covers all 4 statuses and both QC + CA jurisdictions.
    Items are filtered by jurisdiction parameter.
    """
    today = date.today()

    candidates: list[tuple[str, str, int, float | None]] = [
        # (obligation_type, jurisdiction, days_offset, amount_due)
        ("gst_remittance",      "CA", +45,  3200.00),
        ("qst_remittance",      "QC", +12,  1850.00),
        ("payroll_deductions",  "CA",  +3,  4100.00),
        ("corporate_tax",       "CA",  -2,  8500.00),
        ("t4_filing",           "CA", +60,  None),
        ("rl1_filing",          "QC", +60,  None),
    ]

    include_qc = "QC" in jurisdiction
    include_ca = "CA" in jurisdiction

    items: list[ComplianceItem] = []
    for obligation_type, jur, days_offset, amount_due in candidates:
        if jur == "QC" and not include_qc:
            continue
        if jur == "CA" and not include_ca:
            continue

        deadline_date = today + timedelta(days=days_offset)
        days_remaining = (deadline_date - today).days
        status, escalation_level = _classify_deadline(days_remaining)

        items.append(ComplianceItem(
            obligation_type=obligation_type,
            jurisdiction=jur,
            deadline=deadline_date.isoformat(),
            amount_due=amount_due,
            days_remaining=days_remaining,
            status=status,
            escalation_level=escalation_level,
        ))

    return items


def _fetch_deadlines(compliance_input: ComplianceInput) -> list[ComplianceItem]:
    """Fetch compliance deadlines — mock or MCP."""
    compliance_mode = os.getenv("COMPLIANCE_MODE", "mock")

    if compliance_mode == "mcp":
        raise NotImplementedError("COMPLIANCE_MODE=mcp not implemented yet — Phase 4+")

    return _default_mock_deadlines(compliance_input["jurisdiction"])


# ── Mock output writer ───────────────────────────────────────────

def _write_compliance_output(
    client_id: str,
    fiscal_period: str,
    items: list[ComplianceItem],
) -> None:
    """Write compliance results to hitl_emails/ (mock mode)."""
    os.makedirs(COMPLIANCE_EMAILS_DIR, exist_ok=True)
    slug = fiscal_period.replace("-", "_").replace("+", "_")
    filename = f"{COMPLIANCE_EMAILS_DIR}/compliance_{client_id}_{slug}.json"

    payload = {
        "type": "compliance_results",
        "client_id": client_id,
        "fiscal_period": fiscal_period,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [dict(item) for item in items],
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[compliance_node] Results written → {filename} ({len(items)} obligations)")


# ── Main node ────────────────────────────────────────────────────

def compliance_node(state: AccountingAgentsState) -> dict:
    """
    Compliance Agent node. Assesses tax and regulatory deadlines.
    Returns delta only — never the full state.
    """
    error_log = list(state.get("error_log", []))

    raw_input = state.get("compliance_input")
    if raw_input is None:
        compliance_input = ComplianceInput(
            client_id="CLIENT-001",
            fiscal_period="2026-Q1",
            jurisdiction="QC+CA",
        )
        print("[compliance_node] No compliance_input in state — using fixture.")
    else:
        compliance_input = raw_input

    items = _fetch_deadlines(compliance_input)

    highest = _highest_escalation(items)

    if highest == "N1":
        routing_signal = "completed"
        hitl_pending = False
    else:
        routing_signal = "hitl_pending"
        hitl_pending = True

    compliance_mode = os.getenv("COMPLIANCE_MODE", "mock")
    if compliance_mode == "mock":
        _write_compliance_output(
            compliance_input["client_id"],
            compliance_input["fiscal_period"],
            items,
        )

    print(
        f"[compliance_node] {len(items)} obligations assessed "
        f"| highest: {highest} | signal: {routing_signal}"
    )

    return {
        "compliance_results": items,
        "routing_signal": routing_signal,
        "hitl_pending": hitl_pending,
        "error_log": error_log,
    }
