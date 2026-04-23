# UC01 — Financial Document Ingestion

**Main actor**: Ingestion Agent  
**Trigger**: Arrival of an email with an attachment in the firm's Gmail inbox

## Preconditions
- Gmail MCP connected and authenticated
- QBO MCP connected and authenticated
- SharedState initialized

## Main Flow
1. The Ingestion Agent queries Gmail MCP for unprocessed emails
2. It detects an attachment (PDF, CSV, image)
3. It classifies the document: supplier invoice, bank statement, receipt, other
4. It extracts key metadata: date, amount, currency, supplier/client, document number
5. It creates or updates the corresponding entry in QBO via QBO MCP
6. It writes the delta to SharedState (`documents_ingested`, `routing_signal`)
7. The Supervisor receives the signal and routes to the Reconciliation Agent

## Alternate Flow — Unrecognized Document
- At step 3, if classification fails (confidence < threshold)
- The agent writes `routing_signal: "unrecognized"` to SharedState
- The Supervisor triggers an N4 escalation (human handoff)

## Postconditions
- Document classified and recorded in QBO
- SharedState updated with the document metadata
- Routing signal emitted to the next step
