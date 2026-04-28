# UC06 — Reporting Agent: Financial Report Generation

## Summary
The Reporting Agent generates periodic financial reports (P&L, cash flow,
AR aging) and runs anomaly detection. It notifies the accountant of
significant findings and escalates critical anomalies to HITL.

## Trigger
- routing_signal == "to_reporting" emitted by Supervisor after ingestion
  of a reporting_request document, or scheduled (monthly)

## Actors
- Reporting Agent
- Supervisor (routing)
- Accountant (HITL approval for N3/N4 anomalies)

## Preconditions
- SharedState contains reporting_input (or None → fixture used)
- QBO MCP accessible (or REPORTING_MODE=mock)

## Main Flow

1. Reporting Agent reads reporting_input from SharedState.
   If None, uses fixture for period "2026-Q1", client "CLIENT-001".

2. Fetches financial data from QBO MCP (or fixture):
   - P&L: revenue, expenses, net income
   - Cash flow: operating, investing, financing
   - AR aging: current, 30/60/90+ day buckets

3. Runs anomaly detection on each report section:
   - Revenue drop > 20% MoM     → N3 (significant, HITL)
   - Cash flow negative          → N3 (critical, HITL)
   - Expense spike > 30% MoM    → N2 (notify)
   - AR aging > 90 days > 15%   → N2 (notify)
   - Data integrity error        → N4 (transfer)

4. Writes reporting_results to SharedState:
   - period, report_type, summary: dict, anomalies: list[Anomaly],
     highest_escalation: str

5. routing_signal set based on highest anomaly:
   - No anomalies / N1  → "completed"
   - Any N2             → "to_hitl" (notify)
   - Any N3             → "to_hitl" (approve required)
   - Any N4             → "to_hitl" (transfer)

## Anomaly Examples

| Condition                  | Level | Action                        |
|----------------------------|-------|-------------------------------|
| Revenue -25% vs last month | N3    | HITL — review before closing  |
| Negative operating CF      | N3    | HITL — cash position critical |
| Expense +35% MoM           | N2    | Notify — review expenses      |
| AR 90+ days = 22% of total | N2    | Notify — collection action    |
| Mismatched trial balance   | N4    | Transfer — data integrity     |

## Postconditions
- reporting_results written to SharedState
- Report saved to hitl_emails/report_{period}.json (mock)
- HITL triggered if N2/N3/N4 anomalies detected

## Environment Modes
- REPORTING_MODE=mock  → fixture financials, no QBO call (default)
- REPORTING_MODE=mcp   → live QBO MCP reports (Phase 4+)

## SharedState Fields Used
- reporting_input: Optional[ReportingInput]    (read)
- reporting_results: Optional[ReportingResult] (write)
- routing_signal                               (write)
- hitl_pending                                 (write if N2/N3/N4)
- error_log                                    (write on error)
