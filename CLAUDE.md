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
✅ accounting_agents/state.py — SharedState validated
✅ .venv + requirements.txt — venv OK (+ langgraph-checkpoint-sqlite)
✅ .gitignore
✅ accounting_agents/routing.py — 10/10 tests passed
✅ accounting_agents/nodes/__init__.py
✅ accounting_agents/nodes/ingestion.py — stub
✅ accounting_agents/nodes/reconciliation.py — stub
✅ accounting_agents/nodes/hitl.py — stub
✅ accounting_agents/graph.py — 5 nodes compiled and validated
⬜ accounting_agents/webhook.py
