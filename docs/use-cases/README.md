# Use Cases — AccountingAgents

This directory documents the eight use cases covered by the
AccountingAgents multi-agent framework.

| UC   | Agent                | Title                                         | Status |
|------|----------------------|-----------------------------------------------|--------|
| UC01 | Ingestion Agent      | Document Ingestion and Classification         | ✅     |
| UC02 | Reconciliation Agent | Reconciliation Gap Detection                  | ✅     |
| UC03 | HITL Notifier        | Human-in-the-Loop Approval Cycle              | ✅     |
| UC04 | AR Agent             | AR Agent: Overdue Invoice Collections         | ✅     |
| UC05 | AP Agent             | AP Agent: Vendor Bill Processing              | ✅     |
| UC06 | Reporting Agent      | Reporting Agent: Financial Report Generation  | ✅     |
| UC07 | Compliance Agent     | Compliance Agent: Fiscal Deadline Monitoring  | ✅     |
| UC08 | Onboarding Agent     | Onboarding Agent: New Client Profile Creation | ✅     |

## HITL Escalation Model

| Level | Mode           | Trigger                           | Example                                     |
|-------|----------------|-----------------------------------|---------------------------------------------|
| N1    | Automatic      | Routine, low-risk action          | First AR reminder, bill < $500              |
| N2    | Notify only    | Action taken; cancellable         | Invoice created, profile drafted            |
| N3    | Approve (HITL) | High-value or irreversible action | AR > $5k, reconciliation gap, payment > $2k |
| N4    | Transfer       | Outside known rules               | Dispute, regulatory anomaly, invalid data   |
