# EVD-003-001 — M3 increment-1: checkout/PSP vertical (payment owner)

Status: PASS (observed outputs only; commands + results below).

## Scope
PSP fake determinístico + Payment owner (intents, webhook HMAC, reconciliação),
compose profile `m3`, `finance_ops` no Control, drill T01–T05.

## Services (profile `m3`, observed `docker compose ps`)
- `atlas-base-payment-api-1` Up — `:8105`, `atlas-base-psp-fake-1` Up — `:8190`
- `atlas-base-payment-relay-1`, `atlas-base-payment-projector-1` Up
- `atlas-base-control-api-1` Up (recriado: `finance_ops` + `PAYMENT_API_URL`)
- `GET /health` → `{"status":"ok"}` em `:8105` e `:8190`
- `GET /openapi.json` do Control lista
  `/ops/finance/payments/{intent_id}` e `.../reconcile`
- Realm: `erin.finance` → token com `finance_analyst`
  (`map erin.finance->finance_analyst -> 204`)
- Migração `002_payment_projection.sql` aplicada via `psql`
  (`payment_intents`, `payment_webhooks`, `processed_events`)

## Suites (observado)
- `services/psp-fake`: `ruff` clean + `6 passed`
  (approve/decline/dup-key/unknown-500+status/by-key/pending-replay)
- `services/payment`: `ruff` clean + `21 passed`
  (domínio 5, API 13, projeção 3)
- `control-api`: `ruff` clean + `12 passed` (incl. `test_finance.py` 4:
  401 sem token, 403+auditoria p/ customer, view e reconcile p/ analyst)

## Drill E2E `services/payment/e2e/t01_t05.py` (stdlib, ao vivo)
- `ALL PASS (12 checks)`: T01 20 racers mesma chave → 1 intent AUTHORIZED;
  T02 webhook duplo → `200,200`, versão estável; T03 amount 666
  (timeout 12s > client 10s) → UNKNOWN sem ref → reconcile via by-key →
  AUTHORIZED; T04 converge `v=2 ≤ 4`; T05 UNKNOWN(999) → reconcile →
  AUTHORIZED → webhook tardio no-op (`v` estável).

## Invariantes (observado no banco)
- Owner mongo `payment.intents`: 12 AUTHORIZED, agregação por
  `provider_ref` com `n>1` → `[]` ⇒ **duplicate_paid_order=0**.
- PG `payment_intents`: 12 AUTHORIZED, zero dups por `provider_ref`
  (12/12 com o owner — relay+projetor convergiram ao vivo).
- PG `payment_webhooks`: 9 linhas; `processed_events(payment-projector-1)`: 57.
- Nota honesta: fileiras `provider_ref='psp-oo'` (5, ref sintética dos testes
  unitários na PG compartilhada) foram removidas (`DELETE 5`) antes da
  contagem final; fileiras INITIATED residuais de `payment_test` permanecem
  (read model, sem efeito no owner).

## Achado de corrida (corrigido e provado)
- O PSP fake entrega o webhook ANTES da resposta do charge; o caminho do
  charge perdia a corrida de versão (409) embora o pagamento estivesse
  AUTHORIZED via webhook. `handle_create` agora converge para o estado do
  webhook quando é o mesmo `provider_ref` (sem reaplicar evento).
  Prova ao vivo: `POST /intents` → `201 AUTHORIZED` após o rebuild.

## Ruído conhecido (não-erro)
- `payment-projector` registra `Topic ... not found in cluster metadata` no
  boot (auto-create no primeiro produce; convergiu 12/12, sem poison skips).
  O `catalog-projector` (M2) é silencioso; comportamento equivalente.

## Fora do escopo (OPEN, sem ornamento)
- Four-eyes p/ money movement (M4), reembolso/estorno (sem PSP real),
  testes L0-L4 (`NOT_MEASURED`), remotes/commits (3 repos seguem uncommitted,
  aguardando revisão do usuário).
