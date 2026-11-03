# SPEC-002 design — fatia executada em 2 incrementos

## Incremento 1: Catalog owner (EVD-002-001)
`services/catalog/`: `domain` (Product, eventos, erros tipados) →
`application` (commands/handlers, Protocol) → `mongo_repo` (agregado +
outbox na mesma txn, CAS por versão, idempotência por chave única) →
`api` (Pydantic v2, handlers por tipo de erro) → `relay` (outbox→Kafka) +
`projector` (Kafka→PG idempotente). Migração `001_catalog_projection.sql`
(`catalog_product_search`, `processed_events`).
Corridas resolvidas: loop preso no import (lifespan), read em txn abortada
(read fora da txn), WriteConflict 112 no commit (retry no label
transitório), exceção frozen+slots (sem slots).

## Incremento 2: canal de comando + vitrine (EVD-002-002)
`control-api`: JWT via JWKS (iss/exp/assinatura) → exige `catalog_editor`
(403 + linha `denied` em `admin_actions`) → encaminha ao owner (status
pass-through) → grava `allowed`. Banco `control` só tem auditoria.
Next.js SSR (`force-dynamic`) lê `catalog_product_search` em `:3100`;
nota de projeção indicativa (INV-CQRS-001) na página.

## Faltas de design (M2-next)
Estado `PUBLISHING` (receipt version vs `projection_version`); 403 por
`market`/`warehouse` (ABAC além de role); cupons/impostos; E2E Playwright.
