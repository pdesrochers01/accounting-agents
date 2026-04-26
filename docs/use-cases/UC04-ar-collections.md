# UC04 — AR Collections Cycle

**Main actor**: AR Agent  
**Trigger**: Routing signal `to_ar` from Supervisor

## Preconditions
- QBO MCP connected and authenticated
- Gmail MCP connected and authenticated
- SharedState initialized with `thread_id`

## Main Flow
1. AR Agent receives routing signal `to_ar` from Supervisor
2. It queries QBO MCP for open invoices (status: unpaid) — AR_MODE=mock uses fixture data
3. It filters by overdue threshold: invoices past due date
4. For each overdue invoice, it calculates days overdue and outstanding amount
5. It classifies the collection action by escalation level:
   - N1: ≤ 30 days overdue AND amount < $5,000 CAD → auto-send reminder
   - N2: 31–60 days overdue → send reminder + flag for notification
   - N3: > 60 days overdue OR amount ≥ $5,000 CAD → set hitl_pending: true
   - N4: disputed/unrecognized client → routing_signal: "unrecognized"
6. For N1/N2: AR Agent writes reminder to hitl_emails/ (mock) or sends via Gmail MCP (mcp)
7. It writes delta to SharedState (`ar_actions`, `routing_signal`)
8. Supervisor routes: N3 → UC03 HITL cycle, otherwise `completed`

## Alternate Flow — No Overdue Invoices
- At step 3, if no invoices are past due date
- AR Agent writes `routing_signal: "nothing_to_collect"` to SharedState
- Supervisor closes cycle cleanly

## Alternate Flow — N3 Escalation
- At step 5, if threshold exceeded
- AR Agent writes `hitl_pending: true` and invoice details to SharedState
- Supervisor triggers UC03 — accountant approves escalation letter or legal referral

## Postconditions
- All collection actions recorded in SharedState (`ar_actions`)
- Reminder emails sent for N1/N2 cases
- HITL triggered for N3 cases
- Routing signal emitted
