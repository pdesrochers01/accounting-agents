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

AccountingAgents comprises seven specialized agents organized in a hierarchical supervisor-worker graph. All inter-agent communication flows exclusively through a structured `SharedState` TypedDict, eliminating context corruption across long conversation histories.

| Team | Agent | Goal | MCP Tools (MVP) |
|---|---|---|---|
| I. Ingestion | Ingestion Agent · Document Classifier | Capture & classify incoming financial documents | Gmail MCP · QBO MCP · LLM |
| II. Reconciliation | Reconciliation Agent · Gap Detector | Match transactions vs. bank statements; flag discrepancies | QBO MCP · Drive MCP |
| III. Reporting | Reporting Agent · Compliance Agent | Generate P&L, cash flow; monitor fiscal deadlines | QBO MCP · Gmail MCP · Calendar MCP |
| IV. AR / AP / Client | AR Agent · AP Agent · Onboarding Agent | Track overdue invoices; approve vendor bills & payments; create client profiles | QBO MCP · Gmail MCP · Calendar MCP |
| V. Supervisor | Supervisor · Decision Router | Orchestrate state, routing, and error handling | LangGraph StateGraph · checkpointer |
| VI. HITL | HITL Notifier · Webhook Resumption | Async approval via messaging; resume suspended thread | Gmail MCP · Flask · SqliteSaver |

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

| MCP Server | Role |
|---|---|
| **Gmail MCP** | All email I/O, including HITL notifications and approval links |
| **QuickBooks Online MCP** | CRUD on Account, Bill, Customer, Invoice, Vendor, and 7 additional entities |
| **Google Drive MCP** | Financial document storage and retrieval |
| **Google Calendar MCP** | Fiscal deadline monitoring and scheduling |
| **Zapier MCP** | General-purpose bridge to services without a native MCP server |

Additional MCP servers can be substituted or added without modifying agent logic.

---

## Project Structure

```
accounting-agents/
├── accounting_agents/
│   ├── __init__.py
│   ├── state.py              # SharedState TypedDict
│   ├── graph.py              # LangGraph StateGraph
│   ├── routing.py            # Conditional routing functions
│   ├── webhook.py            # Flask HITL webhook (port 5001)
│   └── nodes/
│       ├── ingestion.py      # Ingestion Agent (keyword classification)
│       ├── reconciliation.py # Reconciliation Agent (gap detection)
│       └── hitl.py           # HITL node — interrupt() + notification
├── docs/
│   ├── use-cases/            # UC01, UC02, UC03
│   ├── flowchart-macro.html  # Macro architecture diagram
│   └── langgraph-hitl-gmail.html # LangGraph HITL flow diagram
├── tests/
│   ├── fixtures/             # Fictional Quebec firm test data (CAD)
│   ├── test_ingestion.py     # 9/9 tests
│   ├── test_reconciliation.py # 2/2 tests
│   ├── test_hitl.py          # Full HITL cycle
│   └── test_end_to_end_real.py # 3/3 end-to-end tests
├── scripts/
│   └── demo_hitl.py          # Live HITL demo script
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

**Run tests**

```bash
PYTHONPATH=. .venv/bin/python tests/test_end_to_end_real.py
```

**Run HITL demo** (requires ngrok)

```bash
# Terminal 1 — Flask webhook server
PYTHONPATH=. python accounting_agents/webhook.py

# Terminal 2 — ngrok tunnel
ngrok http 5001

# Terminal 3 — demo script
PYTHONPATH=. .venv/bin/python scripts/demo_hitl.py
# Open the APPROVE link from any mobile device
```

---

## Roadmap

- [x] MVP implementation — Supervisor, Ingestion, Reconciliation, async HITL
- [x] SharedState TypedDict + LangGraph StateGraph
- [x] Async HITL cycle — interrupt() + Flask webhook + mobile approval
- [x] Test suite — 14+ tests, 3 end-to-end scenarios
- [ ] Gmail MCP real integration (Phase 2)
- [ ] QBO MCP real integration (Phase 2)
- [ ] FastAPI webhook + Pydantic validation (Phase 2)
- [ ] LLM-based document classification (Phase 2)
- [ ] AR Agent + AP Agent + Reporting Agent (Phase 3)
- [ ] Compliance Agent + Onboarding Agent (Phase 4)
- [ ] Experimental validation paper (agent accuracy, HITL approval rates)
- [ ] Support for Xero, Sage, Microsoft Dynamics 365

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
