# 07 — Plano SDD evidence-first, milestones, teste e portfólio

## 1. Convenção SDD
Cada unidade de trabalho tem `spec.md` (problema e regras), `design.md` (alternativas/ADRs), `tasks.md` (tarefas pequenas), `acceptance.feature` (Given/When/Then), `evidence.md` (comandos, testes, métricas) e links para diagramas/versionamento. **Primeiro auditoria e documento, depois código.** Sem Spec Kit e sem classes `service.py` triviais apenas por estética.

### Template de issue SDD
`ID | Contexto | Atores | Regras INV-* | Comandos/Queries | Eventos | Contratos | Dados | Falhas/compensações | Ameaças | Testes e evidências | Definition of Done`

## 2. Epics por valor e dependência
| Ordem | Épico | Entrega visível | Gates |
|---:|---|---|---|
| 00 | Discovery | domínio, casos de uso, UML, ER, NFRs, ADRs e riscos | revisão dos modelos sem contradições |
| 01 | Platform Foundation | repos CLI templates + CI + Keycloak + tracing + Compose mínimo | smoke + OIDC + Testcontainers + SAST/SBOM |
| 02 | Catalog/Offers/Inventory | criação via Admin, publicação e leitura no Storefront | 2 writers concorrentes/oversell=0, projeção idempotente |
| 03 | Cart/Quote/Checkout/Order/Payments | comprar usando PSP fake, saga, cache/read model | cenários UC-003 T01..T05 + E2E |
| 04 | Admin workflow | operações, aprovações, escopo, auditoria, relatórios | operador fora do scope=403 e auditado |
| 05 | Customer experience | busca, UX acessível, SEO, idiomas e pedidos | Web Vitals, WCAG audit, Playwright cross-browser |
| 06 | Operations | fulfillment, entrega, returns, notifications | falhas assíncronas e compensação |
| 07 | AI shopping | recomendações com LangGraph, tool authorizations, cart confirmation | injection tests, impossibilidade de compra autônoma |
| 08 | Cloud-native | K8s, Helm, GitOps, scaling, chaos, DR | restore e testes de falha gravados |
| 09 | Scale proof | perf baselines L0-L4 conforme hardware | manifesto de benchmark reproduzível |
| 10 | International portfolio | documentação arquitetural EN, vídeos de demo, postmortems, ADRs, metrics | GitHub README + resultados honestos |

## 3. Estratégia de testes (não depende só de cobertura)
- **Unidade:** regras puras de estoque, preços, pedidos, políticas, VOs, estados; `pytest`, Hypothesis property-based, mutation testing seletivo. Assertivas de invariantes; fixtures determinísticas.
- **Integração:** Mongo replica set (transações), PostgreSQL, Redis, RabbitMQ quorum (topologia), Kafka, Keycloak. Testcontainers quando possível, e Compose para smoke; comportamento sob restart e falha.
- **Contratos:** Protobuf Buf breaking lint, OpenAPI schema diff, AsyncAPI/JSON schema/version envelopes e consumer-driven contract; compatibilidade N/N-1.
- **E2E:** Playwright TypeScript para Next.js e Angular, Android/mobile viewport, browsers Chromium/Firefox/WebKit, idiomas/mercados, autenticação, compra, estoque/admin, limites de acesso. APIs mock de PSP para cenários previsíveis.
- **Resiliência:** kill do worker entre commit e ack, outbox backlog, replay DLQ, queda de Redis, Kafka e PSP, reordenação de webhook, race de reservas, timeout gRPC.
- **Segurança:** OWASP API Top 10 / ASVS, BOLA/IDOR, ABAC, CSRF/SSRF, rate-limit, mass assignment, upload scanning, supply chain scanning, falsificação de webhook, prompt injection, tenant isolation.
- **Performance:** p50/p95/p99, saturation, errors, cost; perf gates explícitos com ambiente documentado.

## 4. Definition of Done por feature
1. Requisito e invariantes mapeados; owner conhecido.
2. Modelos/contratos versionados e migração backward-compatible.
3. Unit/integration/contract/e2e conforme risco, executados e evidenciados.
4. Logs/métricas/traces, alerts/runbook e dashboards atualizados.
5. IAM, autorização, privacidade, validação e limites de payload validados.
6. Retries/idempotency/compensation/recovery comprovados se assíncrono.
7. `docs/` e API changelog em português e inglês nos pontos públicos.
8. Benchmark/regressão para rotas críticas; evidências vinculadas ao commit.

## 5. Estrutura de projetos Git planejada (não gerada ainda)
```text
atlas-local-workspace/                   # pasta local, NAO um unico repo git
├── atlas-storefront/                     # Git repo A, CI e release independentes
│   ├── apps/storefront-next/
│   ├── services/{catalog,pricing,inventory,cart,checkout,orders,payments,ai-shopping,...}/
│   ├── tests/{integration,contracts,e2e,load,chaos}/
│   ├── deploy/{compose,helm,skaffold}/
│   └── specs/ docs/
├── atlas-control/                        # Git repo B, CI e release independentes
│   ├── apps/control-angular/
│   ├── control-api/src/atlas_control/modules/{catalog_ops,stock_ops,pricing_ops,approvals,audit,reports,iam}/
│   ├── tests/{unit,integration,contracts,e2e}/
│   ├── deploy/{compose,helm,skaffold}/
│   └── specs/ docs/
└── atlas-platform-contracts/             # Git repo C, pacote versionado compartilhado
    ├── contracts/{proto,openapi,asyncapi,jsonschema}/
    ├── templates/{fastapi-service,fastapi-modular-monolith}/
    ├── infrastructure/{iam,telemetry,base-compose,charts}/
    └── ci/ test-harness/
```

`platform/contracts` não é `platform/domain`: contratos são pacotes versionados; compartilhamento de modelo interno entre bounded contexts é proibido salvo VOs estáveis deliberadamente comuns.

## 6. Evidências para seleção internacional
- `architecture/` ADRs em inglês, trade-off analysis e context diagrams.
- Vídeo curto do checkout de ponta a ponta e falhas controladas sem pedidos duplicados.
- Captura Grafana trace atravessando storefront→gateway→checkout→payment→events→projection.
- Playwright CI video/traces e relatório de testes.
- Comparação baseline single instance vs K8s replicas / caches e intervalo de confiança.
- Projetos separados em `apps` mas plataforma interoperável e implantação independente.
