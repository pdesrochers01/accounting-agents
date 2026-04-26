"""
Unit tests for the Reporting Agent node (UC06).
No MCP, no LangGraph graph execution — pure node logic.

Reporting data is injected via state["reporting_input"] so tests
are fully deterministic. None triggers the built-in fixture (N1 clean),
{} means no data available.

Test coverage:
  - N1 clean report (no anomalies, report written to hitl_emails/)
  - N2 minor anomaly (expense spike > 30%, report sent with flag)
  - N3 HITL trigger (revenue drop > 20% — report NOT sent)
  - N3 HITL trigger (negative cash flow)
  - N4 data integrity (revenue - expenses ≠ net_income → unrecognized)
  - No data (empty reporting_input → no_report_data)
"""

from accounting_agents.nodes.reporting import reporting_node
from accounting_agents.state import initial_state


# ── Helpers ──────────────────────────────────────────────────────

def _base_current(
    revenue: float = 87500.00,
    expenses: float = 54000.00,
    net_income: float = 33500.00,
    cash_flow: float = 29000.00,
) -> dict:
    """Build a current-period dict with sane AR/AP defaults."""
    return {
        "revenue":    revenue,
        "expenses":   expenses,
        "net_income": net_income,
        "cash_flow":  cash_flow,
        "ar_aging": [
            {"bucket_label": "0-30 days",  "count": 6, "total_cad": 14500.00},
            {"bucket_label": "31-60 days", "count": 2, "total_cad":  4800.00},
            {"bucket_label": "61-90 days", "count": 1, "total_cad":  2100.00},
            {"bucket_label": "90+ days",   "count": 0, "total_cad":     0.00},
        ],
        "ap_summary": {"total_cad": 19200.00, "overdue_count": 1},
    }


def _state_with(reporting_input: dict, thread_id: str = "test-reporting") -> dict:
    state = initial_state(thread_id)
    state["reporting_input"] = reporting_input
    return state


# ── Tests ────────────────────────────────────────────────────────

def test_reporting_n1_clean():
    """No anomalies → N1, report written, routing_signal: completed."""
    state = _state_with(
        {
            "period": "2026-03",
            "current": _base_current(),
            "previous": {"revenue": 85000.00, "expenses": 52000.00},
        },
        "test-rep-n1",
    )
    result = reporting_node(state)

    assert result["routing_signal"] == "completed"
    assert result["report_sent"] is True
    assert result["hitl_pending"] is False
    assert result["report_data"] is not None
    assert result["report_data"]["period"] == "2026-03"
    assert result["report_data"]["anomalies"] == []
    assert result["error_log"] == []
    print(f"✅ test_reporting_n1_clean passed — "
          f"period={result['report_data']['period']}, anomalies=0")


def test_reporting_n2_expense_spike():
    """Expenses up 40% vs prior period → N2 flag, report still sent."""
    state = _state_with(
        {
            "period": "2026-03",
            "current": _base_current(expenses=74000.00, net_income=13500.00),
            "previous": {"revenue": 85000.00, "expenses": 52000.00},
        },
        "test-rep-n2",
    )
    result = reporting_node(state)

    assert result["routing_signal"] == "completed"
    assert result["report_sent"] is True
    assert result["hitl_pending"] is False
    assert result["report_data"] is not None
    assert len(result["report_data"]["anomalies"]) >= 1
    anomaly_text = " ".join(result["report_data"]["anomalies"])
    assert "spike" in anomaly_text.lower() or "expense" in anomaly_text.lower()
    assert result["error_log"] == []
    print(f"✅ test_reporting_n2_expense_spike passed — "
          f"anomalies={result['report_data']['anomalies']}")


def test_reporting_n3_revenue_drop():
    """Revenue dropped 25% vs prior period → N3, report NOT sent, hitl_pending."""
    state = _state_with(
        {
            "period": "2026-03",
            "current": _base_current(revenue=63750.00, net_income=9750.00),
            "previous": {"revenue": 85000.00, "expenses": 52000.00},
        },
        "test-rep-n3-revenue",
    )
    result = reporting_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["report_sent"] is False
    assert result["hitl_pending"] is True
    assert result["report_data"] is not None
    assert len(result["report_data"]["anomalies"]) >= 1
    anomaly_text = " ".join(result["report_data"]["anomalies"])
    assert "revenue" in anomaly_text.lower()
    assert result["error_log"] == []
    print(f"✅ test_reporting_n3_revenue_drop passed — "
          f"anomalies={result['report_data']['anomalies']}")


def test_reporting_n3_negative_cash_flow():
    """Negative cash flow → N3, report NOT sent, hitl_pending."""
    state = _state_with(
        {
            "period": "2026-03",
            "current": _base_current(cash_flow=-5200.00),
            "previous": {"revenue": 85000.00, "expenses": 52000.00},
        },
        "test-rep-n3-cashflow",
    )
    result = reporting_node(state)

    assert result["routing_signal"] == "hitl_pending"
    assert result["report_sent"] is False
    assert result["hitl_pending"] is True
    assert result["report_data"] is not None
    anomaly_text = " ".join(result["report_data"]["anomalies"])
    assert "cash flow" in anomaly_text.lower() or "negative" in anomaly_text.lower()
    assert result["error_log"] == []
    print(f"✅ test_reporting_n3_negative_cash_flow passed — "
          f"anomalies={result['report_data']['anomalies']}")


def test_reporting_n4_data_integrity():
    """revenue - expenses ≠ net_income → N4, routing_signal: unrecognized."""
    state = _state_with(
        {
            "period": "2026-03",
            "current": _base_current(
                revenue=87500.00,
                expenses=54000.00,
                net_income=99999.00,   # deliberately wrong: should be 33500
            ),
            "previous": {"revenue": 85000.00, "expenses": 52000.00},
        },
        "test-rep-n4",
    )
    result = reporting_node(state)

    assert result["routing_signal"] == "unrecognized"
    assert result["report_sent"] is False
    assert result["hitl_pending"] is False
    assert result["report_data"] is not None
    assert len(result["report_data"]["anomalies"]) == 1
    assert "integrity" in result["report_data"]["anomalies"][0].lower()
    assert len(result["error_log"]) == 1
    print(f"✅ test_reporting_n4_data_integrity passed — "
          f"anomaly={result['report_data']['anomalies'][0]}")


def test_reporting_no_data():
    """Empty reporting_input ({}) → no_report_data, nothing written."""
    state = _state_with({}, "test-rep-nodata")
    result = reporting_node(state)

    assert result["routing_signal"] == "no_report_data"
    assert result["report_sent"] is False
    assert result["hitl_pending"] is False
    assert result["report_data"] is None
    assert result["error_log"] == []
    print("✅ test_reporting_no_data passed")


def test_reporting_default_fixture_is_n1():
    """state['reporting_input'] = None → built-in fixture → N1, report sent."""
    state = initial_state("test-rep-fixture")
    # reporting_input is None by default — fixture kicks in
    result = reporting_node(state)

    assert result["routing_signal"] == "completed"
    assert result["report_sent"] is True
    assert result["report_data"] is not None
    assert result["report_data"]["anomalies"] == []
    print(f"✅ test_reporting_default_fixture_is_n1 passed — "
          f"period={result['report_data']['period']}")


if __name__ == "__main__":
    test_reporting_n1_clean()
    test_reporting_n2_expense_spike()
    test_reporting_n3_revenue_drop()
    test_reporting_n3_negative_cash_flow()
    test_reporting_n4_data_integrity()
    test_reporting_no_data()
    test_reporting_default_fixture_is_n1()
    print("\nAll Reporting Agent tests passed.")
