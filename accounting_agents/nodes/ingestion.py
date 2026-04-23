"""
Ingestion Agent node — real implementation (MVP).

Responsibilities (UC01):
  1. Read input_document from SharedState
  2. Classify document type by keyword matching
     (LLM classification deferred to Phase 2)
  3. Extract metadata: date, amount, vendor/client, document number
  4. Write IngestedDocument to documents_ingested
  5. Emit routing_signal

Classification rules (keyword matching, case-insensitive):
  supplier_invoice : facture, invoice, fournisseur, vendor, montant dû
  bank_statement   : relevé, statement, solde, balance, bancaire
  receipt          : reçu, receipt, paiement reçu, payment received
  other            : no match → routing: unrecognized
"""

import re
import uuid
from datetime import datetime

from accounting_agents.state import (
    AccountingAgentsState,
    IngestedDocument,
    DocumentType,
)


# ── Classification ───────────────────────────────────────────────

CLASSIFICATION_RULES: list[tuple[DocumentType, list[str]]] = [
    (
        "supplier_invoice",
        ["facture", "invoice", "fournisseur", "vendor", "montant dû", "amount due"],
    ),
    (
        "bank_statement",
        ["relevé", "statement", "solde", "balance", "bancaire", "bank"],
    ),
    (
        "receipt",
        ["reçu", "receipt", "paiement reçu", "payment received"],
    ),
]


def _classify(raw_text: str) -> DocumentType:
    """Classify document type by keyword matching."""
    text_lower = raw_text.lower()
    for doc_type, keywords in CLASSIFICATION_RULES:
        if any(kw in text_lower for kw in keywords):
            return doc_type
    return "other"


# ── Metadata extraction ──────────────────────────────────────────

def _extract_amount(raw_text: str) -> float:
    """Extract first numeric amount found in text."""
    # Match patterns like: 312.45, $312.45, 2,762.45 — decimal required
    # to avoid matching bare integers in document numbers (e.g. INV-4524)
    pattern = r"\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})"
    matches = re.findall(pattern, raw_text)
    for match in matches:
        try:
            return float(match.replace(",", ""))
        except ValueError:
            continue
    return 0.00


def _extract_date(raw_text: str) -> str:
    """Extract first ISO date (YYYY-MM-DD) found in text."""
    pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
    match = re.search(pattern, raw_text)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def _extract_vendor(raw_text: str) -> str:
    """
    Extract vendor/client name.
    Looks for patterns like 'Fournisseur: X' or 'Vendor: X' or 'From: X'.
    Falls back to first capitalized line segment.
    """
    patterns = [
        r"(?:fournisseur|vendor|client|from|de)\s*[:\-]\s*([^\n]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # Fallback: return first non-empty line
    for line in raw_text.splitlines():
        line = line.strip()
        if line and not line.isdigit():
            return line[:50]
    return "Unknown"


def _extract_document_number(raw_text: str) -> str:
    """Extract document number (INV-XXXX, FACT-XXXX, etc.)."""
    pattern = r"\b([A-Z]{2,6}[-]\d{3,6})\b"
    match = re.search(pattern, raw_text)
    if match:
        return match.group(1)
    return f"DOC-{str(uuid.uuid4())[:8].upper()}"


# ── Main node ────────────────────────────────────────────────────

def ingestion_node(state: AccountingAgentsState) -> dict:
    """
    Real Ingestion Agent node.
    Reads input_document from SharedState, classifies and extracts
    metadata, writes IngestedDocument to documents_ingested.
    """
    error_log = list(state.get("error_log", []))
    input_doc = state.get("input_document")

    if not input_doc:
        error_log.append("[ingestion_node] No input_document in SharedState")
        return {
            "routing_signal": "unrecognized",
            "error_log": error_log,
        }

    raw_text = input_doc.get("raw_text", "")
    source_email_id = input_doc.get("source_email_id", "")
    filename = input_doc.get("filename", "")

    if not raw_text:
        error_log.append(f"[ingestion_node] Empty raw_text in {filename}")
        return {
            "routing_signal": "unrecognized",
            "error_log": error_log,
        }

    # --- Classify ---
    doc_type = _classify(raw_text)

    if doc_type == "other":
        error_log.append(
            f"[ingestion_node] Could not classify document: {filename}"
        )
        return {
            "routing_signal": "unrecognized",
            "error_log": error_log,
        }

    # --- Extract metadata ---
    amount = _extract_amount(raw_text)
    date = _extract_date(raw_text)
    vendor = _extract_vendor(raw_text)
    doc_number = _extract_document_number(raw_text)

    # Preserve qbo_transactions and bank_statement if injected
    # (used by Reconciliation Agent in MVP test harness)
    ingested: IngestedDocument = IngestedDocument(
        document_id=str(uuid.uuid4()),
        document_type=doc_type,
        date=date,
        amount=amount,
        currency="CAD",
        vendor_or_client=vendor,
        document_number=doc_number,
        qbo_entry_id="",
        source_email_id=source_email_id,
    )

    # Pass through qbo_transactions and bank_statement if present
    ingested_dict = dict(ingested)
    if "qbo_transactions" in input_doc:
        ingested_dict["qbo_transactions"] = input_doc["qbo_transactions"]
    if "bank_statement" in input_doc:
        ingested_dict["bank_statement"] = input_doc["bank_statement"]

    existing_docs = list(state.get("documents_ingested", []))
    existing_docs.append(ingested_dict)

    print(f"[ingestion_node] Classified: {filename} → {doc_type}")
    print(f"[ingestion_node] Vendor: {vendor} | Amount: ${amount:,.2f} CAD")
    print(f"[ingestion_node] Document number: {doc_number} | Date: {date}")

    return {
        "documents_ingested": existing_docs,
        "routing_signal": "to_reconciliation",
        "error_log": error_log,
    }
