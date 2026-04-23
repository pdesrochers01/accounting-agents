# Named test scenarios for AccountingAgents MVP
# Each scenario pairs QBO transactions with a bank statement variant

import copy
from tests.fixtures.transactions import QBO_TRANSACTIONS
from tests.fixtures.bank_statement import BANK_STATEMENT


def scenario_clean() -> dict:
    """
    All transactions match perfectly.
    Expected routing: completed (N1 — no HITL)
    """
    bank = copy.deepcopy(BANK_STATEMENT)
    bank[3]["amount"] = 312.45  # fix Hydro-Québec to match QBO exactly
    return {
        "name": "scenario_clean",
        "qbo_transactions": copy.deepcopy(QBO_TRANSACTIONS),
        "bank_statement": bank,
        "expected_routing": "completed",
        "expected_hitl": False,
    }


def scenario_gap_n3() -> dict:
    """
    Hydro-Québec: QBO=$312.45 vs bank=$2,762.45 → gap=$2,450 CAD → N3
    Expected routing: hitl_pending (N3 — HITL required)
    """
    return {
        "name": "scenario_gap_n3",
        "qbo_transactions": copy.deepcopy(QBO_TRANSACTIONS),
        "bank_statement": copy.deepcopy(BANK_STATEMENT),
        "expected_routing": "hitl_pending",
        "expected_hitl": True,
        "expected_gap": {
            "vendor_or_client": "Hydro-Québec",
            "expected_amount": 312.45,
            "actual_amount": 2762.45,
            "delta": 2450.00,
            "escalation_level": "N3",
        },
    }


def scenario_unrecognized() -> dict:
    """
    Incoming document cannot be classified.
    Expected routing: unrecognized (N4 — human transfer)
    """
    return {
        "name": "scenario_unrecognized",
        "qbo_transactions": [],
        "bank_statement": [],
        "expected_routing": "unrecognized",
        "expected_hitl": False,
    }
