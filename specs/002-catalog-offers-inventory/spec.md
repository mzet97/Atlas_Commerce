# SPEC-002 — Catalog/Offers/Inventory slice (PROPOSTA, sem implementar em M0)

## Objetivo
Primeira fatia comercial: operador publica produto e ele aparece na loja,
com autorização, projeção CQRS e concorrência segura.

## Fluxo
Admin Angular autentica (Keycloak, MFA) → Control monólito valida
ação+escopo+four-eyes → comando autenticado ao owner (`CreateProduct`,
`PublishOffer`, `ReceiveStock`) → owner persiste agregado + outbox na mesma
transação Mongo → CDC → Kafka → workers idempotentes → PG
(`catalog_product_search`, `available_offer_view`, `inventory_admin_view`)
→ Storefront Next.js exibe em pt-BR com estado `PUBLISHING` até
`source_version` alcançada.

## Regras
- Publicar produto ≠ criar oferta (UC-005 vs UC-007).
- Estoque: CAS condicional, `oversell = 0`, TTL nunca substitui transição.
- Leitura defasada nunca confirma saldo; `availability_hint` é indicativo.
- Operador fora de `warehouse/market` → 403 + auditoria.

## Gate M2
Produto demo criado por operador permitido aparece na loja pelo caminho
real; 403 fora de escopo; evento repetido não duplica view; 2 escritores
concorrentes na última unidade vendem no máximo 1. Evidência: Mongo, Kafka,
PG, UI, trace, testes T01..T05 adaptados.
