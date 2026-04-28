# UC07 — Compliance Agent: Fiscal Deadline Monitoring

## Summary
The Compliance Agent monitors fiscal deadlines and regulatory obligations
for the firm's clients. It proactively detects upcoming or missed filings,
tax remittances, and payroll obligations, then routes to HITL or auto-notifies
based on urgency and risk level.

## Trigger
- Scheduled run (daily cron) OR
- routing_signal == "to_compliance" emitted by Supervisor after ingestion

## Actors
- Compliance Agent
- Supervisor (routing)
- Accountant (HITL approval for high-risk deadlines)

## Preconditions
- SharedState contains client_id and fiscal_period
- Calendar MCP accessible (or COMPLIANCE_MODE=mock)
- QBO MCP accessible for remittance amounts

## Main Flow

1. Compliance Agent reads compliance_input from SharedState
   (client_id, fiscal_period, jurisdiction="QC+CA")

2. Agent queries Calendar MCP (or fixture) for upcoming deadlines:
   - GST/HST remittance
   - QST remittance
   - Corporate tax instalments
   - Payroll source deductions (RP account)
   - T4 / RL-1 filing deadlines

3. For each deadline, agent computes days_remaining and classifies:
   - days_remaining > 30  → status: "ok"
   - 8–30 days            → status: "upcoming"  → N2 notify
   - 1–7 days             → status: "urgent"    → N3 HITL required
   - 0 or past            → status: "overdue"   → N4 transfer

4. Agent writes compliance_results to SharedState:
   - list[ComplianceItem]: deadline, obligation_type, amount_due,
     days_remaining, status, escalation_level

5. routing_signal set based on highest escalation found:
   - All N1    → "completed"
   - Any N2    → "to_hitl" (notify only)
   - Any N3    → "to_hitl" (approve required)
   - Any N4    → "to_hitl" (transfer)

## Escalation Examples

| Obligation          | Days remaining | Level | Action               |
|---------------------|----------------|-------|----------------------|
| GST/HST remittance  | 45             | N1    | No action            |
| QST remittance      | 12             | N2    | Email notification   |
| Payroll deductions  | 3              | N3    | HITL approval        |
| Corporate tax       | -2 (overdue)   | N4    | Transfer to human    |

## Postconditions
- compliance_results written to SharedState
- HITL triggered if N3/N4 deadlines detected
- hitl_emails/compliance_{client_id}_{period}.json written (mock mode)

## Environment Modes
- COMPLIANCE_MODE=mock  → fixture-based deadlines (default, no MCP)
- COMPLIANCE_MODE=mcp   → live Calendar MCP + QBO MCP (Phase 4+)

## SharedState Fields Used
- compliance_input: Optional[ComplianceInput]  (read)
- compliance_results: list[ComplianceItem]     (write)
- routing_signal                               (write)
- hitl_pending                                 (write if N3/N4)
- error_log                                    (write on error)
