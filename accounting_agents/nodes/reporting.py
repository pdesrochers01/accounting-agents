"""
Reporting Agent node — Financial Reporting (Phase 3).

Responsibilities (UC06):
  1. Fetch QBO P&L, cash flow, AR aging, AP summary for the reporting period:
     REPORTING_MODE=mock: reads state["reporting_input"] if set, else uses fixture.
     REPORTING_MODE=mcp (Phase 4): will query QBO MCP for live data.
  2. Detect anomalies against prior-period baselines:
     Revenue drop > 20%    → N3 (significant — do not send, escalate to HITL)
     Expense spike > 30%   → N2 (minor — flag in report, send anyway)
     Negative cash flow    → N3 (significant)
     AR 60+ bucket > 30% of total AR → N2 (minor)
     revenue - expenses ≠ net_income → N4 (data integrity error → unrecognized)
  3. Act on escalation level:
     N1/N2 → format report, write to hitl_emails/ (mock) or Gmail MCP (Phase 4)
             → routing_signal: "completed", report_sent: True
     N3     → set hitl_pending: True, do NOT send report
             → routing_signal: "hitl_pending"
     N4     → routing_signal: "unrecognized"
  4. Return delta only (never full state).

REPORTING_MODE=mock (default): built-in fixture for clean N1 baseline.
REPORTING_MODE=mcp (Phase 4):  query QBO MCP for live data.

reporting_input dict schema:
  period:   str                  — "YYYY-MM"
  current:  {revenue, expenses, net_income, cash_flow, ar_aging, ap_summary}
  previous: {revenue, expenses}
"""

import json
import os
from datetime import datetime, timezone

from accounting_agents.state import AccountingAgentsState, ARAgingBucket, ReportData

# ── Anomaly thresholds ───────────────────────────────────────────
REVENUE_DROP_THRESHOLD    = 0.20  # >20% drop vs prior period → N3
EXPENSE_SPIKE_THRESHOLD   = 0.30  # >30% increase vs prior period → N2
AR_AGING_60PLUS_THRESHOLD = 0.30  # >30% of total AR in 60+ days → N2

# ── Output directory ─────────────────────────────────────────────
REPORT_DIR = "hitl_emails"

# ── Level priority ───────────────────────────────────────────────
_LEVEL_RANK: dict[str, int] = {"N1": 1, "N2": 2, "N3": 3, "N4": 4}


def _raise_level(current: str, candidate: str) -> str:
    if _LEVEL_RANK.get(candidate, 0) > _LEVEL_RANK.get(current, 0):
        return candidate
    return current


# ── Mock fixture ─────────────────────────────────────────────────

def _default_mock_data() -> dict:
    """Clean N1 baseline fixture — no anomalies."""
    return {
        "period": "2026-03",
        "current": {
            "revenue":    87500.00,
            "expenses":   54000.00,
            "net_income": 33500.00,
            "cash_flow":  29000.00,
            "ar_aging": [
                {"bucket_label": "0-30 days",  "count": 6, "total_cad": 14500.00},
                {"bucket_label": "31-60 days", "count": 2, "total_cad":  4800.00},
                {"bucket_label": "61-90 days", "count": 1, "total_cad":  2100.00},
                {"bucket_label": "90+ days",   "count": 0, "total_cad":     0.00},
            ],
            "ap_summary": {"total_cad": 19200.00, "overdue_count": 1},
        },
        "previous": {
            "revenue":  85000.00,
            "expenses": 52000.00,
        },
    }


def _fetch_reporting_data(state: AccountingAgentsState) -> dict:
    """
    Return raw reporting data.
    None in state  → built-in mock fixture (REPORTING_MODE=mock default)
    {} in state    → explicitly empty; caller will emit no_report_data
    {...} in state → injected data (tests or future MCP result)
    In REPORTING_MODE=mcp, queries QBO MCP (Phase 4).
    """
    mode = os.getenv("REPORTING_MODE", "mock")
    if mode == "mcp":
        raise NotImplementedError("REPORTING_MODE=mcp not implemented — Phase 4")

    injected = state.get("reporting_input")
    return _default_mock_data() if injected is None else injected


