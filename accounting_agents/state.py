from typing import TypedDict, Optional, Literal, Any
from datetime import datetime


# --- Enums ---

RoutingSignal = Literal[
    "to_reconciliation",    # UC01 → UC02
    "unrecognized",         # UC01 alt: unclassifiable document → N4
    "nothing_to_reconcile", # UC02 alt: no pending transactions
    "hitl_pending",         # UC02 → UC03
    "completed",            # cycle completed cleanly
]

HitlDecision = Literal[
    "approve",
    "modify",
    "block",
    "timeout",
]

EscalationLevel = Literal["N1", "N2", "N3", "N4"]

DocumentType = Literal[
    "supplier_invoice",
    "bank_statement",
    "receipt",
    "other",
]


# --- Sub-types ---

class IngestedDocument(TypedDict):
    document_id: str          # UUID generated at ingestion
    document_type: DocumentType
    date: str                 # ISO 8601
    amount: float             # CAD
    currency: str             # "CAD" for MVP
    vendor_or_client: str
    document_number: str
    qbo_entry_id: str         # ID returned by QBO MCP after creation
    source_email_id: str      # Gmail message ID (source)


class ReconciliationGap(TypedDict):
    gap_id: str               # UUID
    document_id: str          # reference to IngestedDocument
    transaction_id: str       # QBO ID of unmatched transaction
    expected_amount: float    # expected amount (CAD)
    actual_amount: float      # actual amount found (CAD)
    delta: float              # actual - expected
    date_expected: str        # ISO 8601
    date_actual: str          # ISO 8601
    vendor_or_client: str
    escalation_level: EscalationLevel  # N1 if delta < 500, N3 if delta > 2000


# --- Main SharedState ---

class AccountingAgentsState(TypedDict):

    # ── Input document (UC01) ─────────────────────────────────────
    input_document: Optional[dict]
    # Raw incoming document injected before graph.invoke().
    # Written by: test harness (MVP) / Gmail MCP (Phase 2)
    # Read by: Ingestion Agent
    # Fields: raw_text, source_email_id, filename

    # ── Ingestion (UC01) ──────────────────────────────────────────
    documents_ingested: list[IngestedDocument]
    # Documents processed in this cycle.
    # Written by: Ingestion Agent
    # Read by: Reconciliation Agent, Supervisor

    # ── Routing (UC01, UC02) ──────────────────────────────────────
    routing_signal: Optional[RoutingSignal]
    # Routing signal emitted by the current agent.
    # Written by: Ingestion Agent, Reconciliation Agent
    # Read by: Supervisor (conditional routing)

    # ── Reconciliation (UC02) ─────────────────────────────────────
    reconciliation_gaps: list[ReconciliationGap]
    # Gaps detected during reconciliation.
    # Written by: Reconciliation Agent
    # Read by: Supervisor, HITL notifier

    # ── HITL (UC03) ───────────────────────────────────────────────
    hitl_pending: bool
    # True if an interrupt() is awaiting human decision.
    # Written by: Reconciliation Agent (set True), Webhook (set False)
    # Read by: Supervisor

    hitl_decision: Optional[HitlDecision]
    # Decision received via webhook after mobile approval.
    # Written by: FastAPI Webhook
    # Read by: Supervisor (post-HITL routing)

    hitl_comment: Optional[str]
    # Optional accountant comment ("modify" decision only).
    # Written by: FastAPI Webhook
    # Read by: Reconciliation Agent (re-route with constraint)

    thread_id: str
    # LangGraph thread ID — required for post-interrupt() resumption.
    # Written by: Supervisor at initialization
    # Read by: FastAPI Webhook, SqliteSaver

    timeout_at: Optional[datetime]
    # HITL expiration timestamp (now + 4h).
    # Written by: Supervisor at interrupt()
    # Read by: Timeout handler

    # ── Errors & audit (all UCs) ──────────────────────────────────
    error_log: list[str]
    # Non-fatal errors accumulated during the cycle.
    # Written by: all agents
    # Read by: Supervisor


# --- Initial state ---

def initial_state(thread_id: str) -> AccountingAgentsState:
    """Return a clean initial state for a new cycle."""
    return AccountingAgentsState(
        input_document=None,
        documents_ingested=[],
        routing_signal=None,
        reconciliation_gaps=[],
        hitl_pending=False,
        hitl_decision=None,
        hitl_comment=None,
        thread_id=thread_id,
        timeout_at=None,
        error_log=[],
    )
