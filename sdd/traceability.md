# sdd/traceability.md — REQ → design → TASK → teste → gate → EVD (M0)

Formato por unidade; sem resultados observados neste M0 (exemplo de
preenchimento futuro na última linha).

| Requirement | Design/Contract | Task | Test | Metric/Gate | Evidence | Status |
|---|---|---|---|---|---|---|
| INV-001/REQ-INV-001 | `inventory.positions` CAS + diagrama 07 | TASK-002-011 | TEST-002-031 concorrência | oversell = 0 | EVD-002-041 | TODO |
| INV-004/REQ-CART-001 | quote TTL + diagrama 10 | TASK-003-012 | TEST-003-014 quote expirada | re-cotação exigida | EVD-003-014 | TODO |
| INV-005/REQ-ORD-001 | state machine diagrama 08 | TASK-003-020 | TEST-003-021 webhook duplo | 1 transição válida | EVD-003-021 | TODO |
| INV-007+012/REQ-ADM-001 | Approval + diagrama 05 | TASK-004-003 | TEST-004-010 auto-aprovação | denied + auditado | EVD-004-010 | TODO |
| INV-009/REQ-AI-001 | LangGraph allowlist doc 08 | TASK-007-002 | TEST-007-005 injection | bypass = 0 | EVD-007-005 | TODO |
| REQ-CQRS-001 | outbox + diagrama 09 | TASK-002-018 | TEST-002-046 evento duplicado | sem projeção dupla | EVD-002-047 | TODO |
