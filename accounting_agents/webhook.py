"""
Flask webhook endpoint — receives HITL decisions from accountant's mobile.

Flow:
  Accountant clicks link in email
  → GET /webhook?thread_id=xxx&decision=approve
  → webhook writes decision to SharedState
  → LangGraph resumes suspended thread
"""

import sqlite3
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from langgraph.checkpoint.sqlite import SqliteSaver
from accounting_agents.graph import build_graph

app = Flask(__name__)
app.config['SERVER_NAME'] = None

# In dev: SQLite file-based checkpointer (persists between runs)
DB_PATH = "accounting_agents.db"


def get_graph():
    """Build graph with persistent SQLite checkpointer."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return build_graph(checkpointer)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/webhook", methods=["GET"])
def webhook():
    """
    Receive HITL decision from accountant.

    Query params:
      thread_id: str  — LangGraph thread ID
      decision:  str  — approve | modify | block
      comment:   str  — optional, used with decision=modify
    """
    thread_id = request.args.get("thread_id")
    decision = request.args.get("decision")
    comment = request.args.get("comment", "")

    # --- Validation ---
    if not thread_id:
        return jsonify({"error": "missing thread_id"}), 400

    valid_decisions = {"approve", "modify", "block"}
    if decision not in valid_decisions:
        return jsonify({
            "error": f"invalid decision '{decision}'",
            "valid": list(valid_decisions)
        }), 400

    # --- Resume suspended LangGraph thread ---
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

        return jsonify({
            "status": "resumed",
            "thread_id": thread_id,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001, host='0.0.0.0')
