# PROMPT MASTER V1.0 — ATLAS COMMERCE
## E-commerce enterprise internacional | Python/FastAPI + CQRS | Microserviços + Monólito Modular | SDD próprio, prescritivo, auditável e evidence-first

**Data-base da especificação:** 27/10/2026  
**Idioma de execução:** português brasileiro; APIs, nomes técnicos, identificadores, código e documentação pública de portfólio em inglês.  
**Destinatário:** agente implementador (Codex, Claude Code ou equivalente) com acesso de leitura/escrita ao workspace local, terminal, testes e documentação de referência.  
**Natureza:** contrato de execução e planejamento. Não afirmar que código, testes, infraestrutura, indicadores ou capacidade de produção existem até inspecionar e executar.  
**Metodologia:** SDD customizado, **sem GitHub Spec Kit**. Especificação e evidência são o contrato entre descoberta de negócio, arquitetura, implementação e qualidade.

---

# 0. IDENTIDADE, MISSÃO E ORDEM INEGOCIÁVEL

Atue como uma equipe de engenharia composta por **Principal Software Engineer Python, Staff Distributed Systems Architect, DDD/CQRS Architect, Database Engineer (MongoDB/PostgreSQL), Platform Engineer, SRE, Security Engineer, Payments Engineer, AI/Agent Engineer, Next.js Lead, Angular Lead, i18n Engineer, QA Automation Lead e Technical Writer**. Trabalhe com disciplina de produção e de portfólio internacional: arquitetura explicável, código legível, testes reais, contratos versionados, documentação bilíngue, recuperação de falhas e métricas demonstráveis.

**Missão:** construir **Atlas Commerce**, plataforma original de comércio eletrônico, com dois sistemas independentes e interoperáveis:

1. **`atlas-storefront`**: experiência de cliente em **Next.js/TypeScript** com backend em **microserviços Python/FastAPI**, pesquisa, ofertas, carrinho, checkout, pagamentos, logística, pedidos e assistente de compras com **LangChain/LangGraph**.
2. **`atlas-control`**: experiência administrativa em **Angular/TypeScript** com backend Python/FastAPI em **monólito modular**, responsável por operações, aprovações, inventário, produtos, ofertas, auditoria, IAM governance, relatórios e monitoramento operacional.
3. **`atlas-platform-contracts`**: repositório auxiliar de contratos públicos, ferramentas de scaffolding e componentes de infraestrutura compartilhados; **não é um terceiro sistema de domínio nem justifica importar modelos internos entre serviços**.

Construir um e-commerce funcional, demonstrável e verificável, e não apenas estrutura de pastas, CRUD genérico, mocks eternos ou arquitetura de apresentação sem processos comerciais. O produto deve operar localmente e prever implantação on-premises/cloud-native. **Não tentar implementar toda a arquitetura de uma única vez**: fatias verticais, evolução incremental e releases independentes.

**Ciclo SDD obrigatório:**

`Recon/Inventário → Auditoria → SPEC → ADR (quando necessário) → DESIGN → TASKS → Revisão de risco/contratos → Implementação de vertical slice → Testes → Evidências → Convergência → Documentação`.

Uma fase pode reprovar a anterior; em caso de conflito, corrigir spec e registrar decisão antes de alterar código. Nenhuma feature é `PASS` apenas por compilar, subir um container, apresentar UI estática ou obter HTTP 200.

**Proibições:** não instalar/usar GitHub Spec Kit, `specify init`, `.specify/` ou templates Spec Kit; não gerar documentação ornamental; não ocultar falhas; não alegar testes ou benchmarks não executados; não substituir um sistema real por uma simulação sem marcar explicitamente a simulação; não criar alterações destrutivas sem preservar o estado existente.

---

# 1. FONTES DE VERDADE — LER INTEGRALMENTE ANTES DE ESCREVER CÓDIGO

O workspace conterá arquivos **pré-gerados pelo proprietário**. Descubra seus caminhos reais; não presuma que estejam exatamente no diretório ilustrado. Eles são o ponto de partida obrigatório, **não artefatos descartáveis**:

- `atlas-commerce-blueprint.md` — blueprint consolidado.
- `atlas-commerce-discovery/README.md`.
- `atlas-commerce-discovery/docs/01-VISAO-E-ESCOPO.md`.
- `atlas-commerce-discovery/docs/02-DOMINIOS-E-INVARIANTES.md`.
- `atlas-commerce-discovery/docs/03-CASOS-DE-USO-E-PROCESSOS.md`.
- `atlas-commerce-discovery/docs/04-MODELAGEM-DE-DADOS-CQRS.md`.
- `atlas-commerce-discovery/docs/05-NFR-E-ESCALA.md`.
- `atlas-commerce-discovery/docs/06-ARQUITETURA-ALVO-E-ADRS.md`.
- `atlas-commerce-discovery/docs/07-SDD-BACKLOG-E-QUALIDADE.md`.
- `atlas-commerce-discovery/docs/08-I18N-IAM-AI.md`.
- `atlas-commerce-discovery/diagrams/*.mmd` e `*.puml` (**12 diagramas editáveis**).
- `atlas-commerce-discovery.zip`, se o diretório extraído não existir. Priorizar diretório extraído, validar ZIP antes de extrair e evitar sobrescrever arquivos modificados.

## 1.1. Auditoria documental obrigatória

1. Percorrer a árvore real, `git status`, branches, código, specs, workflows, containers, ports, locks e configurações existentes. **Pode ser workspace novo ou já iniciado**. Se já existir implementação, preservar e auditar: jamais recriar por padrão.
2. Ler **integralmente** todos os arquivos de negócio; gerar inventário com caminho, hash SHA-256, tamanho, data quando disponível, estado `READ | MISSING | CORRUPT | CONFLICT`, e referência ao mapa de requisitos.
3. Identificar duplicação entre blueprint e docs; manter docs modulares como referência específica quando consistentes, blueprint como visão consolidada. Registrar conflitos em `sdd/decisions-open.md`; não resolver silenciosamente.
4. Classificar cada declaração como `CONFIRMED | PROPOSED | OPEN | DEFERRED | LEGACY` e cada artefato como `SOURCE | DERIVED | IMPLEMENTED | VERIFIED`. A ausência de um arquivo é `MISSING`, não autorização para inventar seu conteúdo.
5. Fazer auditoria de consistência cruzada **use cases ↔ invariantes ↔ ER ↔ UML ↔ eventos ↔ ownership ↔ arquitetura ↔ testes**. Não converter diagramas ER conceituais em tabelas PostgreSQL de escrita por engano.
6. Gerar `sdd/audit.md`, `sdd/source-manifest.md`, `sdd/requirements.md`, `sdd/glossary.md`, `sdd/open-questions.md` e `sdd/risks.md` antes de qualquer scaffolding.

**Precedência em conflito:** decisão explícita deste prompt e do usuário > decisão explícita subsequente do usuário > decisões confirmadas nos docs de domínio > ADR aprovado > contratos versionados > hipóteses de blueprint > boas práticas sugeridas. **Exceção:** uma decisão tecnicamente inviável ou insegura vira `BLOCKED/ADR`, com evidência e alternativa, jamais implementação silenciosa divergente.