# ── Anomaly detection ────────────────────────────────────────────

def _detect_anomalies(current: dict, previous: dict) -> tuple[list[str], str]:
    """
    Compare current-period data against previous-period baselines.
    Returns (anomalies, escalation_level).
    N4 (data integrity) short-circuits — no further checks needed.
    """
    anomalies: list[str] = []
    level = "N1"

    # N4 — data integrity: revenue - expenses must equal net_income (±$0.01)
    expected_net = round(current["revenue"] - current["expenses"], 2)
    actual_net   = round(current["net_income"], 2)
    if abs(expected_net - actual_net) > 0.01:
        anomalies.append(
            f"Data integrity: revenue ${current['revenue']:,.2f} − expenses "
            f"${current['expenses']:,.2f} = ${expected_net:,.2f} "
            f"but net_income = ${actual_net:,.2f}"
        )
        return anomalies, "N4"

    # N3 — revenue drop > 20% vs prior period
    prev_rev = previous.get("revenue", 0.0)
    if prev_rev > 0:
        rev_change = (current["revenue"] - prev_rev) / prev_rev
        if rev_change < -REVENUE_DROP_THRESHOLD:
            anomalies.append(
                f"Revenue drop: {abs(rev_change) * 100:.1f}% vs prior period "
                f"(${prev_rev:,.2f} → ${current['revenue']:,.2f} CAD)"
            )
            level = _raise_level(level, "N3")

    # N3 — negative cash flow
    if current["cash_flow"] < 0:
        anomalies.append(
            f"Negative cash flow: ${current['cash_flow']:,.2f} CAD"
        )
        level = _raise_level(level, "N3")

    # N2 — expense spike > 30% vs prior period
    prev_exp = previous.get("expenses", 0.0)
    if prev_exp > 0:
        exp_change = (current["expenses"] - prev_exp) / prev_exp
        if exp_change > EXPENSE_SPIKE_THRESHOLD:
            anomalies.append(
                f"Expense spike: {exp_change * 100:.1f}% vs prior period "
                f"(${prev_exp:,.2f} → ${current['expenses']:,.2f} CAD)"
            )
            level = _raise_level(level, "N2")

    # N2 — AR aging shift: 60+ day buckets > 30% of total AR
    ar_aging: list[dict] = current.get("ar_aging", [])
    total_ar = sum(b.get("total_cad", 0.0) for b in ar_aging)
    if total_ar > 0:
        over_60 = sum(
            b.get("total_cad", 0.0) for b in ar_aging
            if any(tag in b.get("bucket_label", "") for tag in ("61", "90+"))
        )
        ratio = over_60 / total_ar
        if ratio > AR_AGING_60PLUS_THRESHOLD:
            anomalies.append(
                f"AR aging shift: {ratio * 100:.1f}% of total AR "
                f"(${over_60:,.2f} CAD) is 60+ days overdue"
            )
            level = _raise_level(level, "N2")

    return anomalies, level


# ── Report formatter ─────────────────────────────────────────────

def _format_report(data: ReportData) -> str:
    lines = [
        f"=== AccountingAgents Financial Report — {data['period']} ===",
        "",
        "INCOME STATEMENT (CAD)",
        f"  Revenue:     ${data['revenue']:>12,.2f}",
        f"  Expenses:    ${data['expenses']:>12,.2f}",
        f"  Net Income:  ${data['net_income']:>12,.2f}",
        "",
        "CASH FLOW",
        f"  Net Cash Flow: ${data['cash_flow']:,.2f} CAD",
        "",
        "AR AGING",
    ]
    for bucket in data["ar_aging"]:
        lines.append(
            f"  {bucket['bucket_label']:<12} "
            f"{bucket['count']:>2} invoice(s)   ${bucket['total_cad']:>9,.2f} CAD"
        )
    lines += [
        "",
        "AP SUMMARY",
        f"  Total Payable:  ${data['ap_summary']['total_cad']:,.2f} CAD",
        f"  Overdue Count:  {data['ap_summary']['overdue_count']}",
        "",
    ]
    if data["anomalies"]:
        lines.append(f"ANOMALY FLAGS ({len(data['anomalies'])} detected)")
        for anomaly in data["anomalies"]:
            lines.append(f"  ⚠  {anomaly}")
    else:
        lines.append("ANOMALY FLAGS  None detected — all metrics within normal range.")
    lines += [
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} UTC",
    ]
    return "\n".join(lines)


