# sdd/decisions-open.md — decisões abertas (M0)

| ID | Questão | Opções | Impacto se errar | Default seguro | Status |
|---|---|---|---|---|---|
| OPEN-01 | Equivalência `INV-001..012` ↔ `INV-<DOM>-NNN` | (a) tabela 1:1 (b) adotar um esquema | Rastreabilidade quebrada | Docs 01–08 vencem; mapear em M1 | PROPOSED |
| OPEN-02 | Ordem saga: reserva→pedido→autorização? | (a) blueprint (b) pedido→reserva | Cobrança sem estoque / pedido sem lastro | Blueprint §03 até ADR-007 | PROPOSED |
| OPEN-03 | ADR-007 Saga: timeout PSP gera o quê? | (a) PENDING+reconciliação (b) falha imediata | Pedido pago sem confirmação | (a) + `ReconciliationRequired` | PROPOSED |
| OPEN-04 | Contrato webhook PSP fake | (a) HMAC + provider_ref (b) token opaco | Fraude/replay | (a), versionado em contracts | PROPOSED |
| OPEN-05 | Busca MVP: PG full-text basta? | (a) PG GIN (b) engine dedicada | Custo precoce / recall ruim | (a) + ADR com benchmark | PROPOSED |
| OPEN-06 | BFF `commerce-api` necessário? | (a) sim (b) front direto nos serviços | Acoplamento / latência | (b) até ADR provar (a) | PROPOSED |

ADRs 001–006 (microserviços vs monólito, CQRS, Kafka+Rabbit, outbox,
IA human-approved, Control sem rewrite): todas PROPOSED, nenhuma ACCEPTED.
