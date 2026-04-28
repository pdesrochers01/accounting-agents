# Architecture — AccountingAgents

## LangGraph StateGraph (9 nodes)

```
start
│
▼
ingestion ──────────────────────────────────────────────────────┐
│ routing_signal                                                 │
├── "to_reconciliation" ──► reconciliation ──► hitl ──► END     │
├── "to_ap"             ──► ap             ──► hitl ──► END     │
├── "to_ar"             ──► ar             ──► hitl ──► END     │
├── "to_reporting"      ──► reporting      ──► hitl ──► END     │
├── "to_compliance"     ──► compliance     ──► hitl ──► END     │
├── "to_onboarding"     ──► onboarding     ──► hitl ──► END     │
├── "unrecognized"      ──► hitl ──► END                        │
└── "nothing_to_reconcile" ──► END                              │
                                                                 │
hitl resume: hitl_decision ─────────────────────────────────────┘
├── "approve" ──► END
├── "modify"  ──► END
├── "block"   ──► END
└── "timeout" ──► END
```

## SharedState Fields

| Field                | Type                          | Written by     |
|----------------------|-------------------------------|----------------|
| input_document       | Optional[dict]                | caller         |
| documents_ingested   | list[IngestedDocument]        | ingestion      |
| routing_signal       | str                           | all agents     |
| reconciliation_gaps  | list[ReconciliationGap]       | reconciliation |
| hitl_pending         | bool                          | all agents     |
| hitl_decision        | Optional[str]                 | webhook        |
| hitl_comment         | Optional[str]                 | webhook        |
| thread_id            | str                           | caller         |
| timeout_at           | Optional[datetime]            | hitl           |
| ap_actions           | list[APAction]                | ap             |
| ar_invoices          | Optional[list[dict]]          | caller         |
| ar_actions           | list[ARAction]                | ar             |
| reporting_input      | Optional[dict]                | caller         |
| report_data          | Optional[dict]                | reporting      |
| report_sent          | bool                          | reporting      |
| compliance_input     | Optional[ComplianceInput]     | caller         |
| compliance_results   | list[ComplianceItem]          | compliance     |
| onboarding_input     | Optional[OnboardingInput]     | caller         |
| onboarding_draft     | Optional[OnboardingDraft]     | onboarding     |
| error_log            | list[str]                     | all agents     |

## HITL Escalation Model

The four-level escalation model applies uniformly across all 7 agents:

| Level | Mode           | Trigger                           | Example                                    |
|-------|----------------|-----------------------------------|--------------------------------------------|
| N1    | Automatic      | Routine, low-risk action          | First AR reminder, vendor bill < $500      |
| N2    | Notify only    | Action taken; cancellable         | Invoice created, client profile drafted    |
| N3    | Approve (HITL) | High-value or irreversible action | AR > $5k, reconciliation gap > $2k         |
| N4    | Transfer       | Outside known rules               | Dispute, invalid data, unrecognized vendor |

## Agent Responsibilities

### Ingestion Agent
- Classifies incoming financial documents (hybrid keyword + Pydantic AI LLM)
- Emits routing_signal to direct state to the correct downstream agent
- Modes: CLASSIFICATION_MODE=keyword (default) | llm

### Reconciliation Agent
- Matches QBO transactions vs. bank statement
- Detects gaps and classifies by amount (N1/N3)
- Modes: QBO_MODE=mock (default) | mcp

### AP Agent
- Processes vendor bills: auto-approve (N1), queue (N2), HITL (N3)
- Detects duplicates and unknown vendors (N4)
- Modes: AP_MODE=mock (default) | mcp

### AR Agent
- Monitors overdue invoices: auto-remind (N1), second reminder (N2), HITL (N3)
- Handles disputed invoices (N4)
- Modes: AR_MODE=mock (default) | mcp

### Reporting Agent
- Generates P&L, cash flow, AR aging reports
- Anomaly detection: revenue drop (N3), negative cash flow (N3),
  expense spike (N2), AR aging (N2), data integrity (N4)
