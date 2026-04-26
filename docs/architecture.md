# AccountingAgents — Technical Architecture

## Overview

AccountingAgents is a LangGraph StateGraph where all inter-agent
communication flows exclusively through a typed SharedState (TypedDict).
No agent calls another agent directly.

## Graph Structure

```
START
  │
  ▼
ingestion_node
  │
  ▼ route_after_ingestion(routing_signal)
  ├── "to_reconciliation" ──► reconciliation_node
  │                               │
  │                               ▼ route_after_reconciliation(routing_signal)
  │                               ├── "completed" ──────────────► END
  │                               ├── "nothing_to_reconcile" ──► END
  │                               └── "hitl_pending" ──► hitl_node
  │                                                           │
  │                                                     interrupt()
  │                                                           │
  │                                                     webhook resume
  │                                                           │
  │                                           route_after_hitl(hitl_decision)
  │                                               ├── "approve" ──► END
  │                                               ├── "block" ────► END
  │                                               ├── "timeout" ──► END
  │                                               └── "modify" ───► reconciliation_node
  │
  └── "unrecognized" ──► END (N4 escalation logged)
```

## SharedState Fields

| Field | Type | Written by | Read by |
|---|---|---|---|
| `input_document` | `Optional[dict]` | test harness / Gmail MCP (Phase 2) | Ingestion Agent |
| `documents_ingested` | `list[IngestedDocument]` | Ingestion Agent | Reconciliation Agent |
| `routing_signal` | `RoutingSignal` | Ingestion, Reconciliation | Supervisor (routing) |
| `reconciliation_gaps` | `list[ReconciliationGap]` | Reconciliation Agent | HITL node, Supervisor |
| `hitl_pending` | `bool` | Reconciliation (True), Webhook (False) | Supervisor |
| `hitl_decision` | `Optional[HitlDecision]` | FastAPI Webhook | Supervisor, HITL node |
| `hitl_comment` | `Optional[str]` | FastAPI Webhook | Reconciliation Agent |
| `thread_id` | `str` | Supervisor at init | Webhook, SqliteSaver |
| `timeout_at` | `Optional[datetime]` | HITL node | Timeout handler |
| `error_log` | `list[str]` | All agents | Supervisor |

## Escalation Levels

| Level | Threshold | Routing |
|---|---|---|
| N1 | gap < $500 CAD | `completed` → END |
| N2 | $500–$2,000 CAD | `completed` → END (Phase 2: notify) |
| N3 | gap > $2,000 CAD | `hitl_pending` → HITL node |
| N4 | unrecognized / timeout | `unrecognized` → END + alert |

## Agent Responsibilities

### Ingestion Agent (`nodes/ingestion.py`)
- Reads `input_document` from SharedState
- Hybrid classifier: keyword pre-filter (free, offline) → Pydantic AI
  Agent (LLM) on ambiguous documents. LLM-agnostic via model string
  in .env (Anthropic, OpenAI, Ollama). CLASSIFICATION_MODE=llm|keyword.
- Extracts: amount, date, vendor, document number
- Writes: `documents_ingested`, `routing_signal`
- Phase 2: Gmail MCP polling ✅ + LLM classification ✅

### Reconciliation Agent (`nodes/reconciliation.py`)
- Reads `documents_ingested` from SharedState
- Matches QBO transactions vs bank statement (vendor + date ±3 days)
- Detects gaps, assigns escalation level
- Writes: `reconciliation_gaps`, `routing_signal`, `hitl_pending`
- If `hitl_comment` present: human override → returns `completed`
- Phase 2: QBO MCP real integration

### HITL Node (`nodes/hitl.py`)
- Phase A (first entry): builds email, sends notification, calls `interrupt()`
- Phase B (after resume): reads `hitl_decision`, clears `hitl_pending`
- Detection: `hitl_decision is not None` → Phase B
- Mock mode: writes email to `hitl_emails/` (set `HITL_MODE=mock` in `.env`)
- Phase 2: Gmail MCP real send

### Supervisor (LangGraph routing)
- Implemented as conditional edges, not a node
- `route_after_ingestion()` — reads `routing_signal`
- `route_after_reconciliation()` — reads `routing_signal`
- `route_after_hitl()` — reads `hitl_decision`

## Persistence

SqliteSaver is used as the LangGraph checkpointer.
- Dev: in-memory SQLite (tests) or `accounting_agents.db` (demo)
- All connections require `check_same_thread=False`
- Thread state persists across `interrupt()` / webhook resume

## HITL Webhook

FastAPI + uvicorn (`webhook.py`) running on port 5001.
- `GET /health` — health check
- `GET /webhook?thread_id=X&decision=Y&comment=Z` — resume thread
- `decision` validated as `Literal["approve","modify","block"]` — 422 on invalid input
- Dev tunnel: ngrok (`ngrok http 5001`)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HITL_MODE` | `mock` | `mock` writes to `hitl_emails/`, `gmail` sends via Gmail MCP |
| `HITL_WEBHOOK_BASE_URL` | `http://localhost:5001` | Base URL for action links in emails |
| `HITL_NOTIFY_EMAIL` | `accountant@example.com` | Recipient of HITL notifications |

## Known Issues / Design Decisions

- Port 5001 used (macOS AirPlay Receiver occupies 5000)
- Amount regex requires mandatory decimal (`\.\d{2}`) to avoid
  false matches on document numbers (e.g. INV-4524)
- "modify" path: Reconciliation Agent checks `hitl_comment` and
  returns `completed` immediately to prevent infinite loop
- FastAPI + uvicorn (Phase 2) — migrated from Flask (MVP)
