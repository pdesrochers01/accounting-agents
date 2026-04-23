# UC02 — Reconciliation and Gap Detection

**Main actor**: Reconciliation Agent  
**Trigger**: Routing signal received from the Supervisor after UC01

## Preconditions
- SharedState contains at least one ingested document (`documents_ingested` non-empty)
- QBO MCP accessible (transactions and accounts)

## Main Flow
1. The Reconciliation Agent reads pending transactions from QBO MCP
2. It loads the reference bank statement from SharedState
3. It performs transaction-by-transaction matching (amount, date ±3 days, supplier)
4. It calculates gaps: unmatched transactions, discordant amounts
5. If all gaps are below the N1 threshold (<$500 CAD): writes the result to SharedState and ends
6. If a gap exceeds the N3 threshold (>$2,000 CAD): writes `hitl_pending: true` and the details to SharedState
7. The Supervisor detects `hitl_pending` and triggers UC03

## Alternate Flow — No Transactions to Reconcile
- At step 1, if QBO returns no pending transactions
- The agent writes `routing_signal: "nothing_to_reconcile"` to SharedState
- The Supervisor closes the cycle cleanly

## Postconditions
- Gaps documented in SharedState (`reconciliation_gaps`)
- Routing signal emitted: cycle ended (N1) or HITL triggered (N3)
