# EVD-001-003 — M1 increment-2: compose core + smoke + trace (2026-10-27)

Status: PASS parcial (stack core no ar, smoke e trace provados; gate M1
completo — OIDC token, CI — segue OPEN).

## Imagens (pull provado no host, `distrobox-host-exec docker pull`)
- mongo:8.0.6, redis:8.0.1, keycloak/keycloak:26.2.5,
  grafana/otel-lgtm:0.8.1, postgres:17 (cache), python:3.14-slim (build).
- Digests registrados na saída de `docker images --digests` da sessão.

## Subida
`docker compose --profile core up -d --build` (a partir de
`infrastructure/base-compose/`, `.env` de `.env.example`).
Correções aplicadas e registradas: `--replSet` (era `--replset`),
init via `--eval` inline (bind mount com EACCES no runtime rootless),
OTLP HTTP → `http://otel:4318` (4317 é gRPC e é porta ocupada no host;
host mapeia 4319/4320). Host 4317 ocupado por outro receiver — não usado.

## Provas (comandos reais, exit 0)
- `curl /health` → `{"status":"ok","mongo":"ok","redis":"ok",
  "trace_id":"e4c8ba49d5cdcf0b459f5615beb397e0"}`; `/ready` → ready.
- `mongosh rs.status()` → 1 membro PRIMARY, health 1 (replica set ativo).
- `curl :8180/realms/master` → realm master com public_key (Keycloak up).
- `docker logs smoke-api | grep -c "Transient error"` → 0 após correção.
- Tempo search (proxy Grafana, últimos 10 min) → 5 traces
  `atlas-smoke-api / GET /health`, incluindo `e4c8ba49…` = trace_id do
  `/health`. Primeiro trace ponta a ponta PROVADO.

## Deps resolvidas no smoke-api (pip freeze)
fastapi 0.162.0, uvicorn 0.54.0, motor 3.7.1, redis 6.4.0,
otel SDK/exporter 1.45.1, instrumentações 0.66b1, pydantic 2.14.1.

## Falta para o gate M1
Smoke OIDC com token cliente/admin, realm/atlas config, CI verde,
rebuild determinístico documentado.
