"""
FastAPI webhook endpoint — receives HITL decisions from accountant's mobile.

Flow:
  Accountant clicks link in email
  → GET /webhook?thread_id=xxx&decision=approve
  → webhook writes decision to SharedState
  → LangGraph resumes suspended thread
"""

import sqlite3
from datetime import datetime, timezone
from typing import Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from accounting_agents.graph import build_graph

app = FastAPI(title="AccountingAgents HITL Webhook")

# In dev: SQLite file-based checkpointer (persists between runs)
DB_PATH = "accounting_agents.db"


def get_graph():
    """Build graph with persistent SQLite checkpointer."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/webhook")
def webhook(
    thread_id: str = Query(...),
    decision: Literal["approve", "modify", "block"] = Query(...),
    comment: Optional[str] = Query(None),
):
    """
    Receive HITL decision from accountant.

    Query params:
      thread_id: str                          — LangGraph thread ID
      decision:  approve | modify | block     — FastAPI validates via Literal
      comment:   str                          — optional, used with decision=modify
    """
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}

        # Inject decision into SharedState and resume
        graph.invoke(
            {
                "hitl_decision": decision,
                "hitl_comment": comment if comment else None,
                "hitl_pending": False,
            },
            config=config,
        )

        return {
            "status": "resumed",
            "thread_id": thread_id,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
