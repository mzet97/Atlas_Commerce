# 06 — Arquitetura-alvo, padrões de projeto e ADRs

> A implementação começa **depois** da aprovação dos modelos do problema. Aqui são registradas decisões de engenharia candidatas, não scaffolds implementados.

## 1. Dois produtos, uma plataforma de domínio
**Atlas Storefront (Customer Experience / Data Plane):** `apps/storefront-next` consome `commerce-api/bff` (HTTP/JSON). Os microserviços Python são separados por *business capability*, não por entidades genéricas. Serviços candidatos: Catalog, Offer/Pricing, Search/Discovery, Cart, Checkout/Saga, Order, Inventory, Payment, Fulfillment, Customer, Returns, Reviews, AI Shopping Assistant, Notification. Serviços emergem gradualmente por fatia vertical; não criar dezenas de serviços vazios.

**Atlas Control (Admin Experience / Control Plane):** `apps/control-angular` consome **uma aplicação FastAPI em monólito modular**, módulos: Catalog Operations, Stock Operations, Price Operations, Order Ops, Returns Ops, IAM Governance, Approval Workflow, Audit, Reports e Operational Monitoring. Pode possuir seu DB para **processos administrativos** (approvals, audit, cases), mas **não** persiste o estado canônico de Catalog, Offer, Inventory, Order ou Payment. Para editar, envia comando ao owner via contrato (gRPC ou gateway de comando autorizado); para consultar, usa projeções. Sem acesso direto às coleções de microserviço.

**Repositórios:** dois projetos Git distintos (`atlas-storefront`, `atlas-control`), com pipelines e releases independentes. O terceiro repositório `atlas-platform-contracts` contém apenas contratos públicos versionados e templates/infra compartilhados; sua existência não transforma os dois produtos em um monólito distribuído.

**Shared Platform:** contratos Protobuf/OpenAPI/AsyncAPI/JSON Schema, IAM, observabilidade, CI, deployment, mocks de PSP/shipping e infraestrutura. Compartilhamento de código apenas utilitário, sem importar entidades/domain services através das fronteiras.

## 2. Estilo interno Python
Camadas por bounded context: `domain` (entidades, VOs, eventos, regras), `application` (comandos/queries/handlers/ports/UoW), `infrastructure` (Mongo, PG, Kafka, Rabbit, Redis, gRPC, PSP), `presentation` (FastAPI/gRPC adapter). **DIP**: domain nunca depende de FastAPI/Motor/Kafka. Isolar frameworks e evitar classes abstratas para tudo.

| Padrão | Aplicação concreta | Evitar |
|---|---|---|
| Repository | Persistir agregados Mongo e buscar por ID | Repositório genérico universal CRUD |
| Unit of Work | Mongo transaction para aggregate + outbox | Transação distribuída fictícia |
| Factory | Criar Aggregate Order/Quote com invariantes | Factory onde construtor simples basta |
| Strategy | Frete, imposto, discount eligibility, payment provider | Condicionais dispersos por endpoints |
| Adapter / Ports & Adapters | PSP, Kafka, Mongo, transportadoras, modelo LLM | Domínio acoplado a SDKs |
| Specification / Policy | Regras de elegibilidade, estoque, permissão | Regras somente na UI |
| CQRS Handlers | Commands separados de Queries e DTOs | Comando lendo PG para verificar saldo final |
| Saga / Process Manager | Checkout pagamento/reserva/pedido | Chamadas distribuídas sem compensação |
| Outbox / Inbox | Entrega recuperável e consumo deduplicado | Publicar evento antes/depois de commit sem recovery |
| Circuit Breaker / Bulkhead | PSP, gRPC, AI, frete | Retry infinito, retry de mutação sem idempotency key |

SOLID deve ser avaliado por mudanças concretas: abrir novo PSP sem alterar Order domain, trocar Mongo adapter sem reescrever rules, testar inventory domain sem containers, restringir permissões sem mudar UI.

## 3. Comunicação — por que usar as quatro soluções
| Tecnologia | Responsabilidade | Exemplo | Contrato e garantia |
|---|---|---|---|
| HTTP/JSON | Navegadores, APIs externas | Next.js → BFF, Angular → Admin API | OpenAPI, versionamento, auth, rate limit |
| gRPC | Consulta/comando síncrono interno quando útil | Checkout → Pricing. Admin Command Gateway → Inventory | Proto, deadlines, health, retry controlado |
| RabbitMQ | Tarefas/workflows duráveis e pontuais | Notificar cliente, gerar etiqueta, import job | quorum queue, manual ACK, DLQ, retry e idempotência |
| Kafka | Log de eventos de domínio/integracão, CDC, analytics | OrderConfirmed → PG projection → analytics | key por agregado, schema registry, replay, consumer inbox |

**Anti-padrão:** emitir o mesmo evento de negócio independentemente para RabbitMQ e Kafka no handler de request. Emitir uma vez via outbox para Kafka; criar tasks de Rabbit por um consumidor/bridge idempotente, se necessário.

## 4. IAM
Keycloak como OIDC/OAuth2 provider self-hosted. Fluxo Authorization Code + PKCE, sessão server-side/BFF quando viável, access tokens curtos, refresh rotation conforme configuração, MFA obrigatório para admins, machine identities para serviços e mTLS em tráfego interno crítico. `scope` por warehouse/market/seller sobre RBAC; aprovações e segregação de deveres. Permissões sempre verificadas no backend owner, mesmo se a UI esconde botão.

