# UC05 — AP Agent: Vendor Bill Processing

## Summary
The AP Agent processes incoming vendor bills. It auto-approves routine
low-value bills, flags duplicates, and escalates high-value or unrecognized
vendor payments to HITL before any disbursement is committed.

## Trigger
- routing_signal == "to_ap" emitted by Supervisor after ingestion
  of a supplier_invoice document

## Actors
- AP Agent
- Supervisor (routing)
- Accountant (HITL approval for N3/N4 escalations)

## Preconditions
- SharedState contains input_document with supplier_invoice type
- QBO MCP accessible (or AP_MODE=mock)

## Main Flow

1. AP Agent reads input_document from SharedState.
   Extracts: vendor_name, amount_cad, invoice_number, invoice_date.

2. Checks for duplicate (same vendor + amount + date already in QBO):
   - Duplicate detected → N4: transfer, do not process

3. Validates vendor against known vendor list (QBO or fixture):
   - Unknown vendor → N4: transfer for manual vendor setup

4. Classifies by amount:
   - amount < $500    → N1: auto-approve, mark bill as paid in QBO
   - $500–$2,000      → N2: notify accountant, bill queued
   - > $2,000         → N3: HITL required before payment

5. AP Agent writes ap_results to SharedState:
   - vendor_name, amount_cad, invoice_number, action_taken,
     escalation_level, duplicate: bool

6. routing_signal set:
   - N1           → "completed"
   - N2/N3/N4     → "to_hitl"

## Escalation Examples

| Amount      | Vendor    | Level | Action                         |
|-------------|-----------|-------|--------------------------------|
| $320.00     | Known     | N1    | Auto-approved, QBO updated     |
| $1,250.00   | Known     | N2    | Queued + accountant notified   |
| $4,500.00   | Known     | N3    | HITL before payment            |
| Any amount  | Unknown   | N4    | Transfer — vendor not in QBO   |
| Duplicate   | Any       | N4    | Transfer — duplicate detected  |

## Postconditions
- ap_results written to SharedState
- Bill record written to hitl_emails/ap_bill_{invoice_number}.json (mock)
- HITL triggered if N2/N3/N4

## Environment Modes
- AP_MODE=mock  → fixture vendors, no QBO write (default)
- AP_MODE=mcp   → live QBO MCP bill creation and payment (Phase 4+)

## SharedState Fields Used
- input_document: IngestedDocument  (read)
- ap_results: list[APResult]        (write)
- routing_signal                    (write)
- hitl_pending                      (write if N2/N3/N4)
- error_log                         (write on error)