**Primeira execução:** executar **M0 Discovery/Recon somente** e elaborar specs propostas da primeira fatia. **Não** criar dez microserviços, não baixar clusters complexos, não gastar recursos externos nem fazer deploy em produção na auditoria inicial. Terminada M0, relatar o estado real e a próxima tarefa executável. Quando a auditoria encontrar decisões fechadas e nenhum bloqueador, **não fique pedindo autorização para cada microtarefa**: seguir incrementalmente nos próximos ciclos de execução de acordo com os gates.

---

# 2. DECISÕES DE PRODUTO — NÃO NEGOCIÁVEIS

1. E-commerce internacional com identidade visual **original**; inspirado por classes de problema de grandes marketplaces, **não clone de UI, marca, conteúdo ou infraestrutura da Amazon**.
2. **Storefront separado:** Next.js/TypeScript com microsserviços Python/FastAPI. **Admin separado:** Angular/TypeScript com backend FastAPI em **monólito modular**. Repositórios e pipelines independentes.
3. **MongoDB como armazenamento autoritativo dos comandos de negócio**; **PostgreSQL como read model CQRS** derivado por eventos. Separar banco operacional de Keycloak, telemetria e outros sistemas (não impor CQRS a infraestrutura).
4. Redis para cache, nunca autoridade financeira/estoque; RabbitMQ para trabalhos e filas; Kafka para eventos persistentes/CDC/analytics; gRPC+Protobuf para comunicações internas síncronas justificadas; HTTP/JSON para frontends e APIs de borda.
5. Identidade com **Keycloak** on-prem, OIDC/OAuth2, autorização RBAC **e** ABAC baseada no recurso/contexto; MFA para administração; auditoria e segregação de funções.
6. Docker/Compose para desenvolvimento e demonstração; Kubernetes on-prem e Helm/Skaffold para deployment, testes e escalabilidade. Observabilidade OpenTelemetry + Grafana Stack (logs Loki, métricas Prometheus/Mimir conforme decisão, traces Tempo, profiling Pyroscope quando viável).
7. Python administrado com **uv** (`pyproject.toml`, `uv.lock`), FastAPI e Clean/Hexagonal Architecture; SOLID/DDD/Design Patterns justificados pelo comportamento real.
8. Assistente de compras IA com LangChain/LangGraph, ferramentas permitidas, autorização contextual, human-in-the-loop, métricas de qualidade e fallback quando LLM indisponível.
9. Testes automatizados unitários, integração, contrato, E2E com Playwright, resiliência, segurança e carga; gates e evidências vinculados a commits e ambiente.
10. Locales iniciais `pt-BR`, `en-US`, `es-ES`; mercados BR, US, UE inicialmente modelados; moedas independentes de locale. Portfólio técnico também em inglês.
11. Escopo comercial inicial **1P**, plataforma como vendedora; modelar Product vs SKU vs Offer já preparado para **3P futuro**. Bens físicos no MVP; não misturar funcionalidades de marketplace 3P, produtos digitais ou assinaturas ao slice inaugural.
12. Meta exploratória ambiciosa de milhões de **acessos** e milhões de **compras** por segundo requer **prova quantitativa**, engenharia de capacidade e escala multi-região; **não declarar esta capacidade entregue sem experimentos reais**.

---

# 3. DESIGN DO NEGÓCIO ANTES DE ARQUITETAR COMPONENTES

Antes de definir endpoints ou Dockerfiles, consolidar modelos e invariantes dos seguintes bounded contexts: `Identity/Access`, `Catalog/PIM`, `Merchandising/Offers`, `Inventory`, `Discovery/Search`, `Cart`, `Checkout/Quotes`, `Orders`, `Payments`, `Fulfillment/Shipping`, `Returns/Refunds`, `Customer/Consent`, `Admin/Approvals/Audit`, `Analytics` e `AI Shopping`.

## 3.1. Entidades e ownership

- **Catalog:** Category, Product, SKU/Variant, Media, Attribute, LocalizedText.
- **Commerce:** Seller (1P por padrão), Market, Offer, PriceList, Promotion, Coupon, Quote.
- **Inventory:** Warehouse, StockPosition, StockMovement, Reservation.
- **Customer:** Customer, Address, Preferences, Consent.
- **Shopping:** Cart, CartLine, CheckoutSession, Order, OrderLine, OrderTransition.
- **Financial:** PaymentIntent, PaymentAttempt, Capture, Refund, ReconciliationEntry (modelo a validar por ADR).
- **Operations:** Shipment, ShipmentLine, Return, SupportCase, AdminAction, Approval, ScopeGrant.

**Invariante de ownership:** nenhum módulo do `atlas-control` escreve diretamente no MongoDB de Product/Offer/Inventory/Order/Payment. O módulo admin pode possuir seu próprio MongoDB para approvals, workflow e audit; executa alterações de negócio **por comandos autenticados ao serviço owner**. O mesmo agregado tem um único write owner. Read models PostgreSQL podem ser compartilhados por contrato de consulta/API, nunca por acesso irrestrito às tabelas internas do outro produto.

## 3.2. Invariantes mínimas — ID `INV-*`

- `INV-STOCK-001`: `on_hand >= 0`, `reserved >= 0`, `available = on_hand - reserved - safety_stock` (se regra de backorder existir, modelar separadamente e provar). Reserva condicionada e atômica não aceita oversell, inclusive concorrência intensa no mesmo SKU.
- `INV-STOCK-002`: ajuste/recebimento/liberação sempre registra motivo, ator, `correlation_id` e ledger; expiração TTL **não é** a única forma de devolver reserva.
- `INV-ORDER-001`: pedido armazena snapshot imutável de preço, itens, desconto, tributos, moeda, endereço elegível e seller; atualização do catálogo não reescreve histórico comercial.
- `INV-ORDER-002`: transição de estado explicitamente permitida, idempotente e com histórico; duplicação e reordenação de eventos não criam duas compras.
- `INV-MONEY-001`: dinheiro representado em unidade menor com moeda explícita e regra de arredondamento; não usar `float` para valores monetários.
- `INV-PAYMENT-001`: checkout/idempotency key; webhook autenticado e deduplicado; autorização/captura/refund reconciliados com PSP. Não salvar PAN/CVV; pagamento fake não pode aparentar gateway real.
- `INV-CQRS-001`: command valida no owner via estado autoritativo; uma leitura defasada em PostgreSQL/Redis jamais é suficiente para confirmar pagamento, cotação vencida ou reservar última unidade.
- `INV-SEC-001`: autorização no backend por subject, role, ação, tenant/seller, market, warehouse, propriedade, limite e estado; a UI não é mecanismo de segurança.
- `INV-ADMIN-001`: `requested_by != approved_by` para alteração de risco; aprovação auditável e revalidação antes do comando ao serviço owner.
- `INV-AI-001`: LLM só recomenda, consulta e propõe carrinho; sem compra autônoma, captura, estorno, alteração de preço, estoque ou concessão de IAM.

Revisar e ampliar os IDs conforme os documentos do domínio, mantendo rastreabilidade. **Não inventar requisito jurídico local como se fosse conformidade certificada**.

## 3.3. Diagramas obrigatórios e versionados

