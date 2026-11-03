# SPEC-002 traceability

| REQ | Design/Contrato | Task | Teste | Gate/Evidência | Status |
|---|---|---|---|---|---|
| REQ-CAT-001/002 | Product DRAFT→PUBLISHED + eventos | TASK-002-001 | test_domain (5) | EVD-002-001 | PASS |
| REQ-CQRS-001 | outbox txn + relay + projector | TASK-002-002/005 | test_slice duplicate | EVD-002-001 + lag 0 vivo | PASS |
| REQ-INV-001 (análogo) | idempotência por chave única | TASK-002-004 | 20 escritores → 1 | EVD-002-001 | PASS |
| REQ-ADM-001/002 | Control JWT+role + audit próprio | TASK-002-006/007 | test_ops (4) + 403 vivo | EVD-002-002 | PASS |
| REQ-I18N-001 | título pt-BR, storefront SSR | TASK-002-008 | tsc + HTML com título | EVD-002-002 | PASS |
| Gate M2 resto | PUBLISHING, ABAC scope, E2E | TASK-002-009..012 | — | — | TODO |
