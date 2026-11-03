# EVD-007-001 — M7 increment-1: recommender allowlisted (conteúdo curado)

Status: PASS (observed outputs only; commands + results below).

## Escopo
`/recommendations` na loja surfacea SOMENTE ofertas ACTIVE **e**
curadas em `ai_allowlist`. Curadoria via Control (`catalog_editor`):
`POST/DELETE/GET /ops/ai/allowlist`. Sem PII além da projeção.

## Prova (observado)
- Migração `services/catalog/migrations/003_ai_allowlist.sql` aplicada
  (`ai_allowlist`, atlas PG).
- Control com segundo pool (`ATLAS_PG_DSN`): `ruff` clean + `21 passed`
  (incl. `test_ai.py`: allow+list, customer 403, remove 404).
- Seed honesto via comando real: `cara.catalog` allowlistou
  `offer-8c1634c75e12` ("m7 seed").
- `GET :3100/recommendations` mostra `Cafeteira M2` e oculta
  `Item M6*`/`Item Ship*` (ofertas ACTIVE não curadas) — HTML observado.
- `tsc` limpo; `playwright test` → **5 passed** (1 novo recommendations).

## Decisões registradas
- Join triplo (allowlist→offer ACTIVE→produto) com `ORDER BY
  total_available DESC LIMIT 10`: determinístico, sem modelo externo.
  "AI" aqui = contrato de curadoria + ranking explícito, sem LLM.
- Curadoria mora no atlas PG junto à view (gate de read-model);
  Control escreve cross-DB via pool dedicado — auditado como comando.

## Fora do escopo (OPEN, sem ornamento)
- Ranking por ML/embeddings, personalização, explicabilidade,
  expiração de curadoria, L0-L4 (`NOT_MEASURED`), remotes/commits.