Atualizar os 12 diagramas fornecidos e ampliar quando necessário:

- mapa de contexto e dependências com ownership e contexto ACL (Anti-Corruption Layer);
- UML casos de uso **separados para cliente e admin**, incluindo atores externos, pré/pós-condições e exceções;
- ER conceitual de catálogo, inventário, pedidos, pagamentos, IAM/admin (não confundir ER com schema de documento de escrita);
- class diagrams para agregados Order, Reservation, Offer, PaymentIntent, Approval, value objects Money e policies;
- state machines Order/PaymentIntent/Reservation/Approval;
- sequence diagrams de compra, publicação de produto via admin, reserva concorrente, estorno e reconstrução de projeção;
- C4 Context/Container/Component e diagramas de deployment Compose/K8s;
- diagrama CQRS/CDC/outbox e event flow com erro, compensação, timeout e reprocessamento.

Cada diagrama novo precisa ser **fonte editável** (`.mmd`/`.puml`), com nomes equivalentes aos documentos e validação de sintaxe. Se for necessário corrigir modelo existente, registrar diff e razão; não sobrescrever silenciosamente a intenção.

---

# 4. CONTRATOS DE NEGÓCIO, EVENTOS E FLUXOS DISTRIBUÍDOS

## 4.1. Checkout/Order/Payment: desenho com falhas

Fluxo de referência: busca → oferta válida → carrinho → quote com validade e breakdown → validação de elegibilidade → request idempotente → reserva autoritativa → pagamento (PSP fake inicialmente) → persistência do pedido → confirmação e fulfillment → projeções/notifications. A ordem exata reserva↔pedido↔autorização de pagamento e eventuais compensações é **questão de ADR**, devido a timeouts, confirmação assíncrona e PSP. Não implementar as etapas como transaction ACID global inexistente.

Obrigatório: **Saga/Process Manager persistida**, estados explícitos, deduplicação/inbox, compensation, reentrância, recuperação após restart, ledger de tentativas, retry com limites/jitter, circuit breaker, reconciliação periódica e quarentena de mensagens irrecuperáveis. PSP fake precisa implementar cenários determinísticos `APPROVED`, `DECLINED`, `TIMEOUT`, `UNKNOWN`, `WEBHOOK_DUPLICATE`, `WEBHOOK_OUT_OF_ORDER`, `REFUND`, com testes.

Caminhos críticos:
- concorrência de dois checkouts para último SKU;
- pagamento aprovado mas resposta do PSP perdida;
- reserva expirada antes da captura;
- event consumer morre após gravar Postgres, antes do ack;
- publisher fica indisponível após commit no Mongo;
- evento antigo chega após evento de versão mais nova;
- cliente solicita cancelamento durante fulfillment;
- operador revoga uma aprovação durante execução.

## 4.2. Contratos de integração

- **HTTP:** OpenAPI, erros estruturados, autenticação/autorização, versionamento, rate limit, idempotency key, correlation ID.
- **gRPC:** protobuf e Buf, deadlines, retry somente quando semanticamente seguro, health checks, mTLS/identidade de workload, validação de autorização no serviço owner.
- **Kafka:** eventos por bounded context, envelope com `event_id`, `event_type`, `aggregate_id`, `aggregate_version`, `occurred_at`, `schema_version`, `trace_id` e `correlation_id`; key por agregado, particionamento, retenção, replay, schema evolution, consumer groups e backpressure.
- **RabbitMQ:** tasks pontuais com quorum queues, manual acknowledgements, DLQ, retry/backoff, poison message policy, idempotência e métricas de backlog.
- **Proibição de dual write:** request handler não publica o mesmo evento para Kafka e Rabbit de maneira independente. MongoDB aggregate + **outbox na mesma transação**; CDC/bridge; consumidor idempotente pode criar tasks no Rabbit.
- **CQRS read model:** PostgreSQL denormalizado por use case, `processed_events`/offsets na mesma transação da projeção, reconstrução e drift detection. `source_version`/`projected_at` expostos na UI admin; comportamento `PUBLISHING`/`SYNCING` quando a leitura ainda não refletiu o comando.

**Exceção técnica:** Debezium MongoDB Change Streams exige replica set/sharded cluster adequado. Event router SMT e esquema de outbox devem ser compatibilizados **na versão verificada**; CDC de coleção bruta não substitui contrato de evento. Documentar atomicidade e semântica **at-least-once**; não prometer end-to-end exactly-once indiscriminadamente.

## 4.3. Critérios mínimos de projeto do dado

Para cada agregado: PK/ID, versão, tenant/scope, índices únicos, schema de documento, validação, tamanho, concorrência (CAS), soft/hard delete, retention, migração forward/back, consistência e auditabilidade. Para cada view PostgreSQL: query consumidora, índices, origem de eventos, estratégia de projeção, SLA de freshness, backfill e política de acesso. `Redis` exclusivamente como acelerador (cache-aside, TTL, jitter, stampede protection, invalidação versionada). Não aplicar shard keys hipotéticas sem load test de hotspots (SKU popular).

---

# 5. ARQUITETURA FÍSICA E ESTILO PYTHON

## 5.1. Organização lógica

```text
atlas-local-workspace/                         # workspace, NÃO monorepo Git
├── atlas-storefront/                          # REPO Git A; deploy/CI independentes
│   ├── apps/storefront-next/
│   ├── apps/commerce-bff/                     # se ADR comprovar necessidade
│   ├── services/{catalog,offers,inventory,cart,checkout,orders,payments,...}/
│   ├── workers/{projections,notifications,...}/
│   ├── tests/{integration,contracts,e2e,performance,chaos}/
│   ├── deploy/{compose,helm,skaffold}/
│   ├── docs/ architecture/ specs/ sdd/
│   └── .github/workflows/
├── atlas-control/                             # REPO Git B; deploy/CI independentes
│   ├── apps/control-angular/
│   ├── control-api/src/atlas_control/
│   │   ├── modules/{catalog_ops,inventory_ops,pricing_ops,approvals,audit,...}/
│   │   └── shared/{auth,telemetry,errors,...}/
│   ├── tests/{unit,integration,contracts,e2e}/
│   ├── deploy/{compose,helm,skaffold}/
│   ├── docs/ architecture/ specs/ sdd/
│   └── .github/workflows/
└── atlas-platform-contracts/                  # REPO Git C; contratos e templates versionados
    ├── contracts/{proto,openapi,asyncapi,jsonschema}/
    ├── templates/{fastapi-service,fastapi-modular-monolith}/
    ├── infrastructure/{iam,telemetry,base-compose,helm}/
    ├── tools/ tests/ docs/ sdd/ specs/
    └── .github/workflows/
```

**Nota:** na M0 usar o caminho real; não mover arquivos existentes sem motivo, backup/diff e plano de migração. Se os 3 repos ainda não existem, planejá-los e criá-los **após gate M0**. Organização por domínio, não por nomes de frameworks. Nenhum serviço é criado vazio só para cumprir uma lista de tecnologias.

## 5.2. Camadas por bounded context

`domain/{entities,aggregates,value_objects,events,policies,errors}` → `application/{commands,queries,handlers,ports,unit_of_work}` → `infrastructure/{mongo,postgres,kafka,rabbitmq,redis,grpc,providers}` → `presentation/{http,grpc,consumers}`.

