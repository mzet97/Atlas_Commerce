# SPEC-001 traceability

| REQ | Design/Contrato | Task | Teste | Gate/Evidência | Status |
|---|---|---|---|---|---|
| REQ-CQRS-001 | compose core (mongo rs + kafka) | TASK-001-003 | smoke `/health` mongo ok | EVD-001-003 | PASS |
| REQ-OBS-001 | otel-lgtm + instrumentação | TASK-001-004 | trace_id no Tempo | EVD-001-003 | PASS |
| REQ-ADM-002 | realm + roles + clients | TASK-001-005/006 | JWT + introspecção | EVD-001-004 | PASS |
| REQ-CQRS-001 | envelope AsyncAPI v1 | TASK-001-002/007 | parse + campos INV-010 | EVD-001-002 + CI check | PASS |
| Gate M1 | CI runner / rebuild / PKCE | TASK-001-008..010 | — | — | TODO |
