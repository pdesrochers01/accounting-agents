# UC05 — AP Payment Approval Cycle

**Main actor**: AP Agent  
**Trigger**: Routing signal `to_ap` from Supervisor after UC01 (supplier invoice ingested)

## Preconditions
- SharedState contains at least one ingested supplier invoice (`documents_ingested`)
- QBO MCP connected and authenticated
- Gmail MCP connected and authenticated

## Main Flow
1. AP Agent reads pending supplier invoices from SharedState (`documents_ingested`)
2. It queries QBO MCP to match each invoice against known vendors — AP_MODE=mock uses fixture data
3. For each invoice, it checks: vendor known, amount within expected range, due date valid
4. It detects duplicates: same vendor + amount already present in `ap_actions`
5. It classifies the payment action by escalation level:
   - N1: known vendor, amount < $500 CAD → auto-approve
   - N2: known vendor, amount $500–$2,000 CAD → approve + flag for notification
   - N3: amount > $2,000 CAD OR unknown vendor → set hitl_pending: true
   - N4: unrecognized vendor pattern → routing_signal: "unrecognized"
6. For N1/N2: AP Agent records approval in SharedState (`ap_actions`)
7. Supervisor routes: N3 → UC03 HITL cycle, duplicate → END, otherwise `completed`

## Alternate Flow — Duplicate Bill Detected
- At step 4, if vendor + amount already in `ap_actions`
- AP Agent writes `routing_signal: "duplicate_bill"` to SharedState
- Supervisor closes cycle — no action taken, accountant notified via N2 flag

## Alternate Flow — N3 Escalation
- At step 5, if amount > $2,000 CAD or unknown vendor
- AP Agent writes `hitl_pending: true`, bill details and vendor info to SharedState
- Supervisor triggers UC03 — accountant approves or blocks the payment

## Postconditions
- All payment decisions recorded in SharedState (`ap_actions`)
- HITL triggered for N3 cases
- Routing signal emitted
