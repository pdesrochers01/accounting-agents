"""
scripts/demo_end_to_end.py — End-to-end narrative demo for AccountingAgents Phase 2.

Tells the full story of Marie Lafleur processing a bank reconciliation
for Entreprises Beaumont Inc., from email detection to HITL decision on iPhone.

Usage:
    # Dry-run: Acts 1-3 only (no Gmail, no graph)
    PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py --dry-run

    # Full demo (requires FastAPI server on port 5001 + ngrok configured in .env):
    PYTHONPATH=. .venv/bin/python scripts/demo_end_to_end.py
"""

import argparse
import asyncio
import io
import os
import sqlite3
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

load_dotenv()

os.environ["QBO_MODE"] = "mcp"

# Reconciliation functions used directly for Acts 2-3 display
from accounting_agents.nodes.reconciliation import (
    _compare_with_bank_statement,
    _fetch_qbo_bills_mcp,
    N3_THRESHOLD,
)

# console uses original stdout; stdout redirects during graph.invoke() won't affect it
console = Console()

# --- Demo persona and context ---
CABINET = "Lafleur CPA Firm"
CLIENT = "Entreprises Beaumont Inc."
TASK = "Bank Reconciliation March 2026"
ANALYST = "Marie Lafleur"
WEBHOOK_URL = "http://localhost:5001"
# Same DB as webhook.py so polling sees webhook updates
DB_PATH = "accounting_agents.db"

# Polling constants for Act 5
MAX_WAIT_SECONDS = 120
# All three are valid terminal decisions — "modify" loops at the app level but
# reconciliation_node exits immediately when hitl_comment is set (CLAUDE.md Known Fixes).
TERMINAL_DECISIONS = frozenset({"approve", "block", "modify", "timeout"})

BANK_STATEMENT = [
    {
        "entry_id": "bnq-2026-03-001",
        "date": "2026-03-05",
        "vendor_or_client": "Fournisseur Général Inc.",
        "amount": 1200.00,
    },
    {
        "entry_id": "bnq-2026-03-002",
        "date": "2026-03-10",
        "vendor_or_client": "Vidéotron",
        "amount": 185.00,
    },
    {
        "entry_id": "bnq-2026-03-003",
        "date": "2026-03-15",
        "vendor_or_client": "Bell Canada",
        "amount": 320.00,
    },
    {
        "entry_id": "bnq-2026-03-004",
        "date": "2026-03-22",
        "vendor_or_client": "Hydro-Québec",
        "amount": 4900.00,  # QBO has $2,450.00 → delta $2,450.00 → N3
    },
]

RAW_TEXT = (
    "Bank Statement — National Bank of Canada\n"
    "Period: March 2026\n"
    "Client: Entreprises Beaumont Inc.\n"
    "Accountant: Marie Lafleur\n"
    "Balance: $4,152.44 CAD\n"
    "Date: 2026-03-31"
)


