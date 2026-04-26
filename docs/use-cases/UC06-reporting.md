# UC06 — Periodic Financial Report Generation

**Main actor**: Reporting Agent  
**Trigger**: Routing signal `to_reporting` from Supervisor

## Preconditions
- QBO MCP connected and authenticated
- Gmail MCP connected and authenticated
- SharedState initialized with `thread_id` and reporting period

## Main Flow
1. Reporting Agent receives routing signal `to_reporting` from Supervisor
2. It queries QBO MCP for the reporting period — REPORTING_MODE=mock uses fixture data:
   - Profit & Loss: revenue, expenses, net income
   - Cash flow summary
   - AR aging by bucket (0–30, 31–60, 60+ days)
   - AP summary: pending bills and upcoming due dates
3. It structures the report data into SharedState (`report_data`)
4. It detects anomalies:
   - Revenue drop > 20% vs previous period → N3
   - Expense spike > 30% → N2
   - Negative cash flow → N3
   - AR aging shift (60+ bucket growing) → N2
   - QBO data inconsistency (totals do not balance) → N4
5. It classifies by escalation level:
   - N1: no anomaly → format and send report
   - N2: minor anomaly → include flag in report, send + notify
   - N3: significant anomaly → set hitl_pending: true, do not send
   - N4: data integrity issue → routing_signal: "unrecognized"
6. For N1/N2: Reporting Agent writes report to hitl_emails/ (mock) or sends via Gmail MCP (mcp)
7. It writes delta to SharedState (`report_data`, `report_sent`, `routing_signal`)
8. Supervisor routes: N3 → UC03 HITL cycle, otherwise `completed`

## Alternate Flow — No Data Available
- At step 2, if QBO returns empty results for the period
- Reporting Agent writes `routing_signal: "no_report_data"` to SharedState
- Supervisor triggers N2 notification — accountant investigates QBO connection

## Alternate Flow — N3 Anomaly Detected
- At step 4, if significant anomaly found
- Reporting Agent writes `hitl_pending: true`, anomaly details to SharedState
- Supervisor triggers UC03 — accountant reviews and approves report before sending

## Postconditions
- Report data structured in SharedState (`report_data`)
- Report sent via Gmail for N1/N2 cases
- HITL triggered for N3 cases
- Routing signal emitted
