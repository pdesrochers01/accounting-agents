"""
Onboarding Agent node — New Client Onboarding (Phase 4).

Responsibilities:
  1. Read onboarding_input from state; use fixture if None.
  2. Validate all mandatory fields and identifier formats.
  3. Build QBO customer payload (always, even if validation errors).
  4. Determine escalation:
     - validation_errors non-empty → N4 / validation_failed
     - validation_errors empty     → N2 / draft_ready
  5. Both N2 and N4 route to hitl (writing to QBO always requires approval).
  6. Write hitl_emails/onboarding_{slug}.json (mock mode).
  7. Return delta only — never full state.

ONBOARDING_MODE=mock (default): uses fixture and writes to hitl_emails/
ONBOARDING_MODE=mcp (Phase 4+):  submits validated payload to QBO MCP
"""

import json
import os
import re
from datetime import datetime, timezone

from accounting_agents.state import (
    AccountingAgentsState,
    OnboardingDraft,
    OnboardingInput,
)

# ── Constants ────────────────────────────────────────────────────
ONBOARDING_EMAILS_DIR = "hitl_emails"

_MANDATORY_FIELDS = (
    "client_name",
    "legal_form",
    "address",
    "contact_email",
    "fiscal_year_end",
)

_RE_NEQ = re.compile(r"^\d{9}$")
_RE_GST = re.compile(r"^\d{9}RT\d{4}$")
_RE_QST = re.compile(r"^\d{10}TQ\d{4}$")


# ── Default fixture ──────────────────────────────────────────────

def _default_onboarding_input() -> OnboardingInput:
    """
    Fixture input — NEQ is intentionally invalid (10 digits instead of 9)
    so the N4 / validation_failed path is exercised by default.
    """
    return OnboardingInput(
        client_name="Gestion Tremblay inc.",
        legal_form="corporation",
        address="123 rue Principale, Saint-Jérôme, QC J7Z 1X1",
        contact_email="info@gestiontremblay.qc.ca",
        fiscal_year_end="12-31",
        jurisdiction="QC+CA",
        neq="1234567890",           # invalid: 10 digits, not 9
        gst_number="123456789RT0001",
        qst_number="1234567890TQ0001",
    )


# ── Validation ───────────────────────────────────────────────────

def _validate_onboarding_input(inp: OnboardingInput) -> list[str]:
    """
    Validate mandatory fields and identifier formats.
    Returns a list of human-readable error strings (empty = valid).
    """
    errors: list[str] = []

    for field in _MANDATORY_FIELDS:
        value = inp.get(field)
        if not value or not str(value).strip():
            errors.append(f"Missing mandatory field: {field}")

    neq = inp.get("neq")
    if neq is not None and not _RE_NEQ.match(neq):
        errors.append(
            f"Invalid neq format: {neq!r} — expected exactly 9 digits (e.g. 123456789)"
        )

    gst = inp.get("gst_number")
    if gst is not None and not _RE_GST.match(gst):
        errors.append(
            f"Invalid gst_number format: {gst!r} — expected 9 digits + RT + 4 digits "
            f"(e.g. 123456789RT0001)"
        )

    qst = inp.get("qst_number")
    if qst is not None and not _RE_QST.match(qst):
        errors.append(
            f"Invalid qst_number format: {qst!r} — expected 10 digits + TQ + 4 digits "
            f"(e.g. 1234567890TQ0001)"
        )

    return errors


# ── QBO payload builder ──────────────────────────────────────────

def _build_qbo_payload(inp: OnboardingInput) -> dict:
    return {
        "DisplayName": inp.get("client_name", ""),
        "CompanyName": inp.get("client_name", ""),
        "PrimaryEmailAddr": {"Address": inp.get("contact_email", "")},
        "BillAddr": {"Line1": inp.get("address", "")},
        "CurrencyRef": {"value": "CAD"},
        "FiscalYearEnd": inp.get("fiscal_year_end", ""),
        "Taxable": True,
        "TaxExemptionReasonId": None,
    }


# ── Mock output writer ───────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert client name to a safe filename slug."""
    slug = name.lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug[:40]


def _write_onboarding_output(draft: OnboardingDraft) -> None:
    """Write onboarding draft to hitl_emails/ (mock mode)."""
    os.makedirs(ONBOARDING_EMAILS_DIR, exist_ok=True)
    slug = _slugify(draft["client_name"])
    filename = f"{ONBOARDING_EMAILS_DIR}/onboarding_{slug}.json"

    payload = {
        "type": "onboarding_draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "draft": {
            "client_name": draft["client_name"],
            "status": draft["status"],
            "escalation_level": draft["escalation_level"],
            "validation_errors": draft["validation_errors"],
            "qbo_customer_payload": draft["qbo_customer_payload"],
        },
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        f"[onboarding_node] Draft written → {filename} "
        f"({draft['status']}, {draft['escalation_level']})"
    )


# ── Main node ────────────────────────────────────────────────────

def onboarding_node(state: AccountingAgentsState) -> dict:
    """
    Onboarding Agent node. Validates and drafts a new QBO client record.
    Returns delta only — never the full state.
    Both N2 (notify) and N4 (transfer) route to hitl.
    """
    error_log = list(state.get("error_log", []))

    raw_input = state.get("onboarding_input")
    if raw_input is None:
        onboarding_input = _default_onboarding_input()
        print("[onboarding_node] No onboarding_input in state — using fixture.")
    else:
        onboarding_input = raw_input

    validation_errors = _validate_onboarding_input(onboarding_input)
    qbo_payload = _build_qbo_payload(onboarding_input)

    if validation_errors:
        escalation_level = "N4"
        status = "validation_failed"
    else:
        escalation_level = "N2"
        status = "draft_ready"

    draft = OnboardingDraft(
        client_name=onboarding_input["client_name"],
        qbo_customer_payload=qbo_payload,
        validation_errors=validation_errors,
        escalation_level=escalation_level,
        status=status,
    )

    onboarding_mode = os.getenv("ONBOARDING_MODE", "mock")
    if onboarding_mode == "mock":
        _write_onboarding_output(draft)
    elif onboarding_mode == "mcp":
        raise NotImplementedError("ONBOARDING_MODE=mcp not implemented yet — Phase 4+")

    print(
        f"[onboarding_node] {onboarding_input['client_name']!r} → "
        f"{status} ({escalation_level})"
        + (f" | errors: {len(validation_errors)}" if validation_errors else "")
    )

    return {
        "onboarding_draft": draft,
        "routing_signal": "hitl_pending",
        "hitl_pending": True,
        "error_log": error_log,
    }
