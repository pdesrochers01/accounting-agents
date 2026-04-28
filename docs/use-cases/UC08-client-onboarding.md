# UC08 — Onboarding Agent: New Client Profile Creation

## Summary
The Onboarding Agent creates and validates new client profiles in QBO
when a new engagement is initiated. It drafts the client record, validates
required fiscal identifiers (NEQ, GST/HST number, QST number), and routes
to HITL before any profile is committed to the live QBO environment.

## Trigger
- routing_signal == "to_onboarding" emitted by Supervisor after ingestion
  of an onboarding document (e.g. engagement letter, new client form)

## Actors
- Onboarding Agent
- Supervisor (routing)
- Accountant (HITL approval — mandatory before any QBO write)

## Preconditions
- SharedState contains onboarding_input with client data
- QBO MCP accessible (or ONBOARDING_MODE=mock)
- Ingestion Agent has classified document as "onboarding_form"

## Main Flow

1. Onboarding Agent reads onboarding_input from SharedState:
   - client_name, legal_form, address, contact_email
   - fiscal_year_end, jurisdiction ("QC" | "CA" | "QC+CA")
   - identifiers: neq (optional), gst_number (optional), qst_number (optional)

2. Agent validates all required fields:
   - Missing mandatory fields → N4 (incomplete profile, transfer)
   - Invalid NEQ format (exactly 9 digits) → N4
   - Invalid GST number format (9 digits + RT + 4 digits) → N4
   - Invalid QST number format (10 digits + TQ + 4 digits) → N4

3. Agent drafts QBO customer profile (not yet written to QBO):
   - Maps client fields to QBO Customer object schema
   - Adds Quebec-specific tax codes (GST/QST)
   - Sets fiscal year end and default currency (CAD)

4. Agent writes onboarding_draft to SharedState:
   - client_name, qbo_customer_payload, validation_errors: list[str],
     escalation_level, status ("draft_ready" | "validation_failed")

5. Routing based on validation result:
   - validation_failed → N4 → "to_hitl" (transfer — missing/invalid data)
   - draft_ready       → N2 → "to_hitl" (notify — profile drafted, cancellable)

6. On HITL approve (N3 — mandatory for any QBO write):
   - Agent calls QBO MCP CreateCustomer with qbo_customer_payload
   - Sends welcome email via Gmail MCP (ONBOARDING_MODE=mcp)
   - routing_signal → "completed"

7. On HITL block:
   - Profile discarded, no QBO write
   - routing_signal → "completed"

## Escalation Model

| Condition                        | Level | Action                         |
|----------------------------------|-------|--------------------------------|
| All fields valid, profile ready  | N2    | Notify — profile drafted       |
| Accountant reviews and approves  | N3    | HITL required before QBO write |
| Missing/invalid identifiers      | N4    | Transfer — incomplete profile  |
| Duplicate client detected in QBO | N4    | Transfer — manual resolution   |

## Note on N2→N3 escalation
Writing to a live QBO environment always requires explicit accountant
approval. The Onboarding Agent always stops at N2 (notify) or N4 (transfer).
The N3 HITL gate is enforced by the HITL node on resume — it never auto-commits
a QBO write regardless of N2 notification status.

## Postconditions
- onboarding_draft written to SharedState
- If approved: QBO customer created, welcome email sent
- If blocked: no QBO write, state marked completed
- hitl_emails/onboarding_{client_name_slug}.json written (mock mode)

## Environment Modes
- ONBOARDING_MODE=mock  → no QBO write, draft saved to hitl_emails/ (default)
- ONBOARDING_MODE=mcp   → live QBO MCP CreateCustomer (Phase 4+)

## SharedState Fields Used
- onboarding_input: Optional[OnboardingInput]   (read)
- onboarding_draft: Optional[OnboardingDraft]   (write)
- routing_signal                                (write)
- hitl_pending                                  (write)
- hitl_decision                                 (read on resume)
- error_log                                     (write on error)
