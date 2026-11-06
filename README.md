# Atlas Commerce

Plataforma de e-commerce internacional construída com **SDD (Spec-Driven Development)** — metodologia evidence-first em que nenhuma feature é marcada como entregue sem evidência executável datada. O monorepo contém três produtos lógicos (Storefront, Control admin, Platform Contracts) que compartilham contratos versionados e nunca são donos dos dados uns dos outros.

## Visão geral da arquitetura

```
┌────────────────────────────────────────────────────────────────────┐
│                        atlas-storefront                            │
│  apps/storefront-next (Next.js 16 + React 19)                      │
│  apps/control-angular (Angular 22 admin — OIDC code+PKCE)          │
│                                                                    │
│  services/  (um bounded context por serviço, CQRS + outbox):       │
│   catalog    → outbox→Kafka→PG projection  (armazém de catálogo)   │
│   offers     → oferta única ativa por (sku,seller,market)          │
│   inventory  → reserva CAS, oversell=0, ledger com reason          │
│   order      → Cart→Quote→Checkout saga (Reserve→PENDING→Confirm)  │
│   payment    → PSP fake + webhook HMAC idempotente, refunds        │
│   psp-fake   → PSP determinístico (card 4242 / 0002 / 6666 / 9999) │
│   assistant  → LangGraph doc-08, tools read-only, bypass=0         │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│                        atlas-control                               │
│  apps/control-angular (OIDC code+PKCE, RBAC por scope)             │
│  control-api: módulos catalog_ops / pricing_ops / stock_ops /      │
│   order_ops / finance_ops (four-eyes + settlement) /               │
│   fulfillment_ops (ship + returns/RMA) / ai_ops / seller_ops       │
│  Regra: NUNCA escreve o estado canônico — comanda via owners.      │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│                    atlas-platform-contracts                        │
│  contracts/asyncapi (envelope de eventos versionado)               │
│  infrastructure/base-compose (26 containers, perfis core/m2/m3)    │
│  infrastructure/k8s (deploy surface: 18 Deployments, 14 Services)  │
│  benchmarks (k6 L1/L2/L3, ceiling, soak, chaos, l1_probe)          │
└────────────────────────────────────────────────────────────────────┘
```

**Eventos** são versionados por contrato AsyncAPI com compatibilidade N/N-1. Cada owner grava em MongoDB com outbox na MESMA transação (INV-CQRS-001), e um relay publica no Kafka. Um projector materializa a leitura em PostgreSQL. A leitura é sempre derivada — a autoridade nunca sai dos owners (INV-CQRS-001).

## Stack

| Camada | Tecnologia |
|---|---|
| Storefront | Next.js 16, React 19, TypeScript strict |
| Admin | Angular 22, oidc-client-ts, standalone components |
| APIs | Python 3.12+, FastAPI, uvicorn, motor (Mongo), asyncpg (PG), aiokafka |
| AI | LangGraph (doc-08 graph), tool allowlist, evals precision/groundedness |
| Data | MongoDB (owners), PostgreSQL (projeções CQRS), Redis, Kafka, RabbitMQ |
| Auth | Keycloak OIDC — Authorization Code + PKCE, four-eyes (admin), RBAC por scope |
| Infra | Docker Compose (26 containers), Kubernetes manifests (kubeconform-validados), OTel LGTM |
| CI | GitHub Actions — services (compose+pytest), storefront (tsc+build+Playwright), contracts (envelope validation) |

## Quick start

```sh
# stack completa (26 containers: mongo rs, pg, kafka, redis, keycloak, otel,
# smoke-api, + APIs, relays, projectors, psp-fake, dispatcher RabbitMQ, UI)
cd atlas-platform-contracts/infrastructure/base-compose
cp .env.example .env
docker compose --profile core --profile data --profile m2 --profile m3 up -d --build
```

A stack sobe com: Keycloak realm `atlas` (OIDC PKCE), MongoDB replica set, PostgreSQL com TODAS as migrações de leitura aplicadas automaticamente no primeiro boot, Kafka, Redis, OTel collector, 8 APIs em :8100–8107, storefront Next.js em :3100, admin Angular em :4200, dispatcher RabbitMQ.

Para popular o catálogo com dados de exemplo (Cafeteira M2, RMA, etc.), rode `apps/storefront-next/e2e/seed.py` ou o drill de checkout `services/order/e2e/checkout_e2e.py`.

## Testes

```sh
# por serviço (ruff + pytest)
cd atlas-storefront/services/catalog && uv sync && uv run pytest -q
# admin Angular
cd atlas-control/apps/control-angular && npm ci && npm run build
# E2E Playwright (13 specs: slice, search, recommendations, auth, i18n, seo, admin)
cd atlas-storefront/apps/storefront-next && pnpm e2e
```

O CI real (GitHub Actions) roda a stack compose completa + realm seed + migrações + ruff + pytest para todos os 7 pacotes Python + tsc/build/e2e Playwright, com `paths` filters por subdiretório.

## Requisitos de negócio (REQ-*) e invariantes (INV-*)

