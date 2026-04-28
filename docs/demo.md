# AccountingAgents — Demo Guide

## Overview

| Field | Value |
|---|---|
| **Firm** | Lafleur CPA Firm, Montreal |
| **Client** | Entreprises Beaumont Inc. |
| **Task** | Bank reconciliation March 2026 |
| **Persona** | Marie Lafleur, Director of Operations |

---

## Prerequisites

Before running the demo, three terminals must be active:

| Terminal | Command | Purpose |
|---|---|---|
| Terminal 1 | `PYTHONPATH=. .venv/bin/python accounting_agents/webhook.py` | FastAPI HITL webhook on port 5001 |
| Terminal 2 | `ngrok http 5001` | Public tunnel for iPhone webhook delivery |
| Terminal 3 | `PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py` | Demo script |

Also required:
- iPhone with Gmail inbox open (logged in as `HITL_NOTIFY_EMAIL`)
- `.env` configured: `HITL_MODE=gmail`, `QBO_MODE=mcp`, `HITL_WEBHOOK_BASE_URL` set to current ngrok URL
- `token.json` and `qbo_token.json` present at repo root

---

## Running the Demo

**Full demo** (requires FastAPI server + ngrok):
```bash
PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py
```

---

## Act-by-Act Narrative

### ACT 1 — Document Detection `[Ingestion Agent]`

**What the audience sees:**
Gmail surveillance active on `pdesrochers01@gmail.com`. A new email arrives from `services.bancaires@bnc.ca` with a PDF attachment (`releve_bnq_mars2026.pdf`). The Ingestion Agent classifies it as `bank_statement` for client Entreprises Beaumont Inc., period March 2026, currency CAD.

**Agent responsible:** Ingestion Agent (`accounting_agents/nodes/ingestion.py`)

**Under the hood:**
The `input_document` dict is injected directly into `SharedState`. The Ingestion Agent's `_classify()` function uses a hybrid classifier: keyword pre-filter on clear documents (free, offline), Pydantic AI Agent (LLM) on ambiguous documents. LLM-agnostic: switch model via `CLASSIFICATION_MODEL` in `.env`. Sets `document_type = "bank_statement"` and writes a delta back to `SharedState` via `documents_ingested`.

**Talking point for presenter:**
> "In production, Gmail MCP monitors the inbox continuously. The moment a bank statement arrives, the agent wakes up automatically — no polling, no manual trigger. Classification uses a hybrid approach: a fast keyword pre-filter handles clear documents offline, and a Pydantic AI Agent backed by Claude handles ambiguous ones — enabling context-aware classification of any financial document regardless of format or language."

---

### ACT 2 — QuickBooks Query `[Reconciliation Agent]`

**What the audience sees:**
A spinner while the Reconciliation Agent queries QuickBooks Online. Then a rich table showing all fetched bills — vendor name, amount, currency, and date. CAD bills are highlighted; foreign-currency bills are dimmed and excluded.

**Agent responsible:** Reconciliation Agent (`accounting_agents/nodes/reconciliation.py`)

**Under the hood:**
`_fetch_qbo_bills_mcp()` spawns the Intuit MCP server as a Node.js subprocess via `stdio_client`. It calls the `search_bills` tool and parses the JSON response line by line. Only CAD bills flow into the reconciliation logic. `NODE_NO_WARNINGS=1` suppresses the Node.js punycode deprecation warning from stderr.

Note: In this demo, the Intuit MCP server runs locally as a Node.js subprocess spawned automatically by `stdio_client` — no separate terminal required. In production, it would be deployed as a hosted service. Intuit and Anthropic announced a partnership in February 2026 that includes a hosted QBO MCP integration directly in Claude.ai — currently in rollout.

**Talking point for presenter:**
> "This is a live query to QuickBooks Online via the official Intuit MCP server — real data, real time. No custom API wrapper, no scraping. The same MCP protocol that any certified integration uses."

---

### ACT 3 — Gap Detection `[Reconciliation Agent]`

**What the audience sees:**
An animated line-by-line analysis of the BNC bank statement. Three vendors show a green checkmark (match). Hydro-Québec shows a bold red alert: bank says $4,900.00, QBO shows $2,450.00 — a $2,450.00 gap. A red panel confirms the N3 threshold is exceeded and human approval is mandatory.

**Agent responsible:** Reconciliation Agent (`accounting_agents/nodes/reconciliation.py`)

**Under the hood:**
`_compare_with_bank_statement()` converts QBO bills to the internal transaction format and runs `_match_transactions()`, which matches by vendor name and date (±3 days). The delta of $2,450.00 exceeds `N3_THRESHOLD` ($2,000 CAD), so `routing_signal` is set to `"hitl_pending"`.

**Talking point for presenter:**
> "The system doesn't just find the gap — it knows exactly which escalation level applies. N3 means human approval is mandatory before any action is taken. This is the fiduciary guarantee built into the architecture."

---

### ACT 4 — HITL Interrupt `[Supervisor + HITL Node]`

**What the audience sees:**
A yellow panel announces the graph interrupt. A spinner shows Gmail being sent to Marie Lafleur. Once sent, the thread ID is displayed and the demo transitions to Act 5.

**Agent responsible:** Supervisor (routing) + HITL Node (`accounting_agents/nodes/hitl.py`)

**Under the hood:**
`graph.invoke()` runs the full pipeline: ingestion node → reconciliation node → HITL node. The HITL node calls `_send_gmail()`, which sends a real email via Gmail OAuth2 with three action links: Approve, Modify, Block. Then LangGraph's `interrupt()` primitive suspends the thread — the graph state is checkpointed to SQLite and no further node executes until the webhook delivers a decision.