## 5. Deployment
**Exceção importante para CQRS:** a regra Mongo-write/PostgreSQL-read é para **dados de negócio da plataforma**. O Keycloak necessita de sua própria persistência operacional (por exemplo, um PostgreSQL privado de IAM), que não é projeção de pedidos. Observabilidade e demais ferramentas também usam stores próprios. Não impor CQRS artificialmente aos bancos internos de infraestrutura.

**Local:** Docker Compose profiles `core`, `data`, `messaging`, `observability`, `ai`, `mock-integrations` e versões mínimas (replica set Mongo e broker local; zero obrigação de iniciar tudo). **Kubernetes:** Helm/Kustomize, GitOps Argo CD opcional, namespaces, NetworkPolicy, ExternalSecrets/Vault, HPA/KEDA, Ingress/Gateway API, StatefulSets/operadores para dados, backup/restore, registry, certificação TLS e probes. Para self-managed de produção, serviços stateful precisam HA, storage persistente, recuperação e manutenção de operadores; Docker Compose é ambiente de desenvolvimento e demos, não substituto de K8s HA.

**Observabilidade:** OTel SDK/Collector → Grafana Mimir/Prometheus, Loki, Tempo e Pyroscope, com dashboard de negócio e técnico, SLO, alertas e tracing `checkout_id`/`order_id` em atributos com cautela PII. `docker-otel-lgtm` apenas para desenvolvimento; produção com componentes segregados e persistência própria.

## 6. Scaffolding via CLI; sem construir boilerplate manualmente
- Python: `uv init --package ...`; `uv add ...`, `uv lock`, `uv sync`, `uv run pytest`.
- Templates de microservice/admin compartilhados: criar um template **Copier** controlado pelo repositório; `uvx copier copy ...` (após template aprovado). Gera Clean Architecture, lint/test/CI/health/telemetry/Makefile a partir de uma origem versionada.
- Next.js: `pnpm create next-app` com TypeScript/App Router.
- Angular: `ng new`/`ng generate` com strict TS e arquitetura feature-based.
- Protobuf: `buf generate`, lint e breaking change check.
- Manifests: Helm chart template / `helm create` e `skaffold init` para desenvolvimento de K8s. **Skaffold não é o gerador principal de projeto de negócio**: detecta artefatos e gera config e, opcionalmente, manifests básicos.
- Packages: versões **stable mais novas verificadas no dia do bootstrap**, com arquivos lock (`uv.lock`, `pnpm-lock.yaml`), SBOM, Renovate/Dependabot e CI compatibilidade. Não usar `latest` em deploy reproduzível. Versões numéricas deste documento não são congeladas sem validação de suporte e segurança.

## 7. ADRs (resumo)
### ADR-001 — Storefront microservices + Control modular monolith
**Status:** proposto. **Racional:** experiências distintas e cadência diferente; domínio canônico único. **Consequência:** Admin depende de APIs de negócio; exige contract testing e disponibilidade de comandos.

### ADR-002 — CQRS Mongo command / PostgreSQL query
**Status:** proposto sob validação de workload. **Racional:** exercício de poliglot persistence e projeções. **Consequência:** complexidade/latência/eventual consistency; usar read-your-writes com tracking por versão; pagamento/inventário autoritativos no Mongo e PSP.

### ADR-003 — Kafka + RabbitMQ
**Status:** proposto. **Racional:** distinguir stream histórico e task queue confiável. **Consequência:** overhead operacional real; documentar quando cada um é obrigatório.

### ADR-004 — Domain outbox transacional no MongoDB
**Status:** proposto. **Racional:** reduzir perda em dual write. **Consequência:** transações locais, CDC, replay, versionamento e dedup obrigatórios.

### ADR-005 — AI agent human-approved writes
**Status:** proposto. **Racional:** LLM não é autoridade de produto/preço/pagamento. **Consequência:** somente ferramentas allowlisted, confirmação explícita, defesa contra prompt injection e limites de gasto/tokens.

### ADR-006 — Monólito Control não reescreve estado do Storefront
**Status:** proposto. **Racional:** reduzir split-brain. **Consequência:** modular monolith próprio controla aprovação/ações/auditoria e orquestra serviços proprietários; não duplicar write model.

## Referências de implementação (documentação oficial)
- uv: https://docs.astral.sh/uv/guides/projects/
- FastAPI: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- create-next-app: https://nextjs.org/docs/app/api-reference/cli/create-next-app
- Angular CLI: https://angular.dev/cli/new
- Copier: https://copier.readthedocs.io/
- Skaffold init: https://skaffold.dev/docs/init/
- Debezium MongoDB: https://debezium.io/documentation/reference/stable/connectors/mongodb.html
- Rabbit quorum: https://www.rabbitmq.com/docs/quorum-queues
- Kafka delivery semantics: https://docs.confluent.io/kafka/design/delivery-semantics.html
- Keycloak: https://www.keycloak.org/guides
- Grafana OTel: https://grafana.com/docs/opentelemetry/
- gRPC deadlines: https://grpc.io/docs/guides/deadlines/
