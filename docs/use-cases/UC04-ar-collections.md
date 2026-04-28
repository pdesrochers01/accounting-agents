# UC04 — AR Agent: Overdue Invoice Collections

## Summary
The AR Agent monitors outstanding client invoices and triggers collection
actions based on days overdue and amount. It sends automatic reminders for
low-risk cases and escalates to HITL for disputed or high-value receivables.

## Trigger
- routing_signal == "to_ar" emitted by Supervisor after ingestion, or
- scheduled run (daily)

## Actors
- AR Agent
- Supervisor (routing)
- Accountant (HITL approval for N3/N4 escalations)

## Preconditions
- SharedState contains ar_invoices (or None → fixture used)
- QBO MCP accessible (or AR_MODE=mock)
- Gmail MCP accessible for reminder sending (or AR_MODE=mock)

## Main Flow

1. AR Agent reads ar_invoices from SharedState.
   If None, loads fixture (3 fictional Quebec clients, CAD amounts).

2. For each invoice, computes days_overdue and classifies:
   - days_overdue <= 0  → not yet due, skip
   - 1–30 days         → N1: send first reminder automatically
   - 31–60 days        → N2: send second reminder, notify accountant
   - > 60 days         → N3: HITL required before escalation
   - disputed flag     → N4: transfer to human

3. AR Agent writes ar_results to SharedState:
   - list[ARResult]: invoice_id, client_name, amount_cad, days_overdue,
     action_taken, escalation_level

4. routing_signal set based on highest escalation:
   - All N1           → "completed"
   - Any N2           → "to_hitl" (notify only)
   - Any N3/N4        → "to_hitl" (approve required / transfer)

## Escalation Examples

| Days overdue | Amount    | Level | Action                        |
|-------------|-----------|-------|-------------------------------|
| 15 days     | $1,200    | N1    | First reminder sent (auto)    |
| 45 days     | $3,400    | N2    | Second reminder + notify      |
| 75 days     | $8,750    | N3    | HITL before collections firm  |
| Any         | Disputed  | N4    | Transfer to accountant        |

## Postconditions
- ar_results written to SharedState
- Reminders written to hitl_emails/ar_reminder_{invoice_id}.json (mock)
- HITL triggered if N2/N3/N4 detected

## Environment Modes
- AR_MODE=mock  → fixture invoices, reminders saved to hitl_emails/ (default)
- AR_MODE=mcp   → live QBO MCP + Gmail MCP (Phase 4+)

## SharedState Fields Used
- ar_invoices: Optional[list[ARInvoice]]  (read)
- ar_results: list[ARResult]              (write)
- routing_signal                          (write)
- hitl_pending                            (write if N2/N3/N4)
- error_log                               (write on error)
