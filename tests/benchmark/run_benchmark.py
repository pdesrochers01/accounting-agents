"""
AccountingAgents benchmark runner.

Runs 65 test cases across three agents (Ingestion, Reconciliation, AP)
in offline/mock mode. No LLM calls, no QBO MCP, no Gmail.

Usage:
  PYTHONPATH=. CLASSIFICATION_MODE=keyword QBO_MODE=mock \
    AP_MODE=mock AR_MODE=mock \
    .venv/bin/python tests/benchmark/run_benchmark.py
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("CLASSIFICATION_MODE", "keyword")
os.environ.setdefault("QBO_MODE", "mock")
os.environ.setdefault("AP_MODE", "mock")
os.environ.setdefault("AR_MODE", "mock")

from accounting_agents.state import initial_state, APAction
from accounting_agents.nodes.ingestion import ingestion_node
from accounting_agents.nodes.reconciliation import reconciliation_node
from accounting_agents.nodes.ap import ap_node

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── Dataset loaders ──────────────────────────────────────────────

def load_dataset(filename: str) -> list[dict]:
    path = BENCHMARK_DIR / filename
    with open(path) as f:
        return json.load(f)


# ── Ingestion benchmark ──────────────────────────────────────────

def run_ingestion(cases: list[dict]) -> dict:
    results = []
    for case in cases:
        state = initial_state("benchmark-ing")
        state["input_document"] = {
            "raw_text": case["content"],
            "source_email_id": "",
            "filename": case["id"],
        }

        try:
            delta = ingestion_node(state)
        except Exception as exc:
            results.append({
                "id": case["id"],
                "description": case["description"],
                "predicted_doc_type": "ERROR",
                "predicted_routing": "ERROR",
                "expected_doc_type": case["ground_truth"]["document_type"],
                "expected_routing": case["ground_truth"]["routing_signal"],
                "correct": False,
                "error": str(exc),
            })
            continue

        routing = delta.get("routing_signal", "unrecognized")
        docs = delta.get("documents_ingested", [])

        if routing == "unrecognized" or not docs:
            predicted_doc_type = "unrecognized"
        else:
            predicted_doc_type = docs[-1].get("document_type", "unrecognized")

        expected_doc_type = case["ground_truth"]["document_type"]
        expected_routing = case["ground_truth"]["routing_signal"]

        routing_ok = routing == expected_routing
        doctype_ok = predicted_doc_type == expected_doc_type
        correct = routing_ok and doctype_ok

        results.append({
            "id": case["id"],
            "description": case["description"],
            "predicted_doc_type": predicted_doc_type,
            "predicted_routing": routing,
            "expected_doc_type": expected_doc_type,
            "expected_routing": expected_routing,
            "correct": correct,
        })

    return _ingestion_metrics(results)


def _ingestion_metrics(results: list[dict]) -> dict:
    classes = [
        "bank_statement", "supplier_invoice", "client_invoice",
        "tax_document", "onboarding_form", "unrecognized",
    ]

    tp: dict[str, int] = {c: 0 for c in classes}
    fp: dict[str, int] = {c: 0 for c in classes}
    fn: dict[str, int] = {c: 0 for c in classes}

    for r in results:
        pred = r["predicted_doc_type"]
        actual = r["expected_doc_type"]
        if pred == actual:
            tp[actual] = tp.get(actual, 0) + 1
        else:
            fp[pred] = fp.get(pred, 0) + 1
            fn[actual] = fn.get(actual, 0) + 1

    per_class = {}
    for c in classes:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
        r_ = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
        f1 = 2 * p * r_ / (p + r_) if (p + r_) > 0 else 0.0
        per_class[c] = {"precision": round(p, 3), "recall": round(r_, 3), "f1": round(f1, 3)}

    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    routing_correct = sum(1 for r in results if r["predicted_routing"] == r["expected_routing"])

    return {
        "agent": "ingestion",
        "results": results,
        "total": total,
        "correct": correct,
        "routing_correct": routing_correct,
        "accuracy": round(correct / total, 4) if total else 0,
        "per_class": per_class,
    }


# ── Reconciliation benchmark ─────────────────────────────────────

def run_reconciliation(cases: list[dict]) -> dict:
    results = []
    for case in cases:
        state = initial_state("benchmark-rec")

        bank_statement = [
            {
                "entry_id": str(i),
                "date": tx["date"],
                "vendor_or_client": tx["description"],
                "amount": tx["amount"],
            }
            for i, tx in enumerate(case["bank_transactions"])
        ]
        qbo_transactions = [
            {
                "transaction_id": str(i),
                "date": bill["date"],
                "vendor_or_client": bill["vendor"],
                "amount": bill["amount"],
                "document_number": "",
            }
            for i, bill in enumerate(case["qbo_bills"])
        ]

        dummy_doc = {
            "document_id": "benchmark",
            "document_type": "bank_statement",
            "date": "2026-03-15",
            "amount": 0.0,
            "currency": "CAD",
            "vendor_or_client": "benchmark",
            "document_number": "BENCH-REC",
            "qbo_entry_id": "",
            "source_email_id": "",
            "qbo_transactions": qbo_transactions,
            "bank_statement": bank_statement,
        }
        state["documents_ingested"] = [dummy_doc]

        try:
            delta = reconciliation_node(state)
        except Exception as exc:
            results.append({
                "id": case["id"],
                "description": case["description"],
                "predicted_routing": "ERROR",
                "predicted_gap": 0.0,
                "expected_routing": case["ground_truth"]["routing_signal"],
                "expected_gap": case["ground_truth"]["gap_amount"],
                "expected_escalation": case["ground_truth"]["escalation_level"],
                "correct": False,
                "error": str(exc),
            })
            continue

        routing = delta.get("routing_signal", "")
        gaps = delta.get("reconciliation_gaps", [])
        predicted_gap = round(sum(abs(g["delta"]) for g in gaps), 2)

        expected_routing = case["ground_truth"]["routing_signal"]
        expected_gap = case["ground_truth"]["gap_amount"]

        routing_ok = routing == expected_routing
        gap_ok = abs(predicted_gap - expected_gap) < 0.02
        correct = routing_ok and gap_ok

        results.append({
            "id": case["id"],
            "description": case["description"],
            "predicted_routing": routing,
            "predicted_gap": predicted_gap,
            "expected_routing": expected_routing,
            "expected_gap": expected_gap,
            "expected_escalation": case["ground_truth"]["escalation_level"],
            "correct": correct,
        })

    correct_count = sum(1 for r in results if r["correct"])
    total = len(results)
    gap_errors = [abs(r["predicted_gap"] - r["expected_gap"]) for r in results]
    mae = round(sum(gap_errors) / len(gap_errors), 2) if gap_errors else 0.0

    return {
        "agent": "reconciliation",
        "results": results,
        "total": total,
        "correct": correct_count,
        "accuracy": round(correct_count / total, 4) if total else 0,
        "gap_mae": mae,
    }


# ── AP benchmark ─────────────────────────────────────────────────

def run_ap(cases: list[dict]) -> dict:
    results = []
    levels = ["N1", "N2", "N3", "N4"]
    # confusion[predicted][actual]
    confusion: dict[str, dict[str, int]] = {
        lvl: {k: 0 for k in levels} for lvl in levels
    }

    for case in cases:
        bill = case["bill"]
        state = initial_state("benchmark-ap")

        if bill.get("is_duplicate"):
            prior = APAction(
                action_id=str(uuid.uuid4()),
                document_id="prior-bench",
                vendor=bill["vendor_name"],
                amount=bill["amount_cad"],
                decision="auto_approved",
                escalation_level="N1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes="Prior action injected for duplicate detection test.",
            )
            state["ap_actions"] = [prior]

        prior_count = len(state.get("ap_actions", []))

        ingested_doc = {
            "document_id": str(uuid.uuid4()),
            "document_type": "supplier_invoice",
            "date": bill["invoice_date"],
            "amount": bill["amount_cad"],
            "currency": "CAD",
            "vendor_or_client": bill["vendor_name"],
            "document_number": bill["invoice_number"],
            "qbo_entry_id": "",
            "source_email_id": "",
        }
        state["documents_ingested"] = [ingested_doc]

        try:
            delta = ap_node(state)
        except Exception as exc:
            results.append({
                "id": case["id"],
                "description": case["description"],
                "predicted_escalation": "ERROR",
                "predicted_routing": "ERROR",
                "expected_escalation": case["ground_truth"]["escalation_level"],
                "expected_routing": case["ground_truth"]["routing_signal"],
                "correct": False,
                "error": str(exc),
            })
            continue

        all_actions = delta.get("ap_actions", [])
        new_actions = all_actions[prior_count:]
        routing = delta.get("routing_signal", "completed")

        predicted_escalation = new_actions[0]["escalation_level"] if new_actions else "N1"
        expected_escalation = case["ground_truth"]["escalation_level"]
        expected_routing = case["ground_truth"]["routing_signal"]

        escalation_ok = predicted_escalation == expected_escalation
        routing_ok = routing == expected_routing
        correct = escalation_ok and routing_ok

        if predicted_escalation in levels and expected_escalation in levels:
            confusion[predicted_escalation][expected_escalation] += 1

        results.append({
            "id": case["id"],
            "description": case["description"],
            "predicted_escalation": predicted_escalation,
            "predicted_routing": routing,
            "expected_escalation": expected_escalation,
            "expected_routing": expected_routing,
            "correct": correct,
        })

    correct_count = sum(1 for r in results if r["correct"])
    total = len(results)

    return {
        "agent": "ap",
        "results": results,
        "total": total,
        "correct": correct_count,
        "accuracy": round(correct_count / total, 4) if total else 0,
        "confusion": confusion,
    }


# ── Report generation ────────────────────────────────────────────

def collect_failures(all_metrics: list[dict]) -> list[dict]:
    failures = []
    for m in all_metrics:
        for r in m["results"]:
            if not r.get("correct"):
                if m["agent"] == "ingestion":
                    failures.append({
                        "id": r["id"],
                        "expected": f"{r['expected_doc_type']} / {r['expected_routing']}",
                        "got": f"{r['predicted_doc_type']} / {r['predicted_routing']}",
                    })
                elif m["agent"] == "reconciliation":
                    failures.append({
                        "id": r["id"],
                        "expected": f"{r['expected_escalation']} / {r['expected_routing']} / gap ${r['expected_gap']:.2f}",
                        "got": f"- / {r['predicted_routing']} / gap ${r['predicted_gap']:.2f}",
                    })
                elif m["agent"] == "ap":
                    failures.append({
                        "id": r["id"],
                        "expected": f"{r['expected_escalation']} / {r['expected_routing']}",
                        "got": f"{r['predicted_escalation']} / {r['predicted_routing']}",
                    })
    return failures


def write_json_results(all_metrics: list[dict], generated_at: str) -> None:
    payload = {
        "generated_at": generated_at,
        "agents": {m["agent"]: m for m in all_metrics},
    }
    out = RESULTS_DIR / "benchmark_results.json"
    with open(out, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\n[benchmark] JSON results → {out}")


def write_md_report(all_metrics: list[dict], generated_at: str) -> None:
    ing = next(m for m in all_metrics if m["agent"] == "ingestion")
    rec = next(m for m in all_metrics if m["agent"] == "reconciliation")
    ap_ = next(m for m in all_metrics if m["agent"] == "ap")

    total_correct = ing["correct"] + rec["correct"] + ap_["correct"]
    total_cases = ing["total"] + rec["total"] + ap_["total"]
    mean_acc = round(total_correct / total_cases * 100, 1) if total_cases else 0

    failures = collect_failures(all_metrics)

    lines = [
        "# AccountingAgents — Benchmark Report",
        f"Generated: {generated_at}",
        f"Dataset: {total_cases} test cases | Mode: CLASSIFICATION_MODE=keyword | No API calls",
        "",
        "---",
        "",
        f"## Ingestion Agent ({ing['total']} cases)",
        f"Routing accuracy: {ing['routing_correct']}/{ing['total']} "
        f"({ing['routing_correct'] / ing['total'] * 100:.1f}%)",
        f"Full accuracy (routing + doc type): {ing['correct']}/{ing['total']} "
        f"({ing['accuracy'] * 100:.1f}%)",
        "",
        "| Class            | Precision | Recall | F1   |",
        "|------------------|-----------|--------|------|",
    ]

    for cls, v in ing["per_class"].items():
        lines.append(f"| {cls:<16}  | {v['precision']:.2f}      | {v['recall']:.2f}   | {v['f1']:.2f} |")

    lines += [
        "",
        "---",
        "",
        f"## Reconciliation Agent ({rec['total']} cases)",
        f"Escalation accuracy: {rec['correct']}/{rec['total']} ({rec['accuracy'] * 100:.1f}%)",
        f"Gap precision: mean absolute error ${rec['gap_mae']:.2f} CAD",
        "",
        "---",
        "",
        f"## AP Agent ({ap_['total']} cases)",
        f"Escalation accuracy: {ap_['correct']}/{ap_['total']} ({ap_['accuracy'] * 100:.1f}%)",
        "",
        "Confusion matrix (rows=predicted, cols=actual):",
        "```",
        "         N1   N2   N3   N4",
    ]

    for pred in ["N1", "N2", "N3", "N4"]:
        row = ap_["confusion"][pred]
        cells = "  ".join(f"{row[act]:2d}" for act in ["N1", "N2", "N3", "N4"])
        lines.append(f"pred {pred}  [{cells}]")

    lines += [
        "```",
        "",
        "---",
        "",
        "## Overall",
        f"Mean accuracy: {mean_acc}%",
        f"Total: {total_correct}/{total_cases} correct",
        "",
    ]

    if failures:
        lines += [
            "## Failed Cases",
            "| ID        | Expected                              | Got                                   |",
            "|-----------|---------------------------------------|---------------------------------------|",
        ]
        for f in failures:
            lines.append(f"| {f['id']:<9} | {f['expected']:<37} | {f['got']:<37} |")
    else:
        lines.append("## Failed Cases\nNone — perfect score!")

    lines.append("")
    report = "\n".join(lines)

    out = RESULTS_DIR / "benchmark_report.md"
    with open(out, "w") as f:
        f.write(report)
    print(f"[benchmark] Markdown report → {out}")


# ── Rich console output ──────────────────────────────────────────

def print_rich_summary(all_metrics: list[dict]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
    except ImportError:
        print("\n[benchmark] rich not available — skipping table output")
        return

    console = Console()

    ing = next(m for m in all_metrics if m["agent"] == "ingestion")
    rec = next(m for m in all_metrics if m["agent"] == "reconciliation")
    ap_ = next(m for m in all_metrics if m["agent"] == "ap")

    total_correct = ing["correct"] + rec["correct"] + ap_["correct"]
    total_cases = ing["total"] + rec["total"] + ap_["total"]
    mean_acc = total_correct / total_cases * 100 if total_cases else 0

    console.print()
    console.rule("[bold cyan]AccountingAgents — Benchmark Results[/bold cyan]")
    console.print()

    # Agent summary table
    summary = Table(box=box.ROUNDED, title="Agent Summary", show_lines=True)
    summary.add_column("Agent", style="bold")
    summary.add_column("Correct", justify="center")
    summary.add_column("Total", justify="center")
    summary.add_column("Accuracy", justify="center")
    summary.add_column("Notes")

    ing_acc = ing["accuracy"] * 100
    rec_acc = rec["accuracy"] * 100
    ap_acc = ap_["accuracy"] * 100

    summary.add_row(
        "Ingestion",
        str(ing["correct"]),
        str(ing["total"]),
        f"[green]{ing_acc:.1f}%[/green]" if ing_acc >= 80 else f"[yellow]{ing_acc:.1f}%[/yellow]",
        f"routing {ing['routing_correct']}/{ing['total']}",
    )
    summary.add_row(
        "Reconciliation",
        str(rec["correct"]),
        str(rec["total"]),
        f"[green]{rec_acc:.1f}%[/green]" if rec_acc >= 80 else f"[yellow]{rec_acc:.1f}%[/yellow]",
        f"gap MAE ${rec['gap_mae']:.2f} CAD",
    )
    summary.add_row(
        "AP Agent",
        str(ap_["correct"]),
        str(ap_["total"]),
        f"[green]{ap_acc:.1f}%[/green]" if ap_acc >= 80 else f"[yellow]{ap_acc:.1f}%[/yellow]",
        "escalation + routing",
    )
    summary.add_row(
        "[bold]OVERALL[/bold]",
        f"[bold]{total_correct}[/bold]",
        f"[bold]{total_cases}[/bold]",
        f"[bold cyan]{mean_acc:.1f}%[/bold cyan]",
        "",
    )
    console.print(summary)
    console.print()

    # Ingestion per-class table
    cls_table = Table(box=box.SIMPLE, title="Ingestion — Per-Class Metrics")
    cls_table.add_column("Class")
    cls_table.add_column("Precision", justify="right")
    cls_table.add_column("Recall", justify="right")
    cls_table.add_column("F1", justify="right")
    for cls, v in ing["per_class"].items():
        f1_color = "green" if v["f1"] >= 0.8 else ("yellow" if v["f1"] >= 0.5 else "red")
        cls_table.add_row(
            cls,
            f"{v['precision']:.2f}",
            f"{v['recall']:.2f}",
            f"[{f1_color}]{v['f1']:.2f}[/{f1_color}]",
        )
    console.print(cls_table)
    console.print()

    # AP confusion matrix
    cm_table = Table(box=box.SIMPLE, title="AP Agent — Confusion Matrix (rows=predicted, cols=actual)")
    cm_table.add_column("Predicted \\ Actual")
    for lvl in ["N1", "N2", "N3", "N4"]:
        cm_table.add_column(lvl, justify="center")
    for pred in ["N1", "N2", "N3", "N4"]:
        row_vals = [str(ap_["confusion"][pred][act]) for act in ["N1", "N2", "N3", "N4"]]
        cm_table.add_row(pred, *row_vals)
    console.print(cm_table)
    console.print()

    # Failures
    failures = collect_failures(all_metrics)
    if failures:
        fail_table = Table(box=box.SIMPLE, title=f"[red]Failed Cases ({len(failures)})[/red]")
        fail_table.add_column("ID", style="bold red")
        fail_table.add_column("Expected")
        fail_table.add_column("Got")
        for f in failures:
            fail_table.add_row(f["id"], f["expected"], f["got"])
        console.print(fail_table)
    else:
        console.print("[bold green]All cases passed![/bold green]")

    console.print()


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    generated_at = datetime.now().isoformat(timespec="seconds")
    print(f"\n[benchmark] Starting — {generated_at}")
    print(f"[benchmark] CLASSIFICATION_MODE={os.getenv('CLASSIFICATION_MODE', 'keyword')}")
    print(f"[benchmark] QBO_MODE={os.getenv('QBO_MODE', 'mock')} | AP_MODE={os.getenv('AP_MODE', 'mock')}")

    print("\n[benchmark] Loading datasets...")
    ing_cases = load_dataset("dataset_ingestion.json")
    rec_cases = load_dataset("dataset_reconciliation.json")
    ap_cases = load_dataset("dataset_ap.json")
    print(f"  Ingestion:      {len(ing_cases)} cases")
    print(f"  Reconciliation: {len(rec_cases)} cases")
    print(f"  AP:             {len(ap_cases)} cases")

    print("\n[benchmark] Running Ingestion Agent...")
    ing_metrics = run_ingestion(ing_cases)

    print("\n[benchmark] Running Reconciliation Agent...")
    rec_metrics = run_reconciliation(rec_cases)

    print("\n[benchmark] Running AP Agent...")
    ap_metrics = run_ap(ap_cases)

    all_metrics = [ing_metrics, rec_metrics, ap_metrics]

    write_json_results(all_metrics, generated_at)
    write_md_report(all_metrics, generated_at)
    print_rich_summary(all_metrics)

    total_correct = ing_metrics["correct"] + rec_metrics["correct"] + ap_metrics["correct"]
    total = ing_metrics["total"] + rec_metrics["total"] + ap_metrics["total"]
    print(f"[benchmark] Done — {total_correct}/{total} correct ({total_correct/total*100:.1f}%)\n")


if __name__ == "__main__":
    main()
