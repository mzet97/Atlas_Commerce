# SPEC-001 design — fundação executada em 3 incrementos

## Repos (incremento 1, EVD-001-002)
`atlas-storefront/`, `atlas-control/`, `atlas-platform-contracts/`;
`git init -b main`, zero commits (revisão pendente), sem push autorizado.
READMEs + `.gitignore` (lockfiles versionados, `.env` nunca).

## Compose core (incremento 2, EVD-001-003)
`infrastructure/base-compose/compose.yaml`, perfil `core`: mongo rs0
(`--replSet`, init inline), pg:17, keycloak:26.2.5 + db própria, redis:8.0.1,
otel-lgtm:0.8.1, smoke-api FastAPI. Portas de host ajustadas (4317 ocupado →
4319/4320; 8100/8180/3300 livres). `smoke-api` prova boot+Mongo+Redis+OTLP.

## OIDC + CI (incremento 3, EVD-001-004)
`setup-realm.sh` idempotente: realm `atlas`, 10 roles, 2 clients, 3 users
(alice/customer, boss/iam_admin, cara/catalog_editor). Smoke: JWTs reais +
introspecção `active=True`. 3 workflows (contracts valida envelope INV-010;
guards verificam higiene); actionlint 1.7.7 PASS nos 3; check python
executado localmente. CI em runner bloqueado sem remote.

## Falhas encontradas e decisões
- `--replset` → `--replSet`; init via `--eval` inline (EACCES em bind
  mount no runtime rootless); OTLP HTTP na 4318 (não na gRPC 4317);
  `update-profile` no 1º login exigiu first/last name no bootstrap;
  `.env` jamais commitado (exemplo versionado).