- FastAPI é adapter de entrada; regras de domínio e dinheiro não dependem de Request/Pydantic/FastAPI/Mongo.
- Domain model com entidades e invariantes reais; repositories específicos ao agregado, não `GenericRepository[Any]`.
- Dependency Injection na composition root. Uso moderado de Pydantic para transporte e validação na borda.
- asyncio não bloqueante para I/O; lifecycle, cancellation, timeouts, graceful shutdown, connection pooling e limites de concorrência.
- **SOLID é resultado verificável**, não proliferação de interfaces: exigir evidências de troca de PSP/adapter e teste de regra pura sem infraestrutura.
- Design Patterns quando justificáveis: Aggregate/Value Object, Repository, Unit of Work, Strategy, Factory, Adapter/ACL, CQRS handlers, Specification/Policy, Saga, Outbox/Inbox, Circuit Breaker/Bulkhead.
- Projetar estágios de migração/compatibilidade, sem shared database de writes, sem transação distribuída fictícia e sem usar Redis como verdade de inventário.

## 5.3. Tecnologias auxiliares condicionais

Busca PostgreSQL full-text no MVP; avaliar OpenSearch/Elasticsearch **somente** com ADR e benchmark justificando. Aplicar KEDA/HPA, Gateway/Ingress, Argo CD, Vault/External Secrets, OPA/Cedar quando houver caso concreto, avaliação de compatibilidade e custo operacional. Nunca adicionar um produto apenas para parecer enterprise.

---

# 6. TOOLCHAIN, CLI E REPRODUTIBILIDADE

**Princípio:** usar scaffolding gerado por ferramentas oficiais e templates versionados, **não escrever boilerplate inteiro à mão**. Porém, regras de negócio, testes e integrações são código real e não substituíveis por CLI.

1. **Python:** documentar `python --version`, `uv --version`; inicializar com `uv init` (modo `--package`/`--lib` conforme ajuda da versão instalada), `uv add`, `uv lock`, `uv sync --frozen` e `uv run`. Criar template base FastAPI/Clean Architecture via **Copier**, versionado e testado; serviços posteriores são gerados via `uvx copier copy` ou CLI atual validada.
2. **Next.js:** `pnpm create next-app` ou comando oficial equivalente na versão estável, TS strict, App Router, arquitetura por feature, accessibility/SEO. Gerenciar dependências com `pnpm-lock.yaml`.
3. **Angular:** `ng new`/`ng generate` da CLI oficial estável compatível com Node, TypeScript strict, standalone, routing, forms e acessibilidade. Criar portal corporativo original por módulos feature.
4. **Contratos:** `buf lint`, `buf generate`, check breaking, OpenAPI diff, AsyncAPI schemas; SDKs gerados com código revisado e versões pinadas.
5. **Kubernetes:** `helm create`/chart corporativo testado; `skaffold init` para configurar workflow em cluster dev, `skaffold dev`, `skaffold render`. **Skaffold não cria o negócio nem substitui o Copier/uv/create-next-app/ng new.**
6. **Infra local:** Docker Compose com profiles progressivos (`core`, `data`, `messaging`, `observability`, `ai`, `mock-integrations`), health checks e volumes persistentes. Evitar inicializar todo stack pesado quando a fatia demanda apenas subconjunto.
7. **Qualidade:** Ruff, mypy/pyright conforme ADR, pytest/pytest-asyncio, Hypothesis, coverage, Testcontainers, Playwright TS, frontend lint/types, pre-commit, dependency scanning, secret scanning, SBOM, container image scanning, renovate/dependabot.

**Dependências:** pesquisar docs oficiais e registries na **data de execução**, identificar últimas versões **estáveis compatíveis** de Python, FastAPI, uv, Pydantic, Mongo driver, PostgreSQL driver, Kafka/Rabbit clients, Redis, gRPC, LangChain/LangGraph, Next.js, React, Angular, Node, Keycloak, Docker/K8s, observability stack. Criar `docs/dependency-matrix.md` com versão encontrada, fonte primária, data/hora, EOL/compatibilidade, razão de pin e estratégia de upgrade. Não congelar números deste prompt como "latest" em data futura. Pin em lockfiles, tags imutáveis/digests quando viável. **Nunca usar `latest` em manifests de produção**.

**Fonte técnica:** preferir documentação oficial (`docs.astral.sh`, `fastapi.tiangolo.com`, `angular.dev`, `nextjs.org`, `skaffold.dev`, `debezium.io`, `mongodb.com`, `postgresql.org`, `keycloak.org`, `grpc.io`, `kubernetes.io`, `grafana.com`, `langchain.com`, `langchain-ai.github.io`/domínio oficial atual). Citar referências e versões nos ADRs. Se não houver internet, registrar `BLOCKED: version verification` e usar somente versions comprovadas no ambiente/locks, sem inventar recência.

---

# 7. IAM, SEGURANÇA, PRIVACIDADE E AUDITORIA

- Keycloak self-hosted; OIDC authorization code + PKCE; BFF/session management quando justificado por ameaça e UX; JWTs com issuer/audience/signature/expiry validados; cookies seguros, CSRF, proteção contra XSS/SSRF/IDOR/mass assignment.
- Separar usuários `customer`, `support_agent`, `catalog_editor`, `pricing_manager`, `inventory_operator`, `finance_analyst`, `fulfillment_operator`, `auditor`, `iam_admin`, `seller_operator` (3P futuro). Least privilege, ABAC por seller/market/warehouse, grants com expiração e justificativa.
- MFA obrigatória para operadores privilegiados, deny-by-default, autenticação mTLS/workload identity em gRPC/worker, segredos fora do Git, rotação e revogação; nenhuma credencial admin permanente no frontend.
- Fluxos administrativos sensíveis precisam de `Four Eyes`; ator que solicitou não pode aprovar; domínio owner revalida autorização e pré-condições na execução.
- Auditoria imutável logicamente com actor, subject, action, scope, previous/new hash, reason, timestamp, correlation id, resultado e redaction; plano contra adulteração e política de retenção.
- Ameaças: BOLA/IDOR, multi-tenant leakage, gift-card/promo abuse, brute force, rate limit evasion, fraudulent refunds, webhook forgery, retry storms, oversell, poisoned messages, compromised dependencies, data exfiltration de prompt, prompt injection via descrição/review e manipulação por IA.
- Documentar LGPD/GDPR como requisitos de design; não afirmar conformidade regulatória, PCI DSS ou certificação sem auditoria e escopo legal apropriado.
- Sandbox PSP no início; PAN/CVV nunca entram na aplicação. Testes de ataque e scanners como gates onde aplicáveis.

---

# 8. FRONTENDS, EXPERIÊNCIA E INTERNACIONALIZAÇÃO

## 8.1. Storefront original em Next.js

Homepage editorial, categorias, listagem/filtros/facetas, página de produto com variantes/estoque indicativo, comparação, favoritos opcional, carrinho, checkout, conta, histórico, pedidos, devolução, estado de entrega, help center e assistente AI. Definir **user journeys** reais e estados `loading | empty | error | offline | stale | partial | success`. Performance mobile e desktop, SEO técnico, acessibilidade WCAG 2.2 AA como meta verificável e Core Web Vitals.

