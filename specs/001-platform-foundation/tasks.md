# SPEC-001 tasks

| ID | Objetivo | Aceite | Estado |
|---|---|---|---|
| TASK-001-001 | Render 12 diagramas | mermaid 12 + plantuml 1.2025 OK | PASS |
| TASK-001-002 | 3 repos + READMEs + envelope | `git init` + 7 arquivos | PASS |
| TASK-001-003 | Compose core + smoke-api | `/health` ok + trace_id | PASS |
| TASK-001-004 | Primeiro trace no Tempo | trace_id do `/health` no Tempo | PASS |
| TASK-001-005 | Realm + roles + users | 201s, rerun 409+204 | PASS |
| TASK-001-006 | Smoke OIDC + introspecção | roles + `active=True` | PASS |
| TASK-001-007 | Workflows + actionlint | 3 PASS + check python | PASS |
| TASK-001-008 | CI verde em runner | push + run verdes | PASS (EVD-001-005) |
| TASK-001-009 | Rebuild determinístico doc. | `down -v && up --build` + smoke | PASS (EVD-001-006) |
| TASK-001-010 | Auth Code + PKCE no browser | login real via redirect | PASS (EVD-001-007) |
