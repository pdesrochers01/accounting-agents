# UC03 — Full HITL Cycle (Mobile Approval)

**Main actors**: Supervisor + supervising accountant (human)  
**Trigger**: `hitl_pending: true` detected in SharedState

## Preconditions
- SharedState contains the exception details (`reconciliation_gaps` or equivalent)
- Gmail MCP connected
- FastAPI webhook listening (ngrok active in dev)
- SqliteSaver configured as checkpointer

## Main Flow
1. The Supervisor calls `interrupt()` — LangGraph thread suspended, state persisted via SqliteSaver
2. The Supervisor builds a structured email: client context, gap details, amount, suggestion
3. The email contains 3 action links: **Approve** / **Modify** / **Block**
4. Gmail MCP sends the email to the supervising accountant
5. The accountant receives the email on their iPhone and clicks a link
6. The click triggers an HTTP GET request to the FastAPI webhook (`/webhook?thread_id=xxx&decision=approve`)
7. The webhook writes the decision to SharedState (`hitl_decision`, `hitl_pending: false`)
8. LangGraph resumes the suspended thread at the exact point of interruption
9. The Supervisor routes based on the decision: executes, modifies, or blocks the action

## Alternate Flow — 4-Hour Timeout
- The timeout handler injects `hitl_decision: "timeout"` into SharedState
- The Supervisor automatically escalates to N4

## Alternate Flow — "Modify" Decision
- The webhook captures the comment and writes it to SharedState (`hitl_comment`)
- The Supervisor re-routes to the Reconciliation Agent with the comment as a constraint

## Postconditions
- Human decision traced in SharedState
- LangGraph thread resumed or closed cleanly
- Action executed, modified, or blocked according to the decision