- Modes: REPORTING_MODE=mock (default) | mcp

### Compliance Agent
- Monitors fiscal deadlines: GST/HST, QST, payroll, corporate tax, T4, RL-1
- Supports QC and CA (federal) jurisdictions
- Classifies by days_remaining: ok (N1), upcoming (N2), urgent (N3), overdue (N4)
- Modes: COMPLIANCE_MODE=mock (default) | mcp

### Onboarding Agent
- Creates and validates new client profiles (NEQ, GST, QST validation)
- Always routes to HITL — QBO writes require explicit accountant approval
- N2 (draft ready) → mandatory N3 gate before any QBO write
- N4 on missing mandatory fields or invalid identifiers
- Modes: ONBOARDING_MODE=mock (default) | mcp

### Supervisor
Implemented as deterministic routing functions (no LLM call):
- route_after_ingestion()
- route_after_reconciliation()
- route_after_hitl()
- route_after_ap()
- route_after_ar()
- route_after_reporting()
- route_after_compliance()
- route_after_onboarding()

### HITL Notifier
- Suspends thread via LangGraph interrupt()
- Sends Gmail notification with Approve/Modify/Block links
- Resumes on webhook GET /webhook?decision=approve|modify|block
- 4-hour timeout with automatic N4 escalation
- Modes: HITL_MODE=mock (default) | gmail

## MCP Integrations

| MCP Server        | Status  | Used by                                       |
|-------------------|---------|-----------------------------------------------|
| Gmail MCP         | ✅ Active | Ingestion, HITL, AR, AP, Onboarding          |
| QuickBooks Online | ✅ Active | Reconciliation, AP, AR, Reporting, Onboarding |
| Google Calendar   | Planned | Compliance                                    |
| Google Drive      | Planned | Reconciliation (bank statements)              |
| Zapier MCP        | Planned | General-purpose bridge                        |

## Environment Variables

| Variable              | Values                 | Default | Used by        |
|-----------------------|------------------------|---------|----------------|
| HITL_MODE             | mock \| gmail          | mock    | hitl           |
| HITL_NOTIFY_EMAIL     | email address          | —       | hitl           |
| HITL_WEBHOOK_BASE_URL | https://...            | —       | hitl           |
| QBO_MODE              | mock \| mcp            | mock    | reconciliation |
| QBO_MCP_SERVER_PATH   | path to MCP server     | —       | reconciliation |
| AP_MODE               | mock \| mcp            | mock    | ap             |
| AR_MODE               | mock \| mcp            | mock    | ar             |
| REPORTING_MODE        | mock \| mcp            | mock    | reporting      |
| COMPLIANCE_MODE       | mock \| mcp            | mock    | compliance     |
| ONBOARDING_MODE       | mock \| mcp            | mock    | onboarding     |
| CLASSIFICATION_MODE   | keyword \| llm         | keyword | ingestion      |
| CLASSIFICATION_MODEL  | anthropic model string | —       | ingestion      |

## Webhook

FastAPI + uvicorn, port 5001.

Routes:
- `GET /webhook?decision=approve|modify|block&thread_id=...&comment=...`
- `GET /health`

Pydantic Literal validation on `decision` parameter — 422 auto on invalid input.

## Persistence

SqliteSaver is used as the LangGraph checkpointer.
- Dev: in-memory SQLite (tests) or `accounting_agents.db` (demo)
- All connections require `check_same_thread=False`
- Thread state persists across `interrupt()` / webhook resume

## Known Issues / Design Decisions

- Port 5001 used (macOS AirPlay Receiver occupies 5000)
- Amount regex requires mandatory decimal (`\.\d{2}`) to avoid
  false matches on document numbers (e.g. INV-4524)
- "modify" path: Reconciliation Agent checks `hitl_comment` and
  returns `completed` immediately to prevent infinite loop
- FastAPI + uvicorn (Phase 2) — migrated from Flask (MVP)
