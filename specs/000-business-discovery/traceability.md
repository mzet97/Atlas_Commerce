# SPEC-000 traceability (M0: SPEC → diagramas, código futuro TODO)

| REQ | Diagramas | Contrato futuro | Teste futuro | Status |
|---|---|---|---|---|
| REQ-INV-001 | 07-classes-inventory, 10-sequence | `ReserveStock` gRPC/HTTP + idem key | TEST-002-031 concorrência | TODO |
| REQ-ORD-001 | 06-classes-order, 08-state, 10-seq | `PlaceOrder/ConfirmOrder` + outbox | TEST-003-021 webhook duplo | TODO |
| REQ-CQRS-001 | 09-cqrs-projection, 03/04-ER | envelope Kafka versionado | TEST-002-046 dedup projeção | TODO |
| REQ-ADM-001/002 | 05-er-admin, 02-puml admin | Approval + ScopeGrant | TEST-004-010 auto-aprovação | TODO |
| REQ-AI-001 | 01-puml storefront, doc 08 | 8 tools allowlisted | TEST-007-005 injection | TODO |
| REQ-I18N-001 | 03-er (translations), 01-puml | `LocaleText`, `Money` | E2E 3 locales | TODO |
