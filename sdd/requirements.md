# sdd/requirements.md — requisitos estáveis (M0)

## Convenção
IDs imutáveis após publicados; deprecar, nunca renumerar.
`REQ-CAT-*` catálogo, `REQ-INV-*` estoque, `REQ-ORD-*` pedido/checkout,
`REQ-PAY-*` pagamento, `REQ-ADM-*` admin, `REQ-I18N-*` locale,
`REQ-AI-*` assistente. Invariantes `INV-001..012` (doc 02) + mapeamento
para o esquema `INV-<DOM>-<NNN>` do prompt em OPEN-01.

| ID | Requisito | Owner | Status |
|---|---|---|---|
| REQ-CAT-001 | Criar/editar produto com variantes, mídia, atributos localizados | Catalog | IMPLEMENTED (variantes/mídia pendentes; EVD-002-001) |
| REQ-CAT-002 | Publicar produto só com aprovação; publicar ≠ criar oferta | Catalog + Control | IMPLEMENTED (EVD-002-002) |
| REQ-OFF-001 | Oferta única ativa por (sku, seller, market, canal, vigência) | Pricing | IMPLEMENTED (EVD-002-003) |
| REQ-INV-001 | Reserva condicional atômica; `oversell = 0` sem backorder | Inventory | IMPLEMENTED (EVD-002-003) |
| REQ-INV-002 | Todo movimento com motivo, ator, `correlation_id` + ledger | Inventory | IMPLEMENTED (ledger em `domain.py`, reason obrigatório) |
| REQ-CART-001 | Carrinho + `PriceQuote` versionada com TTL e breakdown | Cart/Checkout | IMPLEMENTED (EVD-003-002) |
| REQ-ORD-001 | Pedido com snapshot imutável; transição idempotente com histórico | Order | IMPLEMENTED (EVD-003-002) |
| REQ-PAY-001 | PSP fake determinístico; webhook assinado e deduplicado; sem PAN/CVV | Payment | IMPLEMENTED (EVD-003-001) |
| REQ-ADM-001 | Four-eyes acima do limite; `requested_by != approved_by` | Control | IMPLEMENTED (EVD-004-001; thresholds por valor pendentes) |
| REQ-ADM-002 | Autorização backend por ação+escopo; 403 fora de escopo auditado | Control + owners | IMPLEMENTED (EVD-002-002/003) |
| REQ-I18N-001 | pt-BR/en-US/es-US; mercado ≠ locale ≠ moeda; `Money` explícito | Storefront/Control | IMPLEMENTED (EVD-001-005 storefront e2e 13/13; Intl + titles JSONB) |
| REQ-AI-001 | IA só recomenda/propõe carrinho; compra exige confirmação em UI confiável | AI Service | IMPLEMENTED (EVD-007-002: grafo doc 08, write-tools ausentes, bypass=0) |
| REQ-CQRS-001 | Outbox mesma transação Mongo; projeção idempotente reconstruível | Todos owners | IMPLEMENTED (EVD-002-003: 2x evento → 1 linha) |
| REQ-OBS-001 | Trace `checkout_id/order_id` com PII minimizada; dashboards por contexto | Platform | IMPLEMENTED (EVD-001-003/004) |
| REQ-MKT-001 | Sellers registrados como tenants (iam_admin) | Control | IMPLEMENTED (EVD-010-001) |
| REQ-MKT-002 | seller_operator publica só no próprio tenant; cross-tenant 403 auditado | Control + offers | IMPLEMENTED (EVD-010-001) |
| REQ-MKT-003 | Oferta concorrente por (sku, seller, market); buybox menor preço | offers + storefront | IMPLEMENTED (EVD-010-001) |
| REQ-MKT-004 | Split settlement auditável (bruto/comissão/líquido por seller) | Control | IMPLEMENTED (EVD-010-001) |
| REQ-MKT-005 | Velocity antifraude (>5 auth/cliente/60s → FRAUD_VELOCITY) | payment | IMPLEMENTED (EVD-010-001) |

## NFRs (propostas, NÃO medidas — doc 05)
L0 local (50 catálogo RPS / 1 checkout/s) até L4 hipótese (1M RPS / 10k+
checkouts/s). p95 checkout `< 1.5s` para aceite PENDING; projection lag
p99 `< 5s`; RTO 30min / RPO 5min propostos. Benchs exigem fingerprint
completo (commit, locks, hardware, réplicas, dataset) — nada declarado aqui.
