# SPEC-002 evidence (índice; detalhe em `sdd/evidence/`)

- EVD-002-001 (owner): 14 testes + ruff; E2E `POST :8101` → publish →
  outbox 0, PG v2, tópicos criados, lag 0; migração 001 aplicada.
- EVD-002-002 (vertical): `:8102/ops/*` com JWT (201/200 editor, 403
  customer), `admin_actions` allowed+denied, `:3100` com o título.
- Suites: catalog 14 passed, control-api 4 passed, tsc limpo.
