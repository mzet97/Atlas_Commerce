# sdd/requirements.md — requisitos estáveis (M0)

## Convenção
IDs imutáveis após publicados; deprecar, nunca renumerar.
`REQ-CAT-*` catálogo, `REQ-INV-*` estoque, `REQ-ORD-*` pedido/checkout,
`REQ-PAY-*` pagamento, `REQ-ADM-*` admin, `REQ-I18N-*` locale,
`REQ-AI-*` assistente. Invariantes `INV-001..012` (doc 02) + mapeamento
para o esquema `INV-<DOM>-<NNN>` do prompt em OPEN-01.

| ID | Requisito | Owner | Status |
|---|---|---|---|
| REQ-CAT-001 | Criar/editar produto com variantes, mídia, atributos localizados | Catalog | PROPOSED |
| REQ-CAT-002 | Publicar produto só com aprovação; publicar ≠ criar oferta | Catalog + Control | PROPOSED |
| REQ-OFF-001 | Oferta única ativa por (sku, seller, market, canal, vigência) | Pricing | PROPOSED |
| REQ-INV-001 | Reserva condicional atômica; `oversell = 0` sem backorder | Inventory | PROPOSED |
| REQ-INV-002 | Todo movimento com motivo, ator, `correlation_id` + ledger | Inventory | PROPOSED |
| REQ-CART-001 | Carrinho + `PriceQuote` versionada com TTL e breakdown | Cart/Checkout | PROPOSED |
| REQ-ORD-001 | Pedido com snapshot imutável; transição idempotente com histórico | Order | PROPOSED |
| REQ-PAY-001 | PSP fake determinístico; webhook assinado e deduplicado; sem PAN/CVV | Payment | PROPOSED |
| REQ-ADM-001 | Four-eyes acima do limite; `requested_by != approved_by` | Control | PROPOSED |
| REQ-ADM-002 | Autorização backend por ação+escopo; 403 fora de escopo auditado | Control + owners | PROPOSED |
| REQ-I18N-001 | pt-BR/en-US/es-US; mercado ≠ locale ≠ moeda; `Money` explícito | Storefront/Control | PROPOSED |
| REQ-AI-001 | IA só recomenda/propõe carrinho; compra exige confirmação em UI confiável | AI Service | PROPOSED |
| REQ-CQRS-001 | Outbox mesma transação Mongo; projeção idempotente reconstruível | Todos owners | PROPOSED |
| REQ-OBS-001 | Trace `checkout_id/order_id` com PII minimizada; dashboards por contexto | Platform | PROPOSED |

## NFRs (propostas, NÃO medidas — doc 05)
L0 local (50 catálogo RPS / 1 checkout/s) até L4 hipótese (1M RPS / 10k+
checkouts/s). p95 checkout `< 1.5s` para aceite PENDING; projection lag
p99 `< 5s`; RTO 30min / RPO 5min propostos. Benchs exigem fingerprint
completo (commit, locks, hardware, réplicas, dataset) — nada declarado aqui.
