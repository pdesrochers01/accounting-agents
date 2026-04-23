"""
End-to-end test using stub nodes only.
Validates the full graph flow: START → ingestion → reconciliation
→ hitl → END using hardcoded stub responses.

No MCP, no Gmail, no QBO — pure LangGraph routing validation.
"""

import sqlite3
import uuid
from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph
from accounting_agents.state import initial_state


def test_end_to_end_stub_flow():
    # --- Setup ---
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state = initial_state(thread_id)

    print(f"Thread ID: {thread_id}")
    print("Starting end-to-end stub flow...")

    # --- Run graph ---
    result = graph.invoke(state, config=config)

    # --- Assertions ---
    print(f"routing_signal:  {result.get('routing_signal')}")
    print(f"hitl_pending:    {result.get('hitl_pending')}")
    print(f"hitl_decision:   {result.get('hitl_decision')}")
    print(f"error_log:       {result.get('error_log')}")

    # Ingestion stub sets routing_signal to "to_reconciliation"
    # Reconciliation stub overrides it to "hitl_pending"
    # hitl stub sets hitl_decision to "approve" and hitl_pending to False
    assert result.get("hitl_decision") == "approve", \
        f"Expected 'approve', got {result.get('hitl_decision')}"
    assert result.get("hitl_pending") == False, \
        f"Expected hitl_pending=False, got {result.get('hitl_pending')}"
    assert result.get("error_log") == [], \
        f"Expected empty error_log, got {result.get('error_log')}"

    print("✅ End-to-end stub flow passed.")


if __name__ == "__main__":
    test_end_to_end_stub_flow()
