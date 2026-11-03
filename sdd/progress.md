# sdd/progress.md — diário M0 (2026-10-27)

- Recon executado: 23 arquivos, 12 diagramas, hashes SHA-256 em
  `source-manifest.md`; `git status` → `NO_REPO`; sem mover origem.
- Auditoria cruzada UC↔INV↔ER↔UML↔eventos↔ownership concluída (`audit.md`);
  6 OPENs registrados, nenhum resolvido silenciosamente.
- Esqueleto `sdd/` + `specs/000-business-discovery/` criado (este ciclo).
- SPEC-001 e SPEC-002 como especificação em `specs/001*` e `specs/002*`.
- Status M0: PASS (auditoria verificável, sem código, sem scaffolding).
- TASK-001-001 PASS em 2026-10-27: 12/12 diagramas renderizam
  (mermaid-cli 12.0.0 + PlantUML 1.2025.0); evidência em
  `sdd/evidence/TASK-001-001-diagrams.md`. Gate de sintaxe p/ M1 liberado.
- M1-increment-1 (2026-10-27): 3 repos `git init` + READMEs + envelope
  AsyncAPI v1 + matriz de dependências; sem commits (p/ revisão);
  `sdd/evidence/EVD-001-002-repos.md`. Gate M1 segue OPEN.
- M1-increment-2 (2026-10-27): compose core UP (mongo rs PRIMARY,
  pg, redis, keycloak, otel-lgtm, smoke-api); `/health` ok com trace_id;
  5 traces no Tempo incluindo o retornado; `sdd/evidence/EVD-001-003-compose.md`.
- M1-increment-3 (2026-10-27): realm `atlas` + 10 roles + 2 clients +
  2 users; JWTs reais (customer/iam_admin) + introspecção active=True;
  3 workflows com actionlint PASS; `sdd/evidence/EVD-001-004-oidc.md`.
- M2-increment-1 (2026-10-27): serviço Catalog owner no ar (11 containers);
  14 testes PASS + ruff limpo; E2E vivo (outbox 0, PG v2, lag 0);
  `sdd/evidence/EVD-002-001-catalog.md`. Gate M2 completo segue OPEN.
- M2-increment-2 (2026-10-27): Control comanda (JWT+role, 403 auditado),
  Storefront Next lê PG; E2E vivo (produto publicado aparece na loja);
  `sdd/evidence/EVD-002-002-vertical.md`. Stack: 13 containers.
- Papelada SDD completada (2026-10-27): ADRs 0001–0007, specs/001 e
  specs/002 com os 9 artefatos cada, `sdd/prompt.md` (R1),
  `sdd/reports/M{0,1,2}.md`.
- M2-resto (2026-10-27): Offers (12) + Inventory (13) + Control scope (8)
  verdes; E2E vivo produto→oferta→estoque→loja; Playwright 2 passed;
  gate oversell=0 provado; `sdd/evidence/EVD-002-003-m2-slice.md`.
  Stack: 19 containers.
- Próxima TASK READY: M3 / SPEC-003 — Cart/Quote/Checkout saga + PSP fake.
- M3-increment-1 (2026-10-28): PSP fake (6 testes) + Payment owner —
  intents idempotentes, webhook HMAC com dedup atômica, reconciliação via
  verdade do PSP; compose profile `m3` (payment :8105, psp-fake :8190,
  relay, projetor); Control `finance_ops` (view/reconcile, role
  `finance_analyst`, usuário `erin.finance`); suites 21 + 12 verdes, ruff
  limpo; drill T01–T05 `ALL PASS (12 checks)`; `duplicate_paid_order=0`
  provado no owner e na projeção (12/12); corrida charge×webhook encontrada
  e corrigida (convergência p/ o webhook); `sdd/evidence/EVD-003-001-m3-payment.md`.
  3 repos seguem uncommitted (aguardando revisão).
- M3-increment-2 (2026-10-28): Order owner — Cart/Quote(TTL)/saga checkout
  (Reserve→PENDING→Authorize→CONFIRMED, compensações decline/shortage,
  reconcile de UNKNOWN); compose `order-api :8106` + relay + projetor;
  suites 18 verdes, ruff limpo; drill `checkout_e2e.py` `ALL PASS
  (12 checks)` no caminho real (produto→oferta→estoque→pedido);
  projeção converge exato (3 CONFIRMED + 1 CANCELLED, 4 linhas);
  `sdd/evidence/EVD-003-002-m3-order.md`. 26 containers Up.
- M4-increment-1 (2026-10-28): four-eyes no reconcile financeiro —
  maker arquiva (202 PENDING), checker distinto aprova e executa;
  self-approval 403 auditado, PENDING duplicado 409; usuário
  `felix.finance`, migração `003_finance_approvals.sql`; control-api
  16 verdes, ruff limpo; `sdd/evidence/EVD-004-001-four-eyes.md`.
- M5-increment-1 (2026-10-28): busca `/search?q=` na loja (PG trigram,
  índice GIN; OPEN-05 decidido PG-only); `tsc` limpo, Playwright 4 passed
  (2 novos); `sdd/evidence/EVD-005-001-search.md`.
- M6-increment-1 (2026-10-28): fulfillment `CONFIRMED->SHIPPED`
  (owner idempotente + `fulfillment_ops` c/ `gina.fulfillment`);
  fila `notification_queue` (contrato de conteúdo, transporte diferido);
  order 21 + control 18 verdes, ruff limpo; drill `fulfill_e2e.py`
  `ALL PASS (5 checks)`; projeção SHIPPED + 2 notificações QUEUED;
  `sdd/evidence/EVD-006-001-fulfillment.md`.
- M7-increment-1 (2026-10-28): recommender allowlisted (`ai_allowlist` +
  `/recommendations`, curadoria `catalog_editor` via Control c/ pool atlas
  dedicado); control 21 verdes, ruff limpo; `tsc` + Playwright 5 passed
  (negativo: não-curadas ocultas); `sdd/evidence/EVD-007-001-ai-allowlist.md`.
- M8-increment-1 (2026-10-28): 18 Deployments + 8 Services K8s
  (namespace+configmap+gate `validate.py` verde); `NOT_DEPLOYED`
  (sem cluster); `sdd/evidence/EVD-008-001-k8s-manifests.md`.
- M9-increment-1 (2026-10-28): sonda L0 medida — leituras p95=4ms
  (n=3000, 0 erros), checkouts p95=143ms (n=60, 0 erros), teto 1.5s
  folgado 10x; `sdd/evidence/EVD-009-001-l0-bench.md`.
- M11 (2026-10-28): portfólio (`sdd/reports/M11-portfolio.md`, EN) +
  reports M3–M9; sweep final verde (psp-fake 6, payment 21, order 21,
  control 21, tsc limpo); stack 26 Up com /health 200 nas 8 APIs.
  Programa M0→M11 executado; OPENs documentados (M10, K8s deploy, L1-L4,
  refunds, RabbitMQ, i18n/SEO, ML, remotes/commits p/ revisão).
