# Report M2 — Catalog slice (2026-10-27) — PARCIAL

Entregue: Catalog owner (agregado+outbox txn, relay, projector, 14 testes
verdes, ruff limpo); Control-api (JWT+role, 403 auditado, 4 testes verdes);
Next.js SSR lendo a projeção. E2E vivo: create→publish via `:8102`,
outbox 0, PG v2, loja `:3100` com o título, lag 0. Stack: 13 containers.
Evidências: EVD-002-001/002. Gate M2 OPEN: PUBLISHING, ABAC por scope,
ofertas/inventário, E2E Playwright.
