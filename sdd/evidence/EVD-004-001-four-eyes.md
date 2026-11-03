# EVD-004-001 — M4 increment-1: four-eyes no dinheiro (maker-checker)

Status: PASS (observed outputs only; commands + results below).

## Escopo
`POST /ops/finance/payments/{id}/reconcile` deixou de executar: agora
arquiva pedido PENDING (202) e só a aprovação de um SEGUNDO analista
executa o reconcile no owner. Leitura segue direta (sem four-eyes p/
leitura — correto).

## Prova (control-api, `ruff` clean + `16 passed`)
- `test_finance.py` atualizado: request → 202 PENDING + intent segue UNKNOWN.
- `test_foureyes.py` (4, stack viva: Keycloak + payment reais):
  maker aprova o próprio → 403 + `approval:decide/denied` auditado;
  checker (`felix.finance`) aprova → EXECUTED + intent AUTHORIZED;
  segundo pedido PENDING igual → 409; reject → REJECTED + nada se move.
- Realm: `map felix.finance->finance_analyst -> 204` (script idempotente).
- Migração `003_finance_approvals.sql` aplicada (`finance_approvals` +
  índice único parcial: um PENDING por (action, intent)).
- Rotas vivas em `:8102/openapi.json`: view, reconcile(202),
  `approvals/pending`, `approve`, `reject`.

## Decisões registradas
- Aprovação é UPDATE (não append-only): o append-only vive em
  `admin_actions` (request/allowed, decide/allowed, decide/denied);
  a tabela de aprovações é fila de estado, não trilha de auditoria.
- Execução com owner fora do ar marca FAILED (não EXECUTED) com
  `execution_status`; re-aprovar é 409 — novo pedido decide de novo.
- Self-approval é 403 auditado, não 422: é violação de autorização.

## Fora do escopo (OPEN, sem ornamento)
- Four-eyes p/ cancelamento de pedido via Control (sem endpoint),
  expiração de PENDING, segundo aprovador obrigatório distinto por
  valor (threshold), L0-L4 (`NOT_MEASURED`), remotes/commits
  (aguardando revisão do usuário).