def _check_webhook() -> bool:
    try:
        with urllib.request.urlopen(f"{WEBHOOK_URL}/health", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _suppress_stdout_invoke(graph, state: dict, config: dict) -> dict:
    """Run graph.invoke() with stdout redirected so app print() calls don't corrupt rich output."""
    _old = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return graph.invoke(state, config=config)
    finally:
        sys.stdout = _old


# ── Act 1 ────────────────────────────────────────────────────────

def act1_email_detection() -> None:
    """Narrative-only — simulates Gmail detection and ingestion classification."""
    console.print()
    console.print(Panel(
        f"[bold white]{CABINET}[/bold white]\n"
        f"Client  : [cyan]{CLIENT}[/cyan]\n"
        f"Task    : [cyan]{TASK}[/cyan]\n"
        f"Lead    : [cyan]{ANALYST}[/cyan]",
        title="[bold blue]AccountingAgents — Phase 2 Demo[/bold blue]",
        subtitle="[dim]QBO MCP  ·  Gmail HITL[/dim]",
        border_style="blue",
        padding=(1, 4),
    ))

    console.print()
    console.print(Panel(
        "[bold blue]ACT 1 — Document Detection        [Ingestion Agent][/bold blue]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()
    time.sleep(0.5)

    console.print("  [dim]•[/dim] Gmail surveillance active — [dim]pdesrochers01@gmail.com[/dim]")
    time.sleep(0.8)
    console.print("  [green]✓[/green] [bold]New email detected[/bold] — BNC bank statement March 2026")
    console.print("    From    : [dim]services.bancaires@bnc.ca[/dim]")
    console.print("    Subject : Account Statement — Entreprises Beaumont Inc. — March 2026")
    console.print("    File    : [dim]releve_bnq_mars2026.pdf (48 KB)[/dim]")
    time.sleep(1)

    console.print()
    console.print("  [dim]→[/dim]  Ingestion Agent — classification in progress...")
    time.sleep(0.8)
    console.print("  [green]✓[/green] Document type: [bold]bank_statement[/bold]")
    console.print(
        "    Period   : March 2026  |  Currency : CAD  "
        "|  Client  : Entreprises Beaumont Inc."
    )
    time.sleep(2)


# ── Act 2 ────────────────────────────────────────────────────────

def act2_qbo_fetch() -> list[dict]:
    """Real QBO MCP fetch — displays results in a rich Table."""
    console.print()
    console.print(Panel(
        "[bold blue]ACT 2 — QuickBooks Query          [Reconciliation Agent][/bold blue]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()

    bills: list[dict] = []
    with console.status(
        "[cyan]Reconciliation Agent — querying QuickBooks Online...[/cyan]",
        spinner="dots",
    ):
        _old = sys.stdout
        sys.stdout = io.StringIO()
        try:
            try:
                bills = asyncio.run(_fetch_qbo_bills_mcp())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    bills = loop.run_until_complete(_fetch_qbo_bills_mcp())
                finally:
                    loop.close()
        finally:
            sys.stdout = _old

    cad_bills = [b for b in bills if b.get("currency") == "CAD"]
    other_bills = [b for b in bills if b.get("currency") != "CAD"]

    console.print(
        f"  [green]✓[/green] {len(bills)} bills fetched from QBO Sandbox "
        f"([white]{len(cad_bills)} CAD[/white], [dim]{len(other_bills)} foreign currency[/dim])"
    )
    console.print()

    table = Table(
        title=f"QBO Bills — {CLIENT}",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Vendor", style="white", min_width=32)
    table.add_column("Amount", justify="right", style="white")
    table.add_column("Currency", justify="center")
    table.add_column("Date", style="dim")

    for bill in cad_bills:
        table.add_row(
            bill["vendor_name"],
            f"${bill['amount']:,.2f}",
            "[white]CAD[/white]",
            bill["date"],
        )
    for bill in other_bills:
        table.add_row(
            bill["vendor_name"],
            f"${bill['amount']:,.2f}",
            f"[dim]{bill['currency']}[/dim]",
            bill["date"],
        )

    console.print(table)

    if other_bills:
        console.print(
            f"  [dim]* {len(other_bills)} bill(s) in foreign currency "
            "excluded from CAD reconciliation[/dim]"
        )

    time.sleep(2)
    return bills


# ── Act 3 ────────────────────────────────────────────────────────

def act3_gap_detection(bills: list[dict]) -> list:
    """Real gap detection — animated line by line, N3 highlighted in bold red."""
    console.print()
    console.print(Panel(
        "[bold blue]ACT 3 — Gap Detection             [Reconciliation Agent][/bold blue]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()
    console.print("  [dim]Line-by-line analysis of BNC statement — March 2026...[/dim]")
    console.print()

    vendor_map = {
        b["vendor_name"].lower(): b
        for b in bills
        if b.get("currency") == "CAD"
    }

    for entry in BANK_STATEMENT:
        vendor = entry["vendor_or_client"]
        bank_amount = entry["amount"]
        time.sleep(0.5)

        qbo_bill = vendor_map.get(vendor.lower())
        if qbo_bill:
            qbo_amount = qbo_bill["amount"]
            delta = bank_amount - qbo_amount
            if abs(delta) < 0.01:
                console.print(
                    f"  [green]✓[/green]  {vendor:<26}  ${bank_amount:>9,.2f} CAD  — match"
                )
            elif abs(delta) >= N3_THRESHOLD:
                console.print(
                    f"  [bold red]✗[/bold red]  [bold red]{vendor:<26}"
                    f"  ${bank_amount:>9,.2f} CAD"
                    f"  — GAP ${abs(delta):,.2f} CAD (N3)[/bold red]"
                )
            else:
                console.print(
                    f"  [yellow]~[/yellow]  {vendor:<26}  ${bank_amount:>9,.2f} CAD  "
                    f"— gap ${abs(delta):,.2f} CAD"
                )
        else:
            console.print(
                f"  [yellow]?[/yellow]  {vendor:<26}  ${bank_amount:>9,.2f} CAD  — not in QBO"
            )

    gaps = _compare_with_bank_statement(bills, BANK_STATEMENT)
    n3_gaps = [g for g in gaps if g["escalation_level"] == "N3"]

    time.sleep(1)
    console.print()

    if n3_gaps:
        gap = n3_gaps[0]
        console.print(Panel(
            f"[bold red]DISCREPANCY DETECTED — {gap['vendor_or_client']}[/bold red]\n\n"
            f"  Expected  (QBO)  : [white]${gap['expected_amount']:,.2f} CAD[/white]\n"
            f"  Actual    (BNC)  : [white]${gap['actual_amount']:,.2f} CAD[/white]\n"
            f"  [bold red]Difference       : ${abs(gap['delta']):,.2f} CAD[/bold red]\n\n"
            "[bold red]N3 threshold exceeded → HUMAN APPROVAL REQUIRED[/bold red]",
            title="[bold red]⚠  Reconciliation Alert[/bold red]",
            border_style="red",
        ))
    else:
        console.print("  [green]✓[/green] No significant discrepancy detected.")

    time.sleep(2)
    return gaps


# ── Act 4 ────────────────────────────────────────────────────────

def act4_hitl_interrupt(
    state: dict,
    graph,
    config: dict,
    thread_id: str,
) -> None:
    """Run graph.invoke() — ingestion → reconciliation (QBO) → hitl (Gmail + interrupt)."""
    console.print()
    console.print(Panel(
        "[bold yellow]ACT 4 — HITL Interrupt            [Supervisor + HITL Node][/bold yellow]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()
    console.print(
        "  [yellow]⚡[/yellow] [bold]Graph interrupted[/bold] — human decision required"
    )
    time.sleep(0.5)

    # graph.invoke runs: ingestion → reconciliation (QBO MCP) → hitl Phase A (Gmail + interrupt())
    with console.status(
        "[cyan]Sending Gmail notification to Marie Lafleur...[/cyan]",
        spinner="dots",
    ):
        _suppress_stdout_invoke(graph, state, config)

    notify_email = os.getenv("HITL_NOTIFY_EMAIL", "accountant@example.com")
    console.print(f"  [green]✓[/green] [bold]Gmail sent[/bold] → {notify_email}")
    console.print(f"  Thread ID : [dim]{thread_id}[/dim]")
    console.print()
    console.print("  [yellow]⏳ Awaiting decision on iPhone...[/yellow]")


# ── Act 5 ────────────────────────────────────────────────────────

def act5_wait_decision(
    graph,
    config: dict,
    start_time: float,
    thread_id: str,
) -> None:
    """Poll LangGraph checkpointer directly for HITL decision with a live elapsed timer.

    Reads state from SQLite on every tick — uvicorn eliminates auto-reloader issues.
    Exits as soon as any terminal decision arrives or after MAX_WAIT_SECONDS.
    "modify" is treated as terminal: reconciliation_node short-circuits on hitl_comment
    (CLAUDE.md Known Fixes), so no re-escalation loop occurs.
    """
    console.print()
    console.print(Panel(
        "[bold yellow]ACT 5 — Awaiting Decision         [HITL Node + Webhook][/bold yellow]",
        border_style="dim",
        padding=(0, 2),
    ))
    console.print()

    decision = None
    timed_out = False

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            elapsed = time.time() - start_time
            remaining = MAX_WAIT_SECONDS - int(elapsed)

            if remaining <= 0:
                timed_out = True
                break

            mins, secs = divmod(int(elapsed), 60)
            live.update(Text.from_markup(
                f"  [yellow]⏳[/yellow]  Awaiting decision on iPhone...  "
                f"[bold yellow]{mins:02d}:{secs:02d}[/bold yellow]"
                f"  [dim](timeout in {remaining}s)[/dim]"
            ))

            # Read from SQLite checkpointer directly — not from FastAPI server in-memory state
            graph_state = graph.get_state(config)
            decision = graph_state.values.get("hitl_decision")
            if decision in TERMINAL_DECISIONS:
                break

            time.sleep(1)

    elapsed = time.time() - start_time

    if timed_out:
        console.print()
        console.print(Panel(
            f"[yellow]No decision received after {MAX_WAIT_SECONDS} seconds.[/yellow]\n\n"
            "Possible causes:\n"
            "  • FastAPI server not running — restart the demo\n"
            "  • Gmail notification not received — check inbox\n"
            "  • ngrok URL expired — update HITL_WEBHOOK_BASE_URL in .env\n\n"
            f"[dim]Thread ID: {thread_id}[/dim]",
            title="[yellow]Timeout — demo interrupted[/yellow]",
            border_style="yellow",
        ))
        return

    decision_color = (
        "green" if decision == "approve" else ("red" if decision == "block" else "yellow")
    )
    decision_label = {
        "approve": "APPROVED ✓",
        "block": "BLOCKED ✗",
        "modify": "MODIFIED ~",
        "timeout": "TIMEOUT ⏰",
    }.get(decision, decision.upper())

    console.print()
    console.print(Panel(
        f"  Decision maker : [white]{ANALYST}[/white]\n"
        f"  Decision       : [{decision_color}][bold]{decision_label}[/bold][/{decision_color}]\n"
        f"  Timestamp      : [white]"
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')} UTC[/white]\n"
        f"  Thread ID      : [dim]{thread_id}[/dim]",
        title=f"[{decision_color}]HITL Decision Received[/{decision_color}]",
        border_style=decision_color,
    ))

    mins, secs = divmod(int(elapsed), 60)
    time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    console.print()
    console.print(Panel(
        f"[green]⏱  Total time: {time_str}[/green]\n"
        "[dim]   Without AccountingAgents: ~2 hours[/dim]\n\n"
        "[bold green]🎯  File submitted for audit[/bold green]",
        title="[green]ACT 6 — Resolution                [Supervisor][/green]",
        border_style="green",
        padding=(1, 4),
    ))


# ── Entry point ──────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AccountingAgents End-to-End Demo — bank reconciliation Phase 2"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute Acts 1-3 only — no Gmail, no graph",
    )
    args = parser.parse_args()

    if not args.dry_run:
        console.print("[dim]Checking FastAPI webhook (port 5001)...[/dim]", end=" ")
        if not _check_webhook():
            console.print()
            console.print(Panel(
                "[red]Error: FastAPI server not available on port 5001.[/red]\n\n"
                "Start the webhook server before running the demo:\n"
                "  [bold]PYTHONPATH=. .venv/bin/python accounting_agents/webhook.py[/bold]\n\n"
                "Expose via ngrok (URL in .env → HITL_WEBHOOK_BASE_URL):\n"
                "  [bold]ngrok http 5001[/bold]",
                title="[red]Missing prerequisite[/red]",
                border_style="red",
            ))
            sys.exit(1)
        console.print("[green]OK[/green]")

    act1_email_detection()
    bills = act2_qbo_fetch()
    gaps = act3_gap_detection(bills)

    if args.dry_run:
        console.print()
        console.print(Panel(
            "[green]Acts 1-3 validated — no errors[/green]\n"
            "[dim]Dry-run mode: Gmail and graph not executed[/dim]",
            title="[green]Dry-run complete[/green]",
            border_style="green",
        ))
        return

    # Acts 4-5 require the full graph with the same DB as webhook.py
    from langgraph.checkpoint.sqlite import SqliteSaver
    from accounting_agents.graph import build_graph
    from accounting_agents.state import initial_state

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    graph = build_graph(checkpointer)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state = initial_state(thread_id)
    state["input_document"] = {
        "raw_text": RAW_TEXT,
        "source_email_id": "gmail-bnq-march-2026",
        "filename": "releve_bnq_mars2026.pdf",
        "qbo_transactions": [],       # unused in QBO_MODE=mcp
        "bank_statement": BANK_STATEMENT,
    }

    start_time = time.time()
    act4_hitl_interrupt(state, graph, config, thread_id)
    act5_wait_decision(graph, config, start_time, thread_id)


if __name__ == "__main__":
    main()
