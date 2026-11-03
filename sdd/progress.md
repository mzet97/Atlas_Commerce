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
- FASE-0 (2026-11-03): monorepo consolidado no GitHub como
  `Atlas_Commerce` (rename de `Atalas_Commerce`, redirect no GitHub).
  Workflows reais na raiz: services (stack completa + realm + migrações +
  ruff + pytest 7 pacotes), storefront (tsc/build + e2e Playwright c/
  seed reproduzível), contracts (paths-filtered). TASK-001-008 PASS.
  Docs sincronizadas (READMEs, requirements IMPLEMENTED com EVD,
  traceability preenchida, OPEN-02..06 DECIDED com evidência).
  `sdd/evidence/EVD-001-005-ci-runner.md`.
- FASE-1 (2026-11-03): TASK-001-009 PASS — rebuild determinístico
  fim-a-fim; imagem pg assa o bootstrap (atlas+control + TODAS as
  migrações de leitura no primeiro boot; bake por causa de NTFS/SELinux
  nos bind mounts). TASK-001-010 PASS — Auth Code + PKCE real no
  storefront (PKCE S256 puro, sessão verificada via JWKS, redirect_uri
  por Host header); Playwright 8 passed. TASK-002-013 PASS — cupons
  (PERCENT/FIXED, escopo de mercado, mínimo), impostos por região
  (BR/US/UE bps, floor), multi-armazém (WAREHOUSES env, hint + reserva
  atômica); PSP fake gatilhos migram de amount p/ cartão (6666/9999).
  Suites: order 39, control 24, psp 6, payment 21, catalog 14, offers
  12, inventory 13; drills coupon 8/8, checkout 12/12, fulfill 5/5.
  `sdd/evidence/EVD-001-006-rebuild.md`, `EVD-001-007-pkce.md`,
  `EVD-002-004-pricing.md`. Próxima: FASE-2 (M4 completo).
- FASE-2 (2026-11-03): M4 completo — four-eyes com threshold por valor
  (APPROVAL_THRESHOLD_MINOR), cancelamento operacional com four-eyes
  (order:cancel, resource_type), sweeper de PENDING expirado
  (compensação + settle attempt); migrações 004/005 (control).
- FASE-3 (2026-11-03): refunds end-to-end (PSP /refunds + agregado
  PaymentRefunded + four-eyes com payload), cancel CONFIRMED com perna
  de dinheiro, Returns/RMA (refund + restock via ledger), dispatcher
  RabbitMQ real (quorum queue, 45 drenadas), carrier label fake.
  EVD-006-002.
- FASE-4 (2026-11-03): M5 completo — i18n pt/en/es (titles JSONB +
  Intl), SEO (canonical/hreflang/sitemap/robots), paginação + facetas;
  13 specs Playwright. EVD-001-005 atualizada.
- FASE-5 (2026-11-03): Control Angular (apps/control-angular) — OIDC
  code+PKCE público, módulos orders/finance/coupons/returns, CORS,
  compose control-ui :4200, CI control-ui job; admin.spec verde.
- FASE-6 (2026-11-03): M7 completo — assistente LangGraph doc 08
  (tools de leitura, bypass=0, human gate, LLM opcional), evals
  (precision 1.00), ranking com peso/TTL/explicabilidade, busca no
  owner catalog. EVD-007-002.
- FASE-7 (2026-11-03): M8 increment-2 — deploy.sh (secrets do .env),
  ExternalName infra, ingress, NetPol, HPA/PDB, kubeconform 46/46;
  deploy bloqueado em host rootless (3 rotas tentadas; receita no
  EVD-008-002). EVD-008-002.
- FASE-8 (2026-11-03): M9 L1 medido (83k reqs; checkout p95 148ms ✓;
  navegação p95 2.48s @950/s ✗ — bottleneck SSR 1 réplica), chaos
  drill RTO 2.9s com leituras 100%; L2/L3 bloqueados sem cluster.
  results/20261103T152532/.
- FASE-9 (2026-11-03): M10 completo — SPEC-010 (9 artefatos), sellers
  (tenancy, 403 auditado cross-tenant), oferta concorrente + buybox,
  split settlement (10%), velocity antifraude (stop real ao vivo),
  paul.seller no realm. EVD-010-001.
- FASE-10 (2026-11-03): RATIFICAÇÃO — ADRs 0001–0007 ACCEPTED com
  evidências; OPEN-01..06 DECIDED (tabela de equivalência INV↔DOM
  incluída); requirements REQ-* IMPLEMENTED com EVDs (REQ-MKT-001..005
  novos); roadmap M10 ENTREGUE; M11 portfólio atualizado. Programa
  SDD M0→M10 fechado; limits nomeados: K8s deploy + L2/L3 (cluster),
  nav SLO @950/s (réplicas da loja).