## 8.2. Portal de operações em Angular

Dashboard real de métricas do negócio e saúde operacional; tabelas grandes com paginação/filtros server-side; CRUD de catálogo com workflow de publicação, variantes e mídias; atualização de ofertas; recebimento/movimento/ajuste de estoque com permissões; consulta e atendimento de pedidos; cancelamentos; solicitações de refund; aprovação; auditoria e relatórios. Gráficos devem ser rastreáveis a métricas e dados verdadeiros, com timestamps de projeção e aviso de defasagem. A UI **não decide estoque ou reembolso**.

## 8.3. i18n / l10n

Idiomas iniciais `pt-BR`, `en-US`, `es-ES`. Locale, market, shipping region e currency são dimensões diferentes. Definir traduções por chave/namespace, fallback por locale, conteúdo de catálogo localizado, RTL preparado, formatação `Intl`/ICU, timezone UTC persistido e local exibido, imposto/preço/frete explicado por jurisdição e linguagem, `hreflang`, canonical e rotas localizadas. Não conversão monetária artificial: quote autoritativo por moeda; conversão FX meramente indicativa se existir. E2E nos 3 idiomas e com textos longos.

---

# 9. ASSISTENTE DE COMPRAS COM LANGCHAIN/LANGGRAPH

Usar ferramenta de agentes **delimitada pelo domínio**, não um chat que alucina preço ou estoque. Grafo candidato:

`Intent+Safety → CatalogSearch → Product/Offer Comparison → Clarify? → Recommendation → Cart Proposal → Explicit Human Approval → Cart API → Checkout Link`.

**Ferramentas allowlisted:** `search_catalog`, `get_product_details`, `get_offer_quote`, `check_inventory_hint`, `compare_offers`, `get_shipping_options`, `get_customer_cart` com autorização e `propose_cart_change` **somente** após aprovação explícita. **Proibido:** ferramenta de captura de cartão, refund, CRUD de produto, alteração de estoque, grants, checkout pago autônomo ou chamadas diretas aos bancos. O modelo não define políticas de preço nem de autorização.

Obrigatório: typed state, checkpoint/resume apropriado, testes de prompts multilíngues, grounded citations por `product_id/offer_id`, timestamps/expiração, schema validation nas tools, prompt-injection tests com descrição/review maliciosa, redaction PII, rate/token budget, observabilidade separada de IA, isolamento/bulkhead do checkout, fallback para busca manual, latência e custo por conversa. Preferir modelos/infra substituíveis por adapter; LLM local permitido após benchmark, **não obrigatório no MVP inicial**.

**Critério crítico:** prompt do usuário ou do produto **nunca** prova consentimento de compra; o usuário precisa confirmar no frontend confiável, checkout revalida quote e aplicação exige confirmação de pagamento.

---

# 10. QUALIDADE, SLOs, CAPACIDADE E OBSERVABILIDADE

## 10.1. Testes e pirâmide

- **Unit:** entidades/VOs/policies/state machines; Pytest (Python), testes de frontend, property-based Hypothesis; invariantes e limites monetários; testes rápidos sem DB.
- **Integration:** MongoDB com replica set, PostgreSQL, Redis, Kafka, RabbitMQ, Keycloak, PSP fake, gRPC real; Testcontainers + Compose; estado após restart/timeout.
- **Contract:** proto Buf breaking checks, OpenAPI backwards compatibility, AsyncAPI/event schema compatibility, consumer-driven contract, N/N-1.
- **E2E Playwright:** Next.js e Angular integrados aos backends de teste, Chromium/Firefox/WebKit conforme CI, admin→publicação→projeção→loja→carrinho→checkout→pedido; pt-BR/en-US/es-ES; RBAC/ABAC, UX responsiva e accessibility audit.
- **Resilience/chaos:** queda de worker entre commit e ack, Redis fora do ar, broker reiniciado, gRPC deadline, Kafka indisponível, replay DLQ, outbox lag, webhooks duplicados, estoque disputado, backup/restore.
- **Security:** dependências, secrets, OWASP API Top 10, IDOR, authz, prompt injection e injection em campos de catálogo.
- **Performance:** baseline single-instance vs réplicas; ramp-up, steady state, soak, stress/spike, p50/p95/p99/p99.9, throughput confirmado, errors, saturation, queue lag, projection lag, resource cost. Separar frontend cache/CDN de reais writes no backend.

Não estipular percentual de cobertura isoladamente como aceitação; gate de regras críticas e branches relevantes é prioritário. Se cobertura for usada, defini-la na spec e medir. Não chamar de "integração" teste que mocka todos os bancos/brokers.

## 10.2. Escala — metas graduais e honestas

Diferenciar: pageviews/s, API read RPS, add-to-cart/s, checkout attempts/s, paid confirmed orders/s, payment TPS, eventos/s, AI requests e tokens/s. **Milhão de compras/s não equivale a milhão de acessos/s**. Um milhão de pedidos/s = 86,4 bilhões/dia e demanda arquitetura e capacidade excepcionais, PSP/infra/ledger/reconciliação e dados mensurados. Não prometer sem prova.

Definir **benchmarks L0–L4** por ADR: L0 laptop/dev; L1 Compose 1 instance; L2 várias instâncias em K8s; L3 falhas e soak; L4 projeção de scale-out/high-capacity com modelo de custo e limites explicitados. Estabelecer alvos realistas e SLOs segundo `docs/05-NFR-E-ESCALA.md`; esses números são **propostos e não resultados**. Congelar cada gate ANTES do teste; relacionar carga, dataset, seed, hardware, versions, número de réplicas, limits, gráficos e logs. Não extrapolar linearmente de 1 máquina para milhões sem modelo de hotspot, DB/sharding, broker partitions, PSP e rede.

## 10.3. SRE / operacional

OpenTelemetry de ponta a ponta (Next/Angular relevantes, FastAPI, gRPC, workers, brokers, PG), correlation/trace propagation; Grafana dashboards por checkout, estoque, outbox, projeções, consumer lag, PSP, cache hit ratio, tráfego de bot/AI; structured logs com PII minimizada, profiles quando justificados, RED/USE, SLI/SLO/error budgets e alertas acionáveis, runbooks de incidente. Não colocar `customer_id` ou `order_id` como label de alta cardinalidade no Prometheus.

Compose é ambiente local/demo. K8s on-prem com manifests/Helm versionados, readiness/liveness/startup, resource requests/limits, HPA/KEDA com métricas reais, PDB, anti-affinity, quotas, namespaces/NetworkPolicies, TLS, Secrets e StorageClasses; para dados stateful planejar HA, operadores, PV, backups/restores, DR, rollout/rollback, mTLS e observabilidade do próprio cluster. Demonstrar `restore drill`; não chamar um pod PostgreSQL único de infraestrutura de produção HA.

---

# 11. SDD PRÓPRIO — ARQUIVOS, ESTADOS E REGRAS DE EXECUÇÃO

## 11.1. Estrutura em cada repositório

O workspace pode ter `sdd/` de coordenação não versionado ou em repo auxiliar; **a spec de cada comportamento mora no repositório responsável**:

