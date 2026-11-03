# EVD-002-003 — M2 resto: Offers + Inventory + ABAC + E2E (2026-10-27)

Status: PASS (fatia M2 completa no essencial; pendências listadas).

## Owners novos (mesmo padrão do Catalog: agregado+outbox txn, relay, projector)
- **offers** (12 testes PASS + ruff): Offer ACTIVE único por
  (sku,seller,market,channel); `OfferConflict` em overlap (409);
  update/deactivate versionados; `available_offer_view` idempotente.
- **inventory** (13 testes PASS + ruff): `available = on_hand - reserved -
  safety_stock`; reserva condicional atômica; idempotência por chave
  (INV-002); confirm/release com ledger; `inventory_availability_view`.
- Bug real achado pelos testes e corrigido nos 3 owners:
  `DuplicateKeyError` é subclasse de `OperationFailure` no pymongo — o
  guard genérico re-lançava o dup e quebrava a idempotência. Cláusulas
  separadas + re-leitura fora da txn.

## Gate concorrência (prova viva)
- 20 escritores paralelos na última unidade: exatamente 1 ACTIVE, 19×409,
  `available == 0`, sem oversell (teste) — INV-001/002.

## Control: pricing_ops + stock_ops com ABAC de escopo
- `command_channel.py`: verify → role → scope grants (tabela
  `scope_grants`, seed cara→BR/W1) → forward → audit allowed/denied.
- 8 testes PASS: 201 editor com escopo, 403 sem role, 403 fora do escopo +
  linha `denied` auditada, actor = `token.subject` verificado.

## Loja: preço + estoque + PUBLISHING (tsc + build OK, Playwright 2 passed)
- `:3100` lista título + preço + disponibilidade da projeção; `?v=N`
  mostra badge `sincronizando…` quando `projection_version < N`.
- E2E vivo: produto→publish→offer→stock via `:8102` aparece na loja com
  `129.90 BRL` e `7 un.`; Playwright Chromium confirma os dois cenários.

## Stack: 19 containers (core + m2: catalog/offers/inventory ×3,
## control-api host-network, storefront-next, infra).
## Falta (M2-next/M3)
Cupons/impostos, multi-armazém além de W1, PUBLISHING automático por
versão de comando (hoje só via `?v=`), E2E do checkout (M3), CI em runner.
