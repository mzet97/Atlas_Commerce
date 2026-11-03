# sdd/traceability.md — REQ → design → TASK → teste → gate → EVD

Preenchida com os artefatos reais (testes/arquivos que existem no repo).
IDs aspiracionais TEST-*/EVD-**** originais substituídos pelos reais.

| Requirement | Design/Contract | Task | Test | Metric/Gate | Evidence | Status |
|---|---|---|---|---|---|---|
| INV-001/REQ-INV-001 | `inventory.positions` CAS + diagrama 07 | TASK-002-011 | `inventory/tests/` (escritores concorrentes, oversell) | oversell = 0 | EVD-002-003 | PASS |
| INV-004/REQ-CART-001 | quote TTL + diagrama 10 | TASK-003-012 | `order/tests/test_api.py::test_expired_quote_rejected` + `test_domain.py::expired` | re-cotação exigida | EVD-003-002 | PASS |
| INV-005/REQ-ORD-001 | state machine diagrama 08 | TASK-003-020 | `payment/tests/` (webhook duplo → 1 transição; `duplicate_paid_order=0`) | 1 transição válida | EVD-003-001 | PASS |
| INV-007+012/REQ-ADM-001 | Approval + diagrama 05 | TASK-004-003 | `control-api/tests/test_foureyes.py` (auto-aprovação 403 auditada) | denied + auditado | EVD-004-001 | PASS |
| INV-009/REQ-AI-001 | LangGraph allowlist doc 08 | TASK-007-002 | — (assistente M7 pendente; allowlist curada em `control-api/tests/test_ai.py`) | bypass = 0 | EVD-007-001 (parcial) | TODO |
| REQ-CQRS-001 | outbox + diagrama 09 | TASK-002-018 | suites offers/inventory (2x evento → 1 linha + inbox) | sem projeção dupla | EVD-002-003 | PASS |