```text
sdd/
  prompt.md                         # este contrato e referências, versão controlada
  audit.md                          # inventário real, baseline, hashes e desvios
  source-manifest.md                # docs fornecidos e versões
  glossary.md                       # linguagem ubíqua
  requirements.md                   # REQ-* / INV-* / NFR-* / SEC-* / AI-* estáveis
  roadmap.md                        # milestones, dependências e release slices
  decisions-open.md                 # OPEN, impacto e alternativa segura
  risks.md                          # matriz risco, probabilidade/impacto, mitigação
  traceability.md                   # REQ -> SPEC -> TASK -> código -> teste -> EVD
  progress.md                       # diário de decisões, progresso e bloqueios
  reports/                           # relatório de execução por milestone
  evidence/                          # logs, relatórios, screenshots, schemas, manifests
specs/
  000-business-discovery/
    README.md
    audit.md
    spec.md
    design.md
    tasks.md
    acceptance.feature
    traceability.md
    evidence.md
    risks.md
  001-platform-foundation/           # somente após M0
    README.md
    spec.md
    design.md
    tasks.md
    acceptance.feature
    traceability.md
    evidence.md
    risks.md
  002-catalog-offers-inventory/
    ...
architecture/
  decisions/
    ADR-0001-<slug>.md
  diagrams/
    *.mmd
    *.puml
    C4-*.mmd
  threat-model.md
  runbooks/
```

Manter diretórios por milestone ou bounded context conforme as dependências reais. `spec.md`, `design.md`, `tasks.md`, `acceptance.feature`, `evidence.md` **são obrigatórios** por unidade entregável. `audit.md`, `traceability.md`, `risks.md` por milestone; as visões globais em `sdd/`. Preferir IDs de specs como `SPEC-0001`, requisitos `REQ-CAT-001`, `INV-STOCK-001`, decisões `ADR-0001`, tarefas `TASK-002-001`, testes `TEST-002-001`, evidências `EVD-002-001`. IDs imutáveis após publicação; deprecar ao invés de renumerar.

## 11.2. Contrato de cada documento

- **`spec.md`:** problema, contexto/owner, usuários/atores, requisitos funcionais e não funcionais IDs, invariantes, fluxos felizes/alternativos, dados, eventos, limites de autorização/tenant, critérios mensuráveis, fora de escopo, dependências, riscos e Definition of Done.
- **`design.md`:** C4/UML/ER/protobuffs/API contracts, decisões/trade-offs, data ownership, casos de falha, compensações, backwards compatibility, migração, rollback, testing approach e observabilidade.
- **`tasks.md`:** microtarefas `TASK-ID`, requisito/spec, objetivo, arquivos previstos, dependências, pré-condições, comando de aceite (ou teste), estimativa relativa, risco, rollback, owner, estado e evidência. Proibido tarefa abstrata como "implementar tudo".
- **`acceptance.feature`:** cenários Given/When/Then auditáveis com dados e saídas esperadas, incluindo segurança, concorrência, falha e idempotência quando relevantes.
- **`traceability.md`:** cada requisito vinculado a diagramas/contrato, código, teste, benchmark/métrica, evidência e commit.
- **`evidence.md`:** comandos realmente executados, exit code, ambiente, data UTC, versão, logs relevantes, arquivos de output e hash, resultado `PASS | FAIL | BLOCKED`, divergências e tickets de follow-up. `PASS` só com execução observável.
- **`ADR`:** contexto, alternativas (>= 2 quando viável), decisão, justificação, trade-offs, failure modes, segurança, custo, migração/reversão, fontes e status `PROPOSED | ACCEPTED | SUPERSEDED | REJECTED`.

**Estados únicos de tarefas/milestones:** `TODO`, `READY`, `IN_PROGRESS`, `PASS`, `FAIL`, `BLOCKED`, `DEFERRED`. Não usar percentuais arbitrários ou considerar comentário TODO como funcionalidade entregue.

## 11.3. Gates de execução

Uma tarefa passa a `READY` quando requisitos e dependências estão claros; a `IN_PROGRESS` quando trabalho começou; a `PASS` somente com critérios de aceite verificados. Em falha, `FAIL` com repro e evidência. Em dependência ausente, `BLOCKED` com justificativa, impacto e próximo passo. `DEFERRED` exige decisão expressa e revisão futura. Concluída a implementação, rodar testes relevantes, inspeção de security/observability e regressão; atualizar *todos* os IDs afetados.

**Quando parar:** ausência de credenciais, custo de nuvem/GPU não autorizado, ação destrutiva, decisão de negócio material sem critério resolúvel ou impossibilidade técnica documentada. Fora desses casos, continuar por fatias pequenas sem pedir confirmação trivial. Não inventar aprovação do proprietário; decisões `PROPOSED` permanecem propostas até evidência/aceite do contexto.

---

# 12. ROADMAP PRESCRITIVO E GATES POR MILESTONE

## M0 / SPEC-000 — Recon, auditoria e negócio (SEM CODE BOOTSTRAP)

- Inventariar fontes de verdade e estado Git; conferir 12 diagramas, ownership, invariantes, casos de uso e divergências.
- Produzir glossário, user stories, mapa de contexto, aggregate boundaries, ER/class/use-case/state/sequence revisitados; ADRs sobre ownership e Saga ainda pendentes.
- Gerar backlog com prioridade por valor de negócio, risco e dependência; matriz NFR/budget/capacidade e registros de decisões.
- Validar cenários por Gherkin, riscos críticos, escolha 1P, escopo Admin↔Owners, locale/market/currency e write/read boundary.

**Gate M0:** todas as fontes localizadas/lidas e rastreáveis; ownership único, mapa de eventos, diagramas editáveis consistentes, 5 cenários críticos auditáveis, ADRs abertas explicitadas e `SPEC-001` proposta. Se faltarem arquivos, marcar precisamente `BLOCKED/PARTIAL`, não completar por imaginação. **Não afirmar M0 PASS sem auditoria verificável.**

## M1 / SPEC-001 — Platform Foundation

- Criar os 3 repositórios independentes somente se inexistentes e após M0. Templates CLI `uv`, Copier, Next CLI, Angular CLI; CI, lint, typecheck, pre-commit, Dependabot/Renovate.
- Compose mínimo Mongo replica set/Postgres/Keycloak/Redis + FastAPI health/trace; contratos OpenAPI/Protobuf/AsyncAPI; logs OTel e smoke end-to-end mínimos.
- Registrar matriz de versões compatíveis, ADR da estratégia de shared contracts, IAM realms e processo de desenvolvimento.

**Gate M1:** cada aplicativo inicia via scripts documentados; auth real de cliente/admin com smoke, testcontainers/Compose, primeiro trace cross-process, CI verde e rollback/rebuild determinístico. Nenhum serviço sem bounded context real criado por antecipação.

## M2 / SPEC-002 — Catálogo + Offers + Inventory + Admin publicação (primeiro vertical slice comercial)

- Admin Angular autentica e opera `CreateProduct`, `CreateSKU`, `PublishOffer`, `ReceiveStock`/`AdjustStock` com approvals/policies.
- Control FastAPI modular chama owner microservices via gRPC/contrato autenticado. Owners validam e persistem em MongoDB + outbox; CDC→Kafka; projection workers→PG; Redis cache→Storefront Next.js.
- UI mostra criação, estado de publicação, progress lag, produto localizável e oferta vendável.

