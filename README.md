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
| VI. HITL | HITL Notifier · Webhook Resumption | Async approval via messaging; resume suspended thread | Gmail MCP · FastAPI · SqliteSaver |

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
├── paper/accounting_agents_paper.pdf    # Preprint (April 2026)
├── docs/flowchart-macro.html            # Macro architecture diagram
├── docs/langgraph-hitl-gmail.html       # LangGraph HITL flow diagram
├── src/                                 # MVP implementation (coming soon)
├── README.md
├── LICENSE                              # Apache 2.0
└── .gitignore
```

---

## Roadmap

- [ ] MVP implementation (LangGraph + MCP)
- [ ] Experimental validation paper (agent accuracy, HITL approval rates, time savings)
- [ ] Support for Xero, Sage, and Microsoft Dynamics 365
- [ ] Canadian regulatory rules (GST/HST, Revenu Québec)

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
