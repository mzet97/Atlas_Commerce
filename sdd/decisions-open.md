# sdd/decisions-open.md — decisões abertas (M0)

| ID | Questão | Opções | Impacto se errar | Default seguro | Status |
|---|---|---|---|---|---|
| OPEN-01 | Equivalência `INV-001..012` ↔ `INV-<DOM>-NNN` | (a) tabela 1:1 (b) adotar um esquema | Rastreabilidade quebrada | Docs 01–08 vencem; mapear em M1 | DECIDED (a) — tabela abaixo |
| OPEN-02 | Ordem saga: reserva→pedido→autorização? | (a) blueprint (b) pedido→reserva | Cobrança sem estoque / pedido sem lastro | Blueprint §03 até ADR-007 | DECIDED (a): Reserve→PENDING→Authorize implementada, EVD-003-002 |
| OPEN-03 | ADR-007 Saga: timeout PSP gera o quê? | (a) PENDING+reconciliação (b) falha imediata | Pedido pago sem confirmação | (a) + `ReconciliationRequired` | DECIDED (a): reconcile implementado (C03), EVD-003-002 |
| OPEN-04 | Contrato webhook PSP fake | (a) HMAC + provider_ref (b) token opaco | Fraude/replay | (a), versionado em contracts | DECIDED (a): HMAC + dedup atômica, EVD-003-001 |
| OPEN-05 | Busca MVP: PG full-text basta? | (a) PG GIN (b) engine dedicada | Custo precoce / recall ruim | (a) + ADR com benchmark | DECIDED (a): PG trigram + GIN, EVD-005-001 |
| OPEN-06 | BFF `commerce-api` necessário? | (a) sim (b) front direto nos serviços | Acoplamento / latência | (b) até ADR provar (a) | DECIDED (b): Next consome serviços/projeções direto; reabrir com ADR se custo provar |

## Tabela de equivalência (OPEN-01, fechada)

| Doc 02 (INV-NNN) | Esquema de domínio | Implementação |
|---|---|---|
| INV-001 oversell=0 | INV-INV-001 | REQ-INV-001 (CAS + reserva atômica) — EVD-002-003 |
| INV-002 money minor/float=0 | INV-ORD-004 | REQ-I18N-001 (Money explícito, minor units) |
| INV-003 preço imutável no pedido | INV-ORD-003 | REQ-ORD-001 (snapshot na quote) |
| INV-004 quote TTL | INV-ORD-002 | REQ-CART-001 — EVD-003-002 |
| INV-005 webhook duplo→1 transição | INV-PAY-002 | REQ-PAY-001 — EVD-003-001 |
| INV-006 estorno auditável | INV-PAY-004 | Refund aggregate — EVD-006-002 |
| INV-007 four-eyes | INV-ADM-001 | REQ-ADM-001 — EVD-004-001 |
| INV-008 403 fora de escopo auditado | INV-ADM-002 | REQ-ADM-002 — EVD-002-002/003 |
| INV-009 IA sem writes autônomos | INV-AI-001 | REQ-AI-001 — EVD-007-002 (bypass=0) |
| INV-010 envelope versionado | INV-PLT-001 | contracts envelope — contracts.yaml CI |
| INV-011 outbox mesma transação | INV-PLT-002 | REQ-CQRS-001 — EVD-002-003 |
| INV-012 tenancy seller | INV-MKT-001 | REQ-MKT-002 — EVD-010-001 (403 auditado) |

ADRs 0001–0007: **ACCEPTED** em 2026-11-03 com evidências (ver cada ADR).
