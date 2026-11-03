# Plano: Finalização completa do programa SDD Atlas Commerce

Escopo aprovado: fechar TODAS as pendências do SDD — incluindo M10 marketplace completo, deploy K8s em cluster real, benchmarks até L3 e assistente LangGraph completo.

**Metodologia**: seguimos o próprio processo SDD do projeto (evidence-first) — cada incremento entrega código + testes + evidência em `sdd/evidence/EVD-*.md`, atualiza `sdd/progress.md` e as tasks/specs correspondentes, e termina com commit convencional.

## Fase 0 — CI real e higiene administrativa
1. Consolidar os 3 workflows de `atlas-*/.github/workflows/` para `.github/workflows/` na raiz (monorepo único só executa workflows na raiz), com `paths:` filters por subprojeto. Jobs: matrix Python (catalog, offers, inventory, order, payment, psp-fake, control-api, smoke-api → `uv sync` + `ruff` + `pytest`), storefront (pnpm + `tsc` + `next build` + Playwright), contratos (validação atual + `buf lint/breaking` após instalar buf).
2. Push e run verde no runner → **TASK-001-008 PASS** com EVD.
3. Atualizar docs desatualizadas: READMEs dos 3 subprojetos (estado real M9+), `sdd/requirements.md` (status dos REQs conforme implementado), `sdd/traceability.md` (preencher com EVDs reais), `specs/00{1,2}*/tasks.md` (TASK-002-014 → PASS; TASK-002-009 → fechar), `sdd/decisions-open.md` (OPEN-05 → DECIDED — PG-only já é fato).
4. Corrigir typo do remote: renomear `Atalas_Commerce` → `Atlas_Commerce` no GitHub (via `gh`, confirmando com você) + `git remote set-url`.

## Fase 1 — Restos de M1/M2
1. **TASK-001-009**: rebuild determinístico documentado — `docker compose down -v && up --build`, smoke completo (containers up, `/health` 200, realm bootstrap), EVD.
2. **TASK-001-010**: login real Auth Code + PKCE no storefront-next (redirect Keycloak, sessão, logout) + teste Playwright.
3. **TASK-002-013**: cupons (discount lines no PriceQuote versionado), impostos por market/tax-region, multi-armazém (positions por warehouse + reserva por posição) — testes, E2E, EVD.

## Fase 2 — M4 completo
Four-eyes para cancelamento de pedido; expiração de PENDING (scheduler cancela com compensação e evento); thresholds por valor (abaixo do limite dispensa four-eyes, configurável). Migrações no control-api, testes, EVD.

## Fase 3 — Refunds + M6 completo
1. **Refunds**: agregado `Refund` no payment (idempotente, evento `Refunded`), endpoint no psp-fake, role `payments:refund` no Control com four-eyes (tool proibida para IA), reconciliação e projeção cobrindo refunds, E2E pedido → refund → convergência.
2. **M6**: Returns/RMA (`ReturnRequest`, `RMA`, `ReturnApproved`, `RefundRequested`; devolução repõe estoque via ledger), etiqueta de transportadora (carrier adapter fake), **dispatcher RabbitMQ real** (quorum queues + DLQ + bridge idempotente Kafka→Rabbit conforme ADR-0003, worker de notificação com retry). Compose atualizado, testes, EVD.

## Fase 4 — M5 completo (i18n/SEO)
`LocaleText` no catalog por locale; storefront com rotas localizadas pt-BR/en-US/es-ES, hreflang, metadata/sitemap/canonical, Intl/ICU, `Money` por mercado/moeda; paginação + facetas na busca PG. Playwright cross-locale, EVD.

## Fase 5 — Control Angular (`apps/control-angular`, novo)
`ng new` strict, feature-based; OIDC Auth Code+PKCE; shell + módulos contra as APIs existentes do control-api: Catalog Ops, Stock, Offers, Order Ops (cancelamento four-eyes), Finance (reconcile + refunds four-eyes), Fulfillment, IAM, Approvals, Audit, curadoria AI. Servir via compose (perfil control-ui), job de CI, Playwright do admin, README atlas-control, EVD.