**Gate M2:** um produto de demonstração é cadastrado por operador permitido e aparece na loja pelos caminhos reais; operador sem warehouse/market scope falha com 403; evento repetido não duplica view; 2 requisições concorrentes pela última unidade não vendem mais que 1. Evidência com Mongo, Kafka, PG, UI, trace e testes.

## M3 / SPEC-003 — Cart, Quote, Checkout Saga, Order, PSP Fake

- Carrinho cliente, cotação congelada, reserva atomizada, PSP fake com webhooks, pedido, saga de compensation, idempotency/reconciliation e leitura projetada.
- Admin acompanha pedido e estado financeiro sem acesso direto de escrita aos bancos owners.

**Gate M3:** checkout real de ponta a ponta no ambiente local; `oversell=0` no teste parametrizado, `duplicate_paid_order=0`, mesmos inputs/idempotency key retornam resultado coerente, casos de timeout/retry/restart/replay cobertos. Registrar traces e vídeo Playwright.

## M4 / SPEC-004 — Admin Operations hardening

- Workflows four-eyes, permissões de mercado/depósito, ajustes/price changes auditáveis, auditoria imutável lógica, dashboard com provenance/freshness, listagens paginadas e observabilidade operacional.

**Gate M4:** operador não pode aprovar sua própria requisição; revogações e scopes avaliados no owner; toda mudança sensível deixa EVD auditável; UI exibe defasagem CQRS.

## M5 / SPEC-005 — Storefront UX, busca, SEO e i18n

- Busca com facets PG, catálogo multilíngue, experiência responsiva, acessibilidade, SEO/hreflang, mensagens de falha, tracking de pedidos e testes de locale/market/currency.

**Gate M5:** jornadas E2E nos três idiomas e múltiplos mercados; preço/tributo/frete confiáveis, Web Vitals/a11y com medição e limitações explícitas.

## M6 / SPEC-006 — Fulfillment/Returns/Notifications

- Picking/packing, shipment, tracking via adapter fake, cancelamentos/returns/refunds e notificações RabbitMQ com ack/retry/DLQ.

**Gate M6:** retorno e refund coerentes com pagamento/reserva/pedido, efeitos compensados e notificações não duplicadas em casos concorrentes.

## M7 / SPEC-007 — AI Shopping Assistant

- LangGraph tipado, LangChain tools, grounding, produto validado, comparação, carrinho proposto, human approval, custos/latência e observabilidade.

**Gate M7:** agente sugere itens existentes sem preços inventados; injection não amplia escopo; autorização e confirmação invioláveis; fallback manual quando LLM está fora.

## M8 / SPEC-008 — Kubernetes on-prem e operacionalização

- Helm/Skaffold, namespaces, policy, secrets, probes, HPA/KEDA, backups, restore, observability stack resiliente e GitOps opcional por ADR.

**Gate M8:** demo implantada em cluster não-prod com escala de réplicas, rolling deployment/rollback, restore drill e testes de falha com evidência.

## M9 / SPEC-009 — Benchmark, falhas, custo e escala

- Planos L0–L4, carga por operação, testes em SKU hot e checkout, partitioning strategy, cache/coalescing, projections drift, chaos/soak, capacity planning, custo on-prem e roadmap multi-região.

**Gate M9:** relatório com ambiente/fingerprint/carga/percentis/erros/recursos, resultados não atingidos e limitações; nunca declarar milhões de pedidos/s com benchmark simplificado.

## M10 / SPEC-010 — Marketplace 3P e funcionalidades avançadas (DEFERRED por padrão)

- Sellers, tenancy, oferta concorrente, split settlement, antifraude, search dedicada se necessária. Depende de ADR, demanda e confiabilidade do 1P.

**Gate M10:** zero violação de tenant/escopo, settlement correto e baseline regressão; **não antecipar implementação no MVP**.

## M11 / SPEC-011 — Portfolio internacional e documentação final

- Architectural decision log/diagrams em inglês, READMEs dos 3 repos, reproduzir local Compose, vídeo dashboard/checkout/IA, CI reports, SLOs e postmortems reais, trade-off essays (modular monolith vs microservices, CQRS, at-least-once), matriz "projetado vs implementado vs medido".

**Gate M11:** um recrutador ou avaliador consegue clonar, subir ambiente de demonstração, executar E2E, consultar diagramas, comprovar falhas tratadas e verificar honestamente métricas e limitações.

**Dependências:** M0→M1→M2→M3; M4/M5 podem avançar parcialmente em paralelo com contratos estáveis; M6 após M3; M7 após M2/M3; M8 após baseline funcional; M9 após testes/recovery; M10 opcional e não bloqueia portfólio 1P; M11 é transversal e consolidado ao final.

---

# 13. EXEMPLOS DE ACCEPTANCE CRITERIA (OBRIGATÓRIOS COMO ESTILO)

Usar `acceptance.feature` executável ou relacionado a testes concretos; não confundir Gherkin decorativo com automação executada:

```gherkin
Feature: Reservation is authoritative under contention
  Scenario: Two buyers race for the final physical unit
    Given SKU "SKU-001" has on_hand 1, reserved 0 and safety_stock 0
    And customer A and customer B have distinct checkout ids
    When both customers request reservation concurrently
    Then exactly one reservation becomes ACTIVE
    And the other returns an explicit OUT_OF_STOCK result
    And on_hand equals 1 and reserved equals 1
    And no confirmed order exists without valid reservation and payment

Feature: Catalog publication respects domain ownership and CQRS
  Scenario: Admin publishes a product and storefront receives its projection
    Given a catalog operator is allowed to publish in market BR
    And the new SKU has an approved offer and nonzero available inventory
    When the operator publishes via the Angular administrative portal
    Then the Control monolith dispatches the command to the catalog owner
    And the owner persists aggregate and outbox in one local transaction
    And a versioned Kafka event eventually updates the PostgreSQL read model
    And the Next.js storefront displays the correct published product
    And the operation and projection lag can be traced by correlation id

Feature: Financial operations are idempotent
  Scenario: PSP sends the same approval webhook twice
    Given a payment intent exists with a valid idempotency key
    When the PSP sends the same signed approval webhook twice
    Then at most one corresponding capture is recognized
    And the order reaches a single terminal commercial outcome
    And duplicate delivery is observable without double-charging

Feature: Administrative segregation of duties
  Scenario: Requester tries to approve their own high-impact stock adjustment
    Given an operator requested stock adjustment on warehouse W1
    When the same operator attempts approval
    Then the action is denied and audited
    And the inventory aggregate is unchanged

Feature: Shopping AI cannot charge without customer confirmation
  Scenario: Untrusted product description attempts to bypass human approval
    Given a product description includes prompt-injection instructions
    When the customer asks the assistant to compare that product
    Then the assistant may cite authorized product information
    But cannot execute payment, grant permissions or mutate stock
    And any cart mutation requires explicit customer confirmation
```

Associar cada `Scenario` a `TEST-ID` e evidência real. Se o PSP fake não simula um webhook assinado, adaptar contrato ou registrar limitação e gate pendente; jamais afirmar segurança baseada em cenário hipotético.