**Talking point for presenter:**
> "The graph is literally paused. The LangGraph thread is suspended in the SQLite checkpointer. No irreversible action can be taken without Marie Lafleur's explicit approval. This is the control plane for fiduciary compliance."

---

### ACT 5 — Awaiting Decision `[HITL Node + Webhook]`

**What the audience sees:**
A live timer counting up (MM:SS format) with a countdown to the 120-second timeout. The demo waits for the accountant to tap Approve, Modify, or Block on their iPhone.

**Agent responsible:** HITL Node + FastAPI Webhook (`accounting_agents/webhook.py`)

**Under the hood:**
The demo script polls `graph.get_state(config)` directly from the SQLite checkpointer every second — it does not call the FastAPI server. When the accountant taps a link on their iPhone, the ngrok tunnel delivers the GET request to the FastAPI server, which calls `graph.update_state()` and resumes the thread. The next poll in Act 5 picks up the `hitl_decision` value and exits the wait loop. uvicorn eliminates the auto-reloader issue present in the prior Flask implementation.

**Talking point for presenter:**
> "The accountant can approve from anywhere — office, home, or vacation. All they need is their phone. The architecture is mobile-first by design, not as an afterthought."

---

### ACT 6 — Resolution `[Supervisor]`

**What the audience sees:**
A decision panel showing the decision maker (Marie Lafleur), the decision (APPROVED / BLOCKED / MODIFIED), timestamp in UTC, and thread ID. A final green panel shows total elapsed time, the comparison to manual processing (~2 hours), and confirms the file has been submitted for audit.

**Agent responsible:** Supervisor (routing via `routing_signal = "completed"`)

**Under the hood:**
After `graph.update_state()` injects the `hitl_decision`, the graph resumes from the HITL node. The Supervisor evaluates `routing_signal` and routes to `__end__`. For "approve": reconciliation is accepted, file marked complete. For "block": file flagged for manual review. For "modify": `hitl_comment` is set; reconciliation node short-circuits to `"completed"` on the next tick (prevents re-escalation loop).

**Talking point for presenter:**
> "From email arrival to approved reconciliation: under 2 minutes."
>
> "Today each decision automatically triggers the appropriate accounting actions. For example:
> - **APPROVE** → QBO is updated automatically, an audit note is created in the client file, and the Reporting Agent refreshes the P&L.
> - **BLOCK** → the transaction is frozen in QBO, an investigation file is opened, and the Compliance Agent sends a regulatory alert if the amount exceeds the threshold.
>
> The same workflow manually takes an accountant 1–2 hours. That's the ROI in a single reconciliation cycle — and this is just one of seven agents."

---

## Key Messages

1. **MCP-native** — All external tool access goes through official MCP servers (Gmail, QuickBooks). No fragile custom wrappers. Easily swappable as new MCP servers emerge.

2. **Async HITL** — Human approval is woven into the workflow architecture, not bolted on. The graph cannot proceed past an N3 threshold without an explicit human decision.

3. **Mobile-first** — The accountant approves from any device, any location, with a single tap. No VPN, no console, no desktop software required.

4. **Fiduciary compliance** — The four-level escalation model (N1–N4) maps directly to accounting firm risk protocols. N3 and N4 decisions are always human-gated.

5. **Open source** — Apache 2.0 licensed. No vendor lock-in. Extensible architecture — swap QBO for Xero, swap agents without touching shared state.

---

## Security & Data Privacy

Data confidentiality is a critical non-functional requirement
for any CPA firm. AccountingAgents addresses this at every layer:

### Data in Transit
- All QBO API calls use OAuth 2.0 with short-lived access tokens
- Gmail notifications use OAuth 2.0 — no passwords stored
- ngrok tunnel uses HTTPS end-to-end

### Data at Rest
- LangGraph thread state persisted in local SQLite
  (never leaves the firm's infrastructure)
- OAuth tokens stored locally (token.json, qbo_token.json)
  excluded from version control (.gitignore)
- No client financial data sent to third-party services
  beyond QBO and Gmail (already trusted by the firm)

### Document Ingestion & Email Privacy
- Current demo: no client email is read by the agent —
  document ingestion is simulated (input_document injected
  directly into the graph)
- Gmail OAuth2 scope is limited to `gmail.send` only —
  the agent can send notifications but cannot read the
  firm's inbox
- Gmail read access will use `gmail.readonly` scope (read-only, no
  modification possible) when inbox monitoring is activated. The firm's
  data privacy policy will govern which emails the agent is authorized
  to process and for how long attachments are retained.

### Human Oversight & Audit Trail
- N1/N2/N3/N4 escalation model ensures no high-value action
  is taken without explicit human approval
- Full audit trail via LangGraph checkpointer —
  every decision is timestamped and traceable
- HITL decisions include decision maker identity,
  timestamp (UTC), and thread ID

### Talking Point for Presenter
> "Client financial data never leaves your infrastructure.
>  The agents orchestrate the workflow — they don't store
>  your clients' data."
>
> "Today, no client email is read by the agent — document
>  ingestion is simulated. In Phase 3, we will implement
>  Gmail read access with the minimum required scope, and
>  the firm's data privacy policy will govern which emails
>  the agent is authorized to process."

---

## Implementation Status

| Phase | Feature                               | Status  |
|-------|---------------------------------------|---------|
| 2     | Gmail MCP real integration            | ✅ Done |
| 2     | QBO MCP real integration              | ✅ Done |
| 2     | FastAPI webhook + Pydantic validation  | ✅ Done |
| 2     | LLM document classification           | ✅ Done |
| 3     | AR Agent                              | ✅ Done |
| 3     | AP Agent                              | ✅ Done |
| 3     | Reporting Agent                       | ✅ Done |
| 4     | Compliance Agent                      | ✅ Done |
| 4     | Onboarding Agent                      | ✅ Done |
