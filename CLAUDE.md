# AccountingAgents — Claude Code Context

## Project
Open-source multi-agent LLM framework modelled on an accounting firm.
Stack: LangGraph, MCP-native, Python, TypedDict SharedState.
License: Apache 2.0
Repo: https://github.com/pdesrochers01/accounting-agents
Author: Paul Desrochers, Independent Researcher, Quebec, Canada

## MVP Scope (Phase 1)
- 3 active agents: Supervisor, Ingestion Agent, Reconciliation Agent
- SharedState: accounting_agents/state.py
- HITL cycle: interrupt() → Gmail notification → webhook → resume
- MCP: QBO MCP + Gmail MCP
- Test data: fictional Quebec firm (CAD, GST/HST)
- Key milestone: full HITL demo on mobile

## File Structure
accounting_agents/
  state.py          → SharedState TypedDict          ✅
  routing.py        → conditional routing functions  ⬜
  graph.py          → LangGraph StateGraph           ⬜
  nodes/
    __init__.py                                       ⬜
    ingestion.py    → Ingestion Agent stub            ⬜
    reconciliation.py → Reconciliation Agent stub     ⬜
    hitl.py         → HITL node stub                  ⬜
  webhook.py        → Flask HITL webhook              ⬜
docs/
  use-cases/
    README.md                                         ✅
    UC01-document-ingestion.md                        ✅
    UC02-reconciliation-gap.md                        ✅
    UC03-hitl-cycle.md                                ✅

## Use Cases (MVP)
- UC01: Ingestion Agent classifies incoming Gmail attachment → writes
        documents_ingested + routing_signal to SharedState
- UC02: Reconciliation Agent matches QBO transactions vs bank statement
        → detects gaps → triggers HITL if gap > $2,000 CAD (N3)
- UC03: Supervisor calls interrupt() → Gmail notification with
        Approve/Modify/Block links → accountant clicks on iPhone →
        webhook resumes thread

## SharedState Key Fields
- documents_ingested: list[IngestedDocument]
- routing_signal: "to_reconciliation" | "unrecognized" |
                  "nothing_to_reconcile" | "hitl_pending" | "completed"
- reconciliation_gaps: list[ReconciliationGap]
- hitl_pending: bool
- hitl_decision: "approve" | "modify" | "block" | "timeout"
- hitl_comment: Optional[str]
- thread_id: str
- timeout_at: Optional[datetime]
- error_log: list[str]

## HITL Escalation Levels
- N1: automatic (gap < $500 CAD)
- N2: notify only
- N3: approve required (gap > $2,000 CAD) ← MVP focus
- N4: transfer to human (unrecognized document, timeout)

## Conventions
- Always use .venv/bin/python (never bare python or python3)
- Each agent node returns a delta only — never the full state
- routing_signal drives all conditional edges
- Stubs first, real MCP integration in Phase 2
- All code and comments in English
- Tests after every file created

## Dependencies (requirements.txt)
langgraph>=0.2.0
langchain-anthropic>=0.1.0
mcp>=1.0.0
flask>=3.0.0
python-dotenv>=1.0.0

## Current Session Progress
✅ docs/use-cases/ — UC01, UC02, UC03 (English)
✅ accounting_agents/__init__.py
✅ accounting_agents/state.py — input_document field added
✅ .venv + requirements.txt — venv OK (+ langgraph-checkpoint-sqlite)
✅ .gitignore
✅ accounting_agents/routing.py — 10/10 tests passed
✅ accounting_agents/nodes/__init__.py
✅ accounting_agents/nodes/ingestion.py — real, 9/9 tests passed
✅ accounting_agents/nodes/reconciliation.py — real, 2/2 tests passed
✅ accounting_agents/nodes/hitl.py — real, full cycle tested
✅ accounting_agents/graph.py — 5 nodes compiled and validated
✅ accounting_agents/webhook.py — port 5001, host 0.0.0.0
✅ tests/test_end_to_end_stubs.py — passed
✅ tests/fixtures/ — 3 scenarios validated
✅ tests/test_reconciliation.py — 2/2 passed
✅ tests/test_hitl.py — full HITL cycle passed
✅ tests/test_ingestion.py — 9/9 passed
✅ tests/test_end_to_end_real.py — 3/3 passed
✅ scripts/demo_hitl.py — live HITL demo validated on iPhone
✅ hitl_emails/ — mock email output
✅ .env + .env.example — HITL_MODE=mock, port 5001
✅ ngrok 3.38.0 — tunnel validated on port 5001
✅ README.md — updated (MVP status, Quick Start, Roadmap)
✅ docs/architecture.md — 122 lines
✅ docs/development-setup.md — 121 lines

## Phase 2 — Next Steps
⬜ Gmail MCP real integration
⬜ QBO MCP real integration
⬜ FastAPI webhook + Pydantic validation
⬜ LLM-based document classification (Ingestion Agent)
⬜ AR Agent + AP Agent + Reporting Agent

## MVP Status
🎉 COMPLETE — Full HITL cycle validated on mobile (iPhone)
   thread_id: de147f32-d16c-4ec8-9775-0ec9f60e3f41
   decision: approve
   timestamp: 2026-04-23T20:06:40

## Design Decisions
- Webhook: Flask (MVP) → FastAPI migration planned for Phase 2
  (async native + Pydantic validation + Swagger docs)
- Classification: keyword matching (MVP) → LLM call planned for Phase 2
- HITL notification: mock email to hitl_emails/ (MVP) → Gmail MCP Phase 2
- Diagrams (docs/flowchart-macro.html, docs/langgraph-hitl-gmail.html):
  represent full Phase 2+ vision, not current MVP state

## Known Fixes
- sqlite3.connect() requires check_same_thread=False everywhere
- Amount regex: decimal mandatory (\.\d{2}) to avoid matching
  integers in document numbers (e.g. INV-4524)
- "modify" HITL path: reconciliation_node checks hitl_comment →
  returns "completed" immediately (prevents infinite loop)
- macOS port 5000 conflict with AirPlay Receiver → use port 5001
- Flask requires host='0.0.0.0' for ngrok tunnel to reach it
- ngrok browser warning on free plan → click "Visit Site" once