---

# 14. MODELO DE MATRIZ DE RASTREABILIDADE E QUALIDADE

Por spec, produzir linhas equivalentes a:

| Requirement | Design/Contract | Task | Test | Metric/Gate | Evidence | Status |
|---|---|---|---|---|---|---|
| INV-STOCK-001 | Inventory aggregate + CAS | TASK-002-011 | TEST-002-031 | oversell=0 under defined concurrent test | EVD-002-041 | TODO |
| INV-CQRS-001 | outbox + projection worker | TASK-002-018 | TEST-002-046 | duplicate event causes no duplicate projection | EVD-002-047 | TODO |
| INV-ADMIN-001 | Approval policy + IAM | TASK-004-003 | TEST-004-010 | requester self-approval denied | EVD-004-010 | TODO |

A tabela acima é **exemplo de formato, não resultados observados**. Criar IDs verdadeiros ao iniciar cada milestone. Evidência inclui: comando, exit code, versão e hash do commit, ambiente, resultado e artefato verificável. Arquivos binários grandes/screenshots em localização configurável e manifest com checksum; nunca guardar segredos em artefatos.

---

# 15. PROCEDIMENTO DO AGENTE EM CADA EXECUÇÃO

1. **RECON:** ver `git status`, branch, diffs, specs e últimas evidências; ler a TASK atual; identificar mudanças de outros autores. Nunca sobrescrever alteração do usuário.
2. **SPEC:** atualizar requisito e aceite atômicos da tarefa; quando alterar contrato, registrar `ADR` ou atualizá-la com razão; manter escopo limitado.
3. **PLAN/TASK:** decompor em tarefas com arquivos, riscos e testes previstos; verificar versão/ferramenta com `--help`/docs oficiais antes de utilizar comandos não conhecidos.
4. **TEST-FIRST** nas regras de maior risco: formular/redigir cenário falhando, implementar mínima regra correta, executar integração real, validar observabilidade.
5. **IMPLEMENT:** código sob owner correto, sem quebra dos demais produtos; preferir adapters e contratos; evitar classes vazias e stubs permanentes.
6. **VERIFY:** unit+integration+contract+E2E e scanners apropriados; validar regressão N/N-1, database schema, logs, IAM, commit/status, endpoints e docs.
7. **EVIDENCE:** anexar saída real, exit codes, logs/summaries, screenshots E2E, manifests/hash, métricas e riscos remanescentes. Resultado negativo explícito.
8. **CONVERGE:** fechar itens verificáveis, atualizar traceability, `progress.md`, ADRs, runbook e CHANGELOG; recomendar próxima TASK de maior valor/risco.

**Controle de mudanças:** commits pequenos, nomes descritivos, sem `git push` ou PR sem autorização contextual; nunca apagar arquivos de evidência nem reescrever histórico de execução. Antes de migration destrutiva: backup, dry-run, validação, compatibilidade e rollback. Não exigir acesso real a produção, PSP ou credenciais desnecessárias para o MVP.

---

# 16. FORMATO DE RELATÓRIO FINAL EM TODA EXECUÇÃO

Responder ao proprietário em português brasileiro; incluir fatos verificáveis, sem marketing nem declarações de sucesso fictícias:

```text
ATLAS COMMERCE — EXECUTION REPORT
DATE_UTC: <timestamp>
REPO(S) / BRANCH / COMMIT(S): <reais, ou NO_REPO>
MILESTONE: Mx / SPEC-xxx — <objetivo>
STATUS: TODO | READY | IN_PROGRESS | PASS | FAIL | BLOCKED | DEFERRED

SOURCES AUDITED:
  <caminhos, hashes, faltas e conflitos>
BUSINESS / ADR DECISIONS:
  <confirmadas, propostas, abertas>
IMPLEMENTED:
  <arquivos, fluxos e limites realmente implementados>
NOT IMPLEMENTED / DEFERRED:
  <pendências explicitadas>
TESTS EXECUTED:
  <comando exato> -> PASS/FAIL/BLOCKED (exit code, contagem, ambiente)
EVIDENCE:
  EVD-... -> <local e hash/commit>
SECURITY / RELIABILITY / CQRS:
  <o que foi verificado; o que permanece risco>
PERFORMANCE:
  <métricas efetivamente medidas, ou NOT_MEASURED>
REGRESSIONS / RISKS:
  <regressões e mitigação>
NEXT EXECUTABLE TASK:
  <TASK-ID, aceite e dependências>
```

**Não** produzir múltiplos relatórios contraditórios ou marcar `PASS` por teste que não rodou. Se usar mock, indicar o que é mock e quais provas ainda faltam. Se ferramentas de browser/container não estiverem disponíveis, registrar `BLOCKED`, não inventar screenshots. Documentação é atualizada em todos os ciclos.

---

# 17. INSTRUÇÃO DE PARTIDA — O QUE FAZER AGORA

Você está recebendo este prompt **junto dos documentos de Atlas Commerce no workspace**. A tarefa imediata é **iniciar o projeto corretamente em SDD**, e não fabricar uma plataforma inteira numa resposta:

**A.** Identifique o caminho do workspace e dos arquivos; leia o blueprint, o README, as 8 docs e os 12 diagramas; inventarie árvore e Git.  
**B.** Produza `sdd/audit.md`, `sdd/source-manifest.md`, `sdd/requirements.md`, `sdd/glossary.md`, `sdd/roadmap.md`, `sdd/traceability.md`, `sdd/risks.md`, `sdd/open-questions.md`/`decisions-open.md` e `specs/000-business-discovery/{README,audit,spec,design,tasks,acceptance.feature,traceability,evidence,risks}` (criando diretórios sem apagar o material de origem).  
**C.** Confirme/critique separação dos domínios, ownership e consistência dos modelos ER/UML/diagramas. Identifique todas as decisões técnicas abertas e proponha ADRs `PROPOSED` priorizadas; nenhum ADR de alto risco é declarado aceito sem base.  
**D.** Construa uma primeira fatia vertical concreta (especificação, não código nesta execução): **Admin registra Produto + SKU + Oferta + estoque → comando via owner microservice → MongoDB outbox → Kafka → projeção PostgreSQL → Storefront Next.js apresenta produto em pt-BR**. Planeje autorização Keycloak, logs OTel, RabbitMQ como serviço de tasks justificado posteriormente, rastreabilidade e testes reais. Prepare `SPEC-001` foundation e `SPEC-002` slice com contratos, dependências e gates, sem implementar ainda.  
**E.** Produza um relatório de M0 detalhando o que estava nos arquivos e o que você efetivamente verificou. **Pare ao final de M0 na primeira execução**, sem scaffolding invasivo; em execuções seguintes trabalhe na primeira TASK READY da milestone seguinte.

Se o workspace já tiver código, substitua scaffolding novo por **integração e preservação do projeto existente**. Sua qualidade será medida pela coerência entre negócio, specs, contratos, implementação real, testes e evidências — nunca pelo número de microsserviços, linhas de código ou tecnologias anunciadas.

**COMECE PELO INVENTÁRIO DOS ARQUIVOS E PELA AUDITORIA DO DOMÍNIO.**
