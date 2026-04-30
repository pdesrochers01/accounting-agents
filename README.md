# AccountingAgents

**A Multi-Agent LLM Framework for Accounting Firm Automation**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Status](https://img.shields.io/badge/status-Public%20--%20Preprint%20submitted%20to%20arXiv-blue)

---

## Overview

AccountingAgents is a novel multi-agent Large Language Model (LLM) framework inspired by the organizational structure of professional accounting firms. The paper is publicly available as a preprint submitted to arXiv (April 2026). Drawing a direct parallel to [TradingAgents](https://arxiv.org/abs/2412.20138) in financial trading, it defines specialized agent roles — Ingestion, Reconciliation, Reporting, Compliance, Accounts Receivable (AR), Accounts Payable (AP), and Onboarding — coordinated by a central Supervisor via a structured `SharedState`. Unlike existing commercial solutions (Intuit Assist, Pilot AI) that operate as closed, monolithic systems, AccountingAgents is MCP-native and open source (Apache 2.0), leveraging official Model Context Protocol servers as representative integrations. A key contribution is the design of an asynchronous Human-in-the-Loop (HITL) mechanism that suspends agent threads via LangGraph's `interrupt()` primitive, notifies the supervising accountant by email or instant message, and resumes execution upon webhook-delivered approval — enabling mobile, real-world oversight without a dedicated console.

---

## Key Features

- **Multi-agent architecture** — Seven specialized roles modelled on real accounting firm structure, coordinated by a hierarchical Supervisor via a typed `SharedState`
- **MCP-native integrations** — All external tool access is mediated through official Model Context Protocol servers; no fragile custom API wrappers
- **Reliable LLM responses** - Python TypedDict and Pydantic AI for structured state management and data validation — ensuring the reliability of LLM responses.
- **Asynchronous HITL mechanism** — LangGraph `interrupt()` + webhook resumption enables mobile approval from any device, with a 4-hour timeout and automatic escalation
- **Four-level escalation model** — Risk-calibrated routing from fully automated (N1) to human transfer (N4), aligned with accounting fiduciary obligations
- **Open-source** — Apache 2.0 licensed; targets small-to-medium accounting firms underserved by enterprise solutions

---

## Related Work

AccountingAgents builds on and extends the following works:

- TradingAgents (Xiao et al., 2025) — arXiv:2412.20138
- Ramachandran (2025) — Enterprise Finance & Accounting Automation, ResearchGate
- Barrak (2025) — Traceability and Accountability in Multi-Agent LLM Pipelines, arXiv:2510.07614

---

## Architecture Overview

| # | Agent | Goal | MCP Tools | MVP Scope |
|---|---|---|---|---|
| 1 | Ingestion Agent | Capture & classify incoming financial documents | Gmail MCP · QBO MCP · LLM | ✅ |
| 2 | Reconciliation Agent | Match transactions vs. bank statements; flag discrepancies | QBO MCP · Drive MCP | ✅ |
| 3 | AP Agent | Approve vendor bills and payments | QBO MCP · Gmail MCP | ✅ |
| 4 | AR Agent | Track overdue invoices; send collection reminders | QBO MCP · Gmail MCP | ✅ |
| 5 | Reporting Agent | Generate P&L, cash flow; detect anomalies | QBO MCP · Gmail MCP | ✅ |
| 6 | Compliance Agent | Monitor fiscal deadlines and regulatory obligations | QBO MCP · Calendar MCP | ✅ |
| 7 | Onboarding Agent | Create and validate new client profiles | QBO MCP · Gmail MCP | ✅ |
| 8 | Supervisor | Orchestrate state, routing, and error handling | LangGraph StateGraph · checkpointer | ✅ |
| 9 | HITL Notifier | Async approval via messaging; resume suspended thread | Gmail MCP · FastAPI · SqliteSaver | ✅ |

*Table 1: AccountingAgents role definitions.*

---

## HITL Escalation Model

Accounting operations carry fiduciary and legal obligations that preclude fully autonomous execution of high-stakes actions. The four-level escalation model routes decisions based on risk profile:

| Level | Mode | Trigger | Example |
|---|---|---|---|
| N1 | Automatic | Routine, low-risk action | First AR reminder, standard report, vendor bill < $500 |
| N2 | Notify only | Action taken; cancellable within window | Invoice created, client profile drafted, recurring AP payment |
| N3 | Approve (HITL) | High-value or irreversible action | AR escalation > $5k, reconciliation gap, vendor payment > $2k |
| N4 | Transfer | Outside known rules | Client dispute, regulatory anomaly, unrecognized vendor |

*Table 2: Four-level HITL escalation model.*

---

## MCP Integrations

All tool access is mediated through official MCP servers. The five servers in the MVP stack are:

| MCP Server | Status | Role |
|---|---|---|
| **Gmail MCP** | ✅ Active | Real OAuth2 sending via Gmail API; HITL_MODE=gmail; token.json at repo root |
| **QuickBooks Online MCP** | ✅ Active | Official Intuit MCP server (stdio); QBO_MODE=mcp; sandbox CA validated (139 tools) |
| **Google Drive MCP** | Planned | Financial document storage and retrieval |
| **Google Calendar MCP** | Planned | Fiscal deadline monitoring and scheduling |
| **Zapier MCP** | Planned | General-purpose bridge to services without a native MCP server |

Additional MCP servers can be substituted or added without modifying agent logic.

---

## Project Structure

```
accounting-agents/
├── accounting_agents/
│   ├── __init__.py
│   ├── state.py              # SharedState TypedDict
│   ├── graph.py              # LangGraph StateGraph (9 nodes)
│   ├── routing.py            # Conditional routing functions
│   ├── webhook.py            # FastAPI HITL webhook (port 5001)
│   └── nodes/
│       ├── ingestion.py      # Ingestion Agent (hybrid keyword + Pydantic AI LLM classification)
│       ├── reconciliation.py # Reconciliation Agent (gap detection)
│       ├── hitl.py           # HITL node — interrupt() + notification
│       ├── ap.py             # AP Agent (Phase 3)
│       ├── ar.py             # AR Agent (Phase 3)
│       ├── reporting.py      # Reporting Agent (Phase 3)
│       ├── compliance.py     # Compliance Agent (Phase 4)
│       └── onboarding.py     # Onboarding Agent (Phase 4)
├── docs/
│   ├── use-cases/            # UC01–UC08
│   ├── architecture.md       # System architecture reference
│   ├── development-setup.md  # Local dev setup guide
│   ├── demo.md               # Demo guide and talking points
│   ├── flowchart-macro.html  # Macro architecture diagram
│   └── langgraph-hitl-gmail.html # LangGraph HITL flow diagram
├── tests/
│   ├── fixtures/             # Fictional Quebec firm test data (CAD)
│   ├── test_ingestion.py     # 10/10 tests
│   ├── test_reconciliation.py # 2/2 tests
│   ├── test_hitl.py          # Full HITL cycle
│   ├── test_ap.py            # 7/7 tests
│   ├── test_ar.py            # 7/7 tests
│   ├── test_reporting.py     # 7/7 tests
│   ├── test_compliance.py    # 7/7 tests
│   ├── test_onboarding.py    # 7/7 tests
│   ├── test_end_to_end_real.py # 3/3 end-to-end tests
│   ├── test_qbo_mcp.py       # QBO MCP live integration test (QBO_MODE=mcp)
│   └── benchmark/            # 65-case deterministic benchmark
├── scripts/
│   ├── demo_end_to_end.py    # End-to-end narrative demo (Phase 2)
│   ├── demo_hitl.py          # Standalone HITL demo script
│   ├── generate_gmail_token.py  # Gmail OAuth2 token generator
│   ├── generate_qbo_token.py    # QBO OAuth2 token generator
│   ├── seed_qbo_sandbox.py      # Seeds QBO sandbox with test vendors + bills
│   └── cleanup_qbo_bills.py     # Removes duplicate bills from QBO sandbox
├── hitl_emails/              # Mock email output (dev)
├── paper/
│   └── accounting_agents_paper.pdf  # Preprint (April 2026)
├── requirements.txt
├── .env.example
├── CLAUDE.md                 # Claude Code persistent context
└── README.md
```

---

## Quick Start

**Prerequisites**
- Python 3.11+
- [ngrok](https://ngrok.com) (free account)
- macOS / Linux

**Installation**

```bash
# Clone
git clone https://github.com/pdesrochers01/accounting-agents.git
cd accounting-agents

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env — set HITL_NOTIFY_EMAIL and HITL_WEBHOOK_BASE_URL
```

**Phase 2 credentials** (required for live MCP paths)

- Gmail OAuth: place `client_secret.json` at repo root, then run
  `PYTHONPATH=. .venv/bin/python scripts/generate_gmail_token.py`
  to generate `token.json`. Set `HITL_MODE=gmail` in `.env`.
- QBO MCP: run `scripts/generate_qbo_token.py` to generate
  `qbo_token.json`. Set `QBO_MODE=mcp` and `QBO_MCP_SERVER_PATH`
  in `.env`. Both credential files are excluded from git.

**Run tests**

```bash
PYTHONPATH=. .venv/bin/python tests/test_end_to_end_real.py
```

**Run HITL demo** (requires ngrok)

```bash
# Terminal 1 — FastAPI webhook server
PYTHONPATH=. .venv/bin/python accounting_agents/webhook.py

# Terminal 2 — ngrok tunnel
ngrok http 5001

# Terminal 3 — demo script
PYTHONPATH=. .venv/bin/python scripts/demo_hitl.py
# Open the APPROVE link from any mobile device
```

---

## Demo

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py
```

See [docs/demo.md](docs/demo.md) for the complete demo guide including act-by-act narrative and presenter talking points.

### Pre-demo checklist

Run these before any live presentation:

```bash
# 1. Verify QBO — must show 6 CAD bills including Hydro-Québec $2,450.00
PYTHONPATH=. .venv/bin/python tests/test_qbo_mcp.py

# 2. Dry-run Acts 1-3 (no Gmail, no graph)
PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py --dry-run
```

**If test_qbo_mcp.py shows 0 bills** — QBO token expired (Intuit OAuth, ~100 day lifetime):
```bash
PYTHONPATH=. .venv/bin/python scripts/generate_qbo_token.py   # browser OAuth flow
PYTHONPATH=. .venv/bin/python tests/test_qbo_mcp.py           # verify 6 CAD bills
```

**If duplicate bills appear** (`12 bills` instead of `8`) — run cleanup without re-seeding:
```bash
PYTHONPATH=. .venv/bin/python scripts/cleanup_qbo_bills.py
```

**Gmail token** — expires every hour but auto-refreshes. If Gmail fails mid-demo, the script now shows a clear error with recovery instructions instead of silently reporting success.

---

## Roadmap

- [x] MVP implementation — Supervisor, Ingestion, Reconciliation, async HITL
- [x] SharedState TypedDict + LangGraph StateGraph
- [x] Async HITL cycle — interrupt() + FastAPI webhook + mobile approval
- [x] Test suite — 50+ tests (unit + end-to-end), 3 fixture scenarios
- [x] Gmail MCP real integration (Phase 2)
- [x] QBO MCP real integration (Phase 2)
- [x] FastAPI webhook + Pydantic validation (Phase 2)
- [x] LLM-based document classification (Phase 2, Pydantic AI)
- [x] AR Agent + AP Agent + Reporting Agent (Phase 3)
- [x] Compliance Agent + Onboarding Agent (Phase 4)
- [x] Experimental benchmark — 65 deterministic test cases,
      fully reproducible without API calls (tests/benchmark/)
      Results: Ingestion 83.3% | Reconciliation 100% | Overall 72.3%
- [ ] AP vendor registry — replace static KNOWN_VENDORS list
      with live QBO MCP list_vendors query (AP_MODE=mcp);
      mock mode to use enriched fixture vendor list
- [ ] Experimental validation paper (agent accuracy, HITL approval rates)
- [ ] Internationalization — translate fixture data, keyword rules,
      and benchmark datasets to English for broader open-source
      accessibility; keyword rules are currently French-only
      (multilingual support requires CLASSIFICATION_MODE=llm)
- [ ] Support for Xero, Sage, Microsoft Dynamics 365

### Production Readiness Roadmap

**Tier 1 — Production blockers (required before any deployment)**
- [ ] Webhook HMAC signature validation — prevent unauthorized
      /webhook?decision=approve calls
- [ ] Secrets management — replace .env with AWS Secrets Manager,
      HashiCorp Vault, or equivalent
- [ ] TLS + rate limiting on FastAPI webhook endpoint
- [ ] Immutable audit log — every agent action logged externally
      with: agent, action, client_id, amount, decision, timestamp
      (regulatory obligation in accounting — SharedState alone
      is insufficient)
- [ ] QBO write idempotence — duplicate Approve clicks must not
      create duplicate payments (most costly production bug)
- [ ] Retry logic + circuit breaker on all MCP calls (QBO, Gmail)

**Tier 2 — Important, deployable incrementally**
- [ ] Structured JSON logging → Datadog / CloudWatch / Grafana Loki
- [ ] Distributed tracing on LangGraph graphs (LangSmith or
      OpenTelemetry)
- [ ] Key metrics: latency per agent, HITL rate per level,
      timeout rate
- [ ] Multi-tenancy — thread and data isolation per client_id;
      SharedState partitioned by tenant (today: single-client only)
- [ ] GDPR — right to erasure per client, data residency policy,
      encryption at rest for SQLite checkpoints

**Tier 3 — Scaling and operations**
- [ ] SQLiteSaver → PostgresSaver (LangGraph) for multi-instance
      horizontal scaling
- [ ] Queue-based ingestion (SQS, Cloud Tasks) for volume spikes
- [ ] Alerting: N4 timeout unresolved, MCP error rate > threshold,
      webhook unreachable
- [ ] Canary deployments + shadow mode (run agents in parallel
      without acting, compare decisions)

**Accounting-specific requirements**
- [ ] SOC 2 Type II (if serving US clients)
- [ ] Document retention policy — 7-year retention (Canada)
- [ ] Segregation of duties — an agent must not both approve
      and execute the same action

**Recommended sprint sequence**

  Sprint 1: Webhook HMAC + secrets management + immutable audit log
  Sprint 2: Structured logging + MCP retry/circuit breaker
  Sprint 3: Multi-tenancy + GDPR
  Sprint 4: PostgresSaver + horizontal scaling
  Sprint 5: Full observability + alerting

---

## Citation

```bibtex
@misc{desrochers2026accountingagents,
  title={AccountingAgents: A Multi-Agent LLM Framework for Accounting Firm Automation},
  author={Desrochers, Paul},
  year={2026},
  month={April},
  note={Preprint. GitHub: https://github.com/pdesrochers01/accounting-agents}
}
```

---

## Contact

Paul Desrochers — Independent Researcher, Quebec, Canada
pdesrochers.ai.research@gmail.com
https://cv.paul-desrochers.com

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).
