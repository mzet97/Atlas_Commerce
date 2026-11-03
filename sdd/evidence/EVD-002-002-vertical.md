# EVD-002-002 — M2 increment-2: Admin comanda, Storefront lê (2026-10-27)

Status: PASS (fatia vertical completa no caminho real; gate M2 completo:
 Cupons/impostos, múltiplos armazéns e E2E Playwright seguem OPEN).

## Caminho provado (comandos reais, 13 containers Up)
1. `cara.catalog` (role `catalog_editor`) → `POST :8102/ops/products`
   → Control valida JWT (JWKS, iss/exp) + role → 201 DRAFT
   (`product-e5bf8f35817f`) → comando ao owner → Mongo + outbox.
2. `POST :8102/ops/products/{id}/publish` → 200 PUBLISHED v2.
3. Relay → Kafka `atlas.catalog.*.v1` → projector → PG
   `catalog_product_search`.
4. `GET :3100/` (Next.js SSR, `force-dynamic`) mostra "Mochila Vertical"
   com status — leitura da projeção, nunca do Mongo do owner.
5. `alice.customer` (só role `customer`) → `POST /ops/products` → **403**.
6. `admin_actions` (banco `control`, propriedade do Control):
   `catalog:create/allowed`, `catalog:publish/allowed`,
   `catalog:create/denied` — tentativa fora de escopo auditada.

## Testes
- control-api: 4 passed + ruff limpo (401 sem token, 403 customer+auditoria,
  201+200 editor, linha `denied` verificada no banco).
- catalog: 14 passed (inalterado, sem regressão).
- storefront-next: `tsc --noEmit` limpo; `pnpm build` dentro da imagem OK
  (container serve :3100 com o produto).

## Diagnósticos registrados
- Tokens via `localhost:8180` carregam iss localhost → `control-api` roda em
  `network_mode: host` (dev-only) para alcançar o mesmo localhost; porta
  8102 (8000 ocupada por outra API local); OTLP via `:4319`.
- `setup-realm.sh` agora cria `cara.catalog`/`catalog_editor` (idempotente).

## Falta para o gate M2 completo
Cupons/impostos por região, múltiplos armazéns, reembolso, E2E Playwright
cross-browser, 403 por `warehouse`/`market` (hoje só por role).
