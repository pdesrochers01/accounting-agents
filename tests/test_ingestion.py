"""
Unit tests for the real Ingestion Agent node.
No MCP, no LangGraph graph execution — pure node logic.
"""

from accounting_agents.nodes.ingestion import (
    ingestion_node,
    _classify,
    _extract_amount,
    _extract_date,
    _extract_vendor,
)
from accounting_agents.state import initial_state
from tests.fixtures.scenarios import scenario_gap_n3


def test_classify_supplier_invoice():
    assert _classify("FACTURE\nFournisseur: Hydro-Québec") == "supplier_invoice"
    assert _classify("Invoice\nVendor: Telus") == "supplier_invoice"
    print("✅ test_classify_supplier_invoice passed")


def test_classify_bank_statement():
    assert _classify("Relevé bancaire\nSolde: $1,200.00") == "bank_statement"
    assert _classify("Bank Statement\nBalance: $500.00") == "bank_statement"
    print("✅ test_classify_bank_statement passed")


def test_classify_receipt():
    assert _classify("Reçu\nPaiement reçu: $50.00") == "receipt"
    assert _classify("Receipt\nPayment received") == "receipt"
    print("✅ test_classify_receipt passed")


def test_classify_unrecognized():
    assert _classify("Lorem ipsum dolor sit amet") == "other"
    print("✅ test_classify_unrecognized passed")


def test_extract_amount():
    assert _extract_amount("Montant: $312.45 CAD") == 312.45
    assert _extract_amount("Total: $2,762.45") == 2762.45
    assert _extract_amount("no amount here") == 0.00
    print("✅ test_extract_amount passed")


def test_extract_date():
    assert _extract_date("Date: 2026-03-22") == "2026-03-22"
    assert _extract_date("no date") != ""  # falls back to today
    print("✅ test_extract_date passed")


def test_ingestion_node_supplier_invoice():
    """Full node test — supplier invoice → to_reconciliation."""
    state = initial_state("test-ingestion-001")
    state["input_document"] = {
        "raw_text": (
            "FACTURE INV-4524\n"
            "Fournisseur: Hydro-Québec\n"
            "Date: 2026-03-22\n"
            "Montant: $312.45 CAD"
        ),
        "source_email_id": "gmail-001",
        "filename": "facture_hydro_mars2026.pdf",
    }

    result = ingestion_node(state)

    assert result["routing_signal"] == "to_reconciliation"
    assert len(result["documents_ingested"]) == 1
    doc = result["documents_ingested"][0]
    assert doc["document_type"] == "supplier_invoice"
    assert doc["vendor_or_client"] == "Hydro-Québec"
    assert doc["amount"] == 312.45
    assert doc["document_number"] == "INV-4524"
    assert result["error_log"] == []
    print(f"✅ test_ingestion_node_supplier_invoice passed")
    print(f"   → {doc['document_type']} | {doc['vendor_or_client']} "
          f"| ${doc['amount']:,.2f} | {doc['document_number']}")


def test_ingestion_node_unrecognized():
    """Unclassifiable document → unrecognized routing."""
    state = initial_state("test-ingestion-002")
    state["input_document"] = {
        "raw_text": "Lorem ipsum dolor sit amet consectetur",
        "source_email_id": "gmail-002",
        "filename": "unknown_doc.pdf",
    }

    result = ingestion_node(state)

    assert result["routing_signal"] == "unrecognized"
    assert len(result.get("documents_ingested", [])) == 0
    assert len(result["error_log"]) == 1
    print("✅ test_ingestion_node_unrecognized passed")


def test_ingestion_node_no_input():
    """No input_document → unrecognized routing."""
    state = initial_state("test-ingestion-003")
    result = ingestion_node(state)
    assert result["routing_signal"] == "unrecognized"
    assert len(result["error_log"]) == 1
    print("✅ test_ingestion_node_no_input passed")


if __name__ == "__main__":
    test_classify_supplier_invoice()
    test_classify_bank_statement()
    test_classify_receipt()
    test_classify_unrecognized()
    test_extract_amount()
    test_extract_date()
    test_ingestion_node_supplier_invoice()
    test_ingestion_node_unrecognized()
    test_ingestion_node_no_input()
    print("\nAll ingestion tests passed.")