| Requisito | Implementação | Evidência |
|---|---|---|
| REQ-CAT-001/002 Catálogo com variantes, mídia, publicação | Catalog owner + Control catalog_ops | EVD-002-001 |
| REQ-INV-001 Oversell=0 sem backorder | CAS atômico + reserva | EVD-002-003 |
| REQ-CART-001 Quote versionada TTL/breakdown | Coupon, tax por região, multi-armazém | EVD-002-004 |
| REQ-ORD-001 Pedido snapshot imutável | Saga Reserve→PENDING→Authorize→Confirm | EVD-003-002 |
| REQ-PAY-001 Webhook assinado deduplicado | HMAC + provider_ref + refunds | EVD-003-001 |
| REQ-ADM-001 Four-eyes + thresholds por valor | finance_ops + order_ops | EVD-004-001 |
| REQ-ADM-002 Autorização backend por scope | command_channel (ABAC) | EVD-002-002/003 |
| REQ-I18N-001 pt-BR/en-US/es-US + Money | lib/i18n.ts + titles JSONB | EVD-001-005 |
| REQ-MKT-001..005 Marketplace 3P | seller tenancy + buybox + split settlement | EVD-010-001 |
| REQ-AI-001 IA sem writes autônomos | LangGraph read-only + human gate | EVD-007-002 |

Invariantes de arquitetura: INV-CQRS-001 (leitura derivada), INV-001 (oversell=0), INV-006 (estorno auditável), INV-010 (envelope versionado), INV-CQRS (outbox na mesma transação).

## Estrutura do monorepo

```
atlas-storefront/            # cliente
  apps/storefront-next/      # Next.js 16 (app router, i18n, SEO, e2e Playwright)
  apps/control-angular/      # Angular 22 admin (OIDC PKCE, módulos ops)
  services/catalog|inventory|offers|order|payment|psp-fake|assistant/
  e2e/  (checkout_e2e.py, fulfill_e2e.py, coupon_e2e.py, refund_e2e.py, marketplace_e2e.py)
atlas-control/               # admin
  control-api/               # FastAPI modular monolith (ABAC, four-eyes, audit)
  apps/control-angular/      # SPA Angular
atlas-platform-contracts/
  contracts/asyncapi/        # envelope de eventos versionado
  infrastructure/base-compose/  # 26 containers, perfis core/data/m2/m3/m7
  infrastructure/k8s/        # deploy surface validada (kubeconform 46/46)
  benchmarks/                # k6 L1/L2/L3, probes, chaos drill, ceiling
  infrastructure/smoke-api/
architecture/decisions/      # 7 ADRs ACCEPTED
sdd/                         # roadmap, requirements, progress, evidence, reports
specs/                       # SPEC-000/001/002/010 (9 artefatos cada)
.github/workflows/           # services.yaml, storefront.yaml, contracts.yaml
```

## Deploy

### Compose (dev/demo)

```sh
cd atlas-platform-contracts/infrastructure/base-compose
cp .env.example .env
docker compose --profile core --profile data --profile m2 --profile m3 --profile m7 up -d --build
```

### Kubernetes

```sh
cd atlas-platform-contracts/infrastructure/k8s
HOST_INFRA_IP=<IP-compose> bash deploy.sh   # atlas-secrets + ExternalName + Deployments
```

## Benchmarks

O harness k6 (doc-05) mediu L0 (50/1 RPS, p95 4ms), L1 (checkout p95 148ms SLO ✓), teto bracketado (950→2000 nav RPS), soak 10min (554k reqs, p95 92,9ms), caos RTO 2,9s. Resultados em `benchmarks/results/<run_id>/` com fingerprint. L2/L3 foram executados contra o cluster k8s1 com resultados honestos e limitações nomeadas (EVD-009-002).

## CI/CD

| Workflow | Gatilho | Jobs |
|---|---|---|
| `services.yaml` | push/PR em atlas-storefront, atlas-control | compose stack, realm seed, migrações, ruff+pytest nos 7 pacotes Python |
| `storefront.yaml` | push/PR em atlas-storefront | tsc, next build, Playwright e2e (13 specs), ng build (admin) |
| `contracts.yaml` | push/PR em atlas-platform-contracts | envelope AsyncAPI validation |

## SDD — metodologia

Todo requisito tem: spec, design, tasks, acceptance.feature, evidence (output observado), audit (cross-check), traceability (REQ→Task→Test→Gate→EVD), risks e README. As ADRs 0001–0007 foram ratificadas com evidências. Os OPEN-01..06 foram decididos. Ver `sdd/` para detalhes.

## Limitações nomeadas

- **K8s deploy em nó local**: o kernel `ogc4.1` não delega cpuset/memory/io para a árvore do usuário — o kubelet não roda sem root do host (receita de correção em `sdd/evidence/EVD-008-002-deploy-surface.md`).
- **Latência L2/L3**: o teto de navegação (p95 24,8s @ 10k RPS) e o checkout p95 (24,9s) no k8s1 se devem à topologia pods→compose pela LAN; em produção, mongo/pg/kafka seriam StatefulSets no cluster.
- **Cgroup v2**: os controllers `cpuset`, `memory`, `io` não estão disponíveis para o usuário — kubelet com `cgroups-per-qos=false` é usado como workaround de dev.

## Licença

Ver LICENSE.md (se aplicável).

## Contribuição

Siga a metodologia SDD: requisito → design → tasks → código → testes → evidência → ADR. Nada entra na main sem CI verde e evidência executável datada.