## Fase 6 — M7 completo: assistente LangGraph + ranking
Grafo do doc 08 (IntentAndSafety → CatalogSearchTool → ParallelOfferComparison → ClarifyNeeds → RecommendationComposer → OptionalCartProposal → **HumanApproval** → CartMutationTool → CheckoutLink), só tools permitidas, bypass=0. LLM configurável por env (interface OpenAI-compatible — serve qualquer provedor ou self-hosted Ollama/vLLM); sem credencial → fallback para busca manual. Dataset de avaliação (retrieval precision, groundedness, alucinação de preço/estoque, prompt-injection success rate, custo/conversa, p95 turn latency). Ranking: expiração de curadoria (TTL), explicabilidade, sinais de vendas/margem/curadoria + personalização leve. EVD + gate M7.

## Fase 7 — M8 completo + deploy em cluster real
**Pré-requisito**: você fornece kubeconfig/aponta o cluster no início desta fase. Completar manifests: secrets (ESO ou SealedSecrets conforme o cluster), statefulsets Mongo/PG/Kafka com PVs, ingress+TLS, NetworkPolicy, HPA/PDB; `kubectl --dry-run=server`; deploy dos 18 Deployments + 8 Services, smoke no cluster com OTel, `validate.py` verde, EVD com fingerprint do cluster.

## Fase 8 — M9: benchmarks até L3
Harness k6/Locust conforme doc 05: carga aberta, ~95% navegação, SKU hot, seed 10^6 SKUs, warmup/steady/spike/soak/chaos, resultados em `results/<run_id>/` com fingerprint completo. **L1** (1k RPS / 20 checkout/s) no compose local; **L2** (10k / 200) no cluster real com HPA/Kafka lag/backpressure; **L3** (100k / 2k) multi-nó no cluster — se o hardware não alcançar, relatório honesto de limites (o SDD proíbe declarar sem medir). Soak + chaos (kill relay/projector/replica Mongo, rebalance Kafka) + RTO/RPO medidos. Relatórios + EVDs.

## Fase 9 — M10 marketplace 3P completo
Spec formal SPEC-010 (9 artefatos em `specs/010-*/`) antes do código. Domínio: onboarding de Sellers (tenant real), oferta concorrente por (sku, seller, market), listagem/buybox no storefront, split settlement (ledger por seller + comissão), antifraude básico (velocity), IAM `seller_operator` com scopes por seller/tenant (previstos no blueprint). Gates: zero violação de tenant (cross-tenant → 403 auditado), settlement corretamente rateado, baseline de regressão 1P 100% verde. EVD.

## Fase 10 — Ratificação e fechamento
ADRs 0001–0007 PROPOSED → ACCEPTED com links de evidência; resolver OPEN-01..06 em `decisions-open.md` (OPEN-02/04/05 já de facto decididos); atualizar relatório M11 portfólio e sweep final do `progress.md`; roadmap M10 → entregue.

## Ordem e dependências
0 → 1 → 2 → 3 → 4 ∥ 5 → 6 → 7 (precisa kubeconfig) → 8 (usa o cluster da fase 7) → 9 (exige 1P estável) → 10.

Cada fase termina com: testes verdes, ruff/tsc limpos, EVD em `sdd/evidence/`, progress/tasks atualizadas, commit.

## Premissas
- LLM do M7: provider configurável via env; você fornece endpoint/key quando quiser ativar (sem isso: fallback manual + dataset on-demand).
- Cluster K8s: acesso fornecido por você no início da Fase 7 (kubeconfig + permissões para namespace/secrets/ingress).
- Renomear o repo no GitHub é ação externa — confirmo com você antes de executar.
- Playwright no CI sobe stack mínima via service containers (detalhe ajustado na execução).