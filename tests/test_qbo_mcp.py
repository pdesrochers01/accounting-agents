"""
Integration test for QBO MCP real connection.
Calls _fetch_qbo_bills_mcp() directly against the live QBO sandbox.
Requires: QBO_MCP_SERVER_PATH, QBO_CLIENT_ID, QBO_CLIENT_SECRET,
          QBO_REALM_ID, QBO_ENVIRONMENT, qbo_token.json
"""

import asyncio
import os

os.environ["QBO_MODE"] = "mcp"

from accounting_agents.nodes.reconciliation import _fetch_qbo_bills_mcp


def test_fetch_qbo_bills_mcp():
    """Fetch real bills from QBO sandbox and verify seeded test data."""
    bills = asyncio.run(_fetch_qbo_bills_mcp())

    print(f"\nBills fetched from QBO sandbox: {len(bills)}")
    for b in bills:
        print(
            f"  id={b['qbo_bill_id']:>5}  {b['vendor_name']:<40}"
            f"  ${b['amount']:>10,.2f} {b['currency']}"
            f"  date={b['date']}"
        )

    assert len(bills) >= 1, f"Expected at least 1 bill, got {len(bills)}"

    hydro = next(
        (b for b in bills if b["vendor_name"] == "Hydro-Québec"), None
    )
    assert hydro is not None, (
        "Hydro-Québec bill not found — was the sandbox seeded? "
        "Run scripts/seed_qbo_sandbox.py first."
    )
    assert hydro["amount"] == 2450.00, (
        f"Expected $2,450.00, got ${hydro['amount']:,.2f}"
    )
    assert hydro["currency"] == "CAD", (
        f"Expected CAD, got {hydro['currency']}"
    )

    print(
        f"\n✅ test_fetch_qbo_bills_mcp passed"
        f"\n   Hydro-Québec: ${hydro['amount']:,.2f} {hydro['currency']}"
        f"  (id={hydro['qbo_bill_id']}, date={hydro['date']})"
    )


if __name__ == "__main__":
    test_fetch_qbo_bills_mcp()
    print("\nAll QBO MCP tests passed.")
