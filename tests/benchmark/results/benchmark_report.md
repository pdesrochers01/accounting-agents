# AccountingAgents — Benchmark Report
Generated: 2026-04-28T17:41:06
Dataset: 65 test cases | Mode: CLASSIFICATION_MODE=keyword | No API calls

---

## Ingestion Agent (30 cases)
Routing accuracy: 25/30 (83.3%)
Full accuracy (routing + doc type): 25/30 (83.3%)

| Class            | Precision | Recall | F1   |
|------------------|-----------|--------|------|
| bank_statement    | 0.62      | 1.00   | 0.77 |
| supplier_invoice  | 0.71      | 1.00   | 0.83 |
| client_invoice    | 1.00      | 0.60   | 0.75 |
| tax_document      | 1.00      | 0.60   | 0.75 |
| onboarding_form   | 1.00      | 1.00   | 1.00 |
| unrecognized      | 1.00      | 0.80   | 0.89 |

---

## Reconciliation Agent (15 cases)
Escalation accuracy: 15/15 (100.0%)
Gap precision: mean absolute error $0.00 CAD

---

## AP Agent (20 cases)
Escalation accuracy: 7/20 (35.0%)

Confusion matrix (rows=predicted, cols=actual):
```
         N1   N2   N3   N4
pred N1  [ 2   0   0   2]
pred N2  [ 0   0   0   0]
pred N3  [ 3   5   5   3]
pred N4  [ 0   0   0   0]
```

---

## Overall
Mean accuracy: 72.3%
Total: 47/65 correct

## Failed Cases
| ID        | Expected                              | Got                                   |
|-----------|---------------------------------------|---------------------------------------|
| ING-013   | client_invoice / to_ar                | bank_statement / to_reconciliation    |
| ING-015   | client_invoice / to_ar                | bank_statement / to_reconciliation    |
| ING-018   | tax_document / to_compliance          | bank_statement / to_reconciliation    |
| ING-020   | tax_document / to_compliance          | supplier_invoice / to_ap              |
| ING-028   | unrecognized / unrecognized           | supplier_invoice / to_ap              |
| AP-001    | N1 / completed                        | N3 / hitl_pending                     |
| AP-002    | N1 / completed                        | N3 / hitl_pending                     |
| AP-005    | N1 / completed                        | N3 / hitl_pending                     |
| AP-006    | N2 / completed                        | N3 / hitl_pending                     |
| AP-007    | N2 / completed                        | N3 / hitl_pending                     |
| AP-008    | N2 / completed                        | N3 / hitl_pending                     |
| AP-009    | N2 / completed                        | N3 / hitl_pending                     |
| AP-010    | N2 / completed                        | N3 / hitl_pending                     |
| AP-016    | N4 / unrecognized                     | N3 / hitl_pending                     |
| AP-017    | N4 / unrecognized                     | N3 / hitl_pending                     |
| AP-018    | N4 / unrecognized                     | N3 / hitl_pending                     |
| AP-019    | N4 / duplicate_bill                   | N1 / duplicate_bill                   |
| AP-020    | N4 / duplicate_bill                   | N1 / duplicate_bill                   |
