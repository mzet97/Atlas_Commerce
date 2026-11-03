# EVD-001-002 — M1 increment-1: repos + contracts skeleton (2026-10-27)

Status: PARCIAL (gate M1 NÃO atingido; sem compose, sem smoke, sem CI).

## Executado
- `git init -b main` em `atlas-storefront/`, `atlas-control/`,
  `atlas-platform-contracts/` → 3 repos independentes, branch `main`,
  zero commits (deixado uncommitted para revisão, sem push).
- 7 arquivos: 3 README + 3 .gitignore + envelope AsyncAPI v1
  (`contracts/asyncapi/domain-event-envelope.yaml`, campos INV-010).
- Toolchain provada: Python 3.14.7, uv 0.11.15, Node v24.15.0,
  pnpm 11.1.3, Docker host 29.9.2, git 2.55.0 → `sdd/dependency-matrix.md`.
- Ausentes e marcados TODO: `ng`, `buf`.

## Não executado (próximos incrementos)
- Templates Copier, `create-next-app`, `ng new`, compose core (Mongo
  replica set/PG/Keycloak/Redis), OTel, contratos OpenAPI/Proto, CI.
- Gate M1 (smoke OIDC, trace cross-process, rebuild determinístico): OPEN.
