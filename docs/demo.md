# AccountingAgents — Demo Guide

## Overview

| Field | Value |
|---|---|
| **Firm** | Lafleur CPA Firm, Montreal |
| **Client** | Entreprises Beaumont Inc. |
| **Task** | Bank reconciliation March 2026 |
| **Persona** | Marie Cardin, Senior Partner |

---

## Prerequisites

Before running the demo, three terminals must be active:

| Terminal | Command | Purpose |
|---|---|---|
| Terminal 1 | `PYTHONPATH=. .venv/bin/python accounting_agents/webhook.py` | Flask HITL webhook on port 5001 |
| Terminal 2 | `ngrok http 5001` | Public tunnel for iPhone webhook delivery |
| Terminal 3 | `PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py` | Demo script |

Also required:
- iPhone with Gmail inbox open (logged in as `HITL_NOTIFY_EMAIL`)
- `.env` configured: `HITL_MODE=gmail`, `QBO_MODE=mcp`, `HITL_WEBHOOK_BASE_URL` set to current ngrok URL
- `token.json` and `qbo_token.json` present at repo root

---

## Running the Demo

**Full demo** (requires Flask + ngrok):
```bash
PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py
```

**Dry-run** (Acts 1–3 only — no Gmail sent, no graph executed):
```bash
PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py --dry-run
```

Expected duration: ~2 minutes (from script start to iPhone approval).

---

## Act-by-Act Narrative

### ACT 1 — Document Detection `[Ingestion Agent]`

**What the audience sees:**
Gmail surveillance active on `pdesrochers01@gmail.com`. A new email arrives from `services.bancaires@bnc.ca` with a PDF attachment (`releve_bnq_mars2026.pdf`). The Ingestion Agent classifies it as `bank_statement` for client Entreprises Beaumont Inc., period March 2026, currency CAD.

**Agent responsible:** Ingestion Agent (`accounting_agents/nodes/ingestion.py`)

**Under the hood:**
The `input_document` dict is injected directly into `SharedState`. The Ingestion Agent's `_classify()` function runs keyword matching against the raw text, sets `document_type = "bank_statement"`, and writes a delta back to `SharedState` via `documents_ingested`.

**Talking point for presenter:**
> "In production, Gmail MCP monitors the inbox continuously. The moment a bank statement arrives, the agent wakes up automatically — no polling, no manual trigger."

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

**Agent responsible:** HITL Node + Flask Webhook (`accounting_agents/webhook.py`)

**Under the hood:**
The demo script polls `graph.get_state(config)` directly from the SQLite checkpointer every second — it does not call Flask. This makes it immune to Flask auto-reloader restarts. When the accountant taps a link on their iPhone, the ngrok tunnel delivers the GET request to Flask, which calls `graph.update_state()` and resumes the thread. The next poll in Act 5 picks up the `hitl_decision` value and exits the wait loop.

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
> "From email arrival to approved reconciliation: under 2 minutes. The same workflow manually takes an accountant 1–2 hours. That's the ROI in a single reconciliation cycle — and this is just one of seven agents."

---

## Key Messages

1. **MCP-native** — All external tool access goes through official MCP servers (Gmail, QuickBooks). No fragile custom wrappers. Easily swappable as new MCP servers emerge.

2. **Async HITL** — Human approval is woven into the workflow architecture, not bolted on. The graph cannot proceed past an N3 threshold without an explicit human decision.

3. **Mobile-first** — The accountant approves from any device, any location, with a single tap. No VPN, no console, no desktop software required.

4. **Fiduciary compliance** — The four-level escalation model (N1–N4) maps directly to accounting firm risk protocols. N3 and N4 decisions are always human-gated.

5. **Open source** — Apache 2.0 licensed. No vendor lock-in. Extensible architecture — swap QBO for Xero, swap Flask for FastAPI, add agents without touching shared state.

---

## Phase 2 — Next Steps (for investor discussion)

| Feature | Description | Status |
|---|---|---|
| FastAPI webhook | Replace Flask — async native, Pydantic v2 validation, Swagger docs | Planned |
| LLM classification | Replace keyword matching in Ingestion Agent with Claude API call | Planned |
| AR Agent | Automated overdue invoice follow-up and escalation | Planned |
| AP Agent | Vendor payment approval with N3 HITL gate | Planned |
| Reporting Agent | P&L, cash flow, compliance deadline monitoring | Planned |
