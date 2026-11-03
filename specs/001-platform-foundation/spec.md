# SPEC-001 — Platform Foundation (PROPOSTA, sem implementar em M0)

## Objetivo
Três repos Git independentes + toolchain reproduzível + Compose mínimo
observável, sem nenhum serviço de domínio vazio.

## Escopo
- Criar pós-gate M0: `atlas-storefront`, `atlas-control`,
  `atlas-platform-contracts` (nunca monorepo; workspace ≠ repo).
- Templates versionados via Copier (`fastapi-service`,
  `fastapi-modular-monolith`); frontends via CLIs oficiais
  (`create-next-app`, `ng new`); contratos via `buf`/OpenAPI/AsyncAPI.
- Compose profiles `core/data/messaging/observability/ai/mock-integrations`
  com Mongo **replica set**, PostgreSQL, Keycloak, Redis; OTel → Collector.
- CI por repo: lint, typecheck, teste, SAST/SBOM, `buf breaking`, imagens
  com digest; `uv.lock`/`pnpm-lock.yaml`; nunca `latest` em produção.

## Contratos a versionar
OpenAPI (borda HTTP), Protobuf (gRPC interno, deadlines, mTLS workload),
AsyncAPI/JSON Schema (envelope Kafka com `event_id`, versões, `traceparent`).

## Gate M1
Cada app sobe por script documentado; smoke OIDC cliente+admin;
Testcontainers/Compose; primeiro trace cross-process; CI verde;
rebuild determinístico. Nenhum microserviço sem bounded context real.
