# EVD-005-001 — M5 increment-1: busca full-text na loja (PG trigram)

Status: PASS (observed outputs only; commands + results below).

## Escopo
Busca server-side `/search?q=` sobre a projeção `catalog_product_search`,
rank por trigram + substring exata. Resolve OPEN-05 como PG-only
(sem engine; reavaliação só sob pressão L2 medida).

## Prova (observado)
- Migração `services/catalog/migrations/002_catalog_search.sql` aplicada:
  `CREATE EXTENSION pg_trgm` + índice GIN trigram no título.
- `GET :3100/search?q=Cafeteira` retorna `Cafeteira M2` (HTML observado).
- `pnpm exec tsc --noEmit` limpo; `playwright test` → **4 passed**
  (2 slice existentes + 2 busca novos), Chromium ao vivo contra `:3100`
  (imagem reconstruída com a página `/search`).

## Decisões registradas
- Trigram em vez de tsvector: títulos pt-BR com tolerância a erro de
  digitação sem configurar dicionário; consulta parametrizada ($1),
  limite 80 chars, LIMIT 50.
- Página é server component (`force-dynamic` herdado do padrão): lê a
  projeção, nunca o Mongo do owner.

## Fora do escopo (OPEN, sem ornamento)
- i18n/SEO da loja, paginação, facetas, L0-L4 (`NOT_MEASURED`),
  remotes/commits (aguardando revisão do usuário).