# ── Report dispatch ──────────────────────────────────────────────

def _send_report_mock(data: ReportData, formatted: str) -> str:
    """Write report to hitl_emails/ as JSON + plain text. Returns filename."""
    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = f"{REPORT_DIR}/report_{data['period']}.json"
    payload = {
        "type": "financial_report",
        "period": data["period"],
        "report_data": dict(data),
        "formatted_text": formatted,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return filename


def _dispatch_report(data: ReportData, formatted: str) -> str:
    """Dispatch report — mock writes to file; gmail mode calls Gmail MCP."""
    hitl_mode = os.getenv("HITL_MODE", "mock")
    if hitl_mode in ("mock", ""):
        return _send_report_mock(data, formatted)
    raise NotImplementedError(
        f"HITL_MODE={hitl_mode!r} not supported for reports — Phase 4"
    )


# ── Main node ────────────────────────────────────────────────────

def reporting_node(state: AccountingAgentsState) -> dict:
    """
    Reporting Agent node.
    Fetches QBO data, detects anomalies, and dispatches the report.
    Returns delta only — never the full state.
    """
    error_log = list(state.get("error_log", []))

    raw = _fetch_reporting_data(state)

    if not raw:
        print("[reporting_node] No reporting data available.")
        return {
            "routing_signal": "no_report_data",
            "report_data": None,
            "report_sent": False,
            "hitl_pending": False,
            "error_log": error_log,
        }

    period   = raw.get("period", "unknown")
    current  = raw.get("current", {})
    previous = raw.get("previous", {})

    anomalies, level = _detect_anomalies(current, previous)

    # Build ReportData regardless of escalation — it is always stored in state
    ar_aging_buckets: list[ARAgingBucket] = [
        ARAgingBucket(
            bucket_label=b["bucket_label"],
            count=b["count"],
            total_cad=b["total_cad"],
        )
        for b in current.get("ar_aging", [])
    ]

    report = ReportData(
        period=period,
        revenue=current.get("revenue", 0.0),
        expenses=current.get("expenses", 0.0),
        net_income=current.get("net_income", 0.0),
        cash_flow=current.get("cash_flow", 0.0),
        ar_aging=ar_aging_buckets,
        ap_summary=current.get("ap_summary", {"total_cad": 0.0, "overdue_count": 0}),
        anomalies=anomalies,
    )

    print(f"[reporting_node] Period: {period} | Level: {level} | "
          f"Anomalies: {len(anomalies)}")

    # N4 — data integrity error
    if level == "N4":
        print(f"[reporting_node] DATA INTEGRITY ERROR: {anomalies[0]}")
        return {
            "routing_signal": "unrecognized",
            "report_data": report,
            "report_sent": False,
            "hitl_pending": False,
            "error_log": error_log + [f"[reporting_node] N4: {anomalies[0]}"],
        }

    # N3 — significant anomaly: escalate, do not send
    if level == "N3":
        for a in anomalies:
            print(f"[reporting_node] N3 anomaly: {a}")
        return {
            "routing_signal": "hitl_pending",
            "report_data": report,
            "report_sent": False,
            "hitl_pending": True,
            "error_log": error_log,
        }

    # N1/N2 — format and send
    for a in anomalies:
        print(f"[reporting_node] N2 flag: {a}")

    formatted = _format_report(report)
    filename  = _dispatch_report(report, formatted)

    print(f"[reporting_node] Report {'sent' if not anomalies else 'sent with flags'} "
          f"→ {filename}")

    return {
        "routing_signal": "completed",
        "report_data": report,
        "report_sent": True,
        "hitl_pending": False,
        "error_log": error_log,
    }
