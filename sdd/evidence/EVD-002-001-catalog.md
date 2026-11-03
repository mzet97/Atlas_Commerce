# EVD-002-001 — M2 increment-1: Catalog owner slice (2026-10-27)

Status: PASS (slice vertical do owner ao read model; gate M2 completo —
Admin UI e Storefront display — segue OPEN).

## Serviço `atlas-storefront/services/catalog` (14 arquivos)
Clean/Hexagonal: `domain.py` (Product, eventos ProductCreated/Published,
erros tipados com campos) → `application.py` (commands/handlers, Protocol)
→ `mongo_repo.py` (agregado + outbox na mesma transação, CAS por versão,
idempotência por chave única) → `api.py` (Pydantic v2 na borda, handlers
de erro por tipo) → `relay.py` (outbox→Kafka) + `projector.py`
(Kafka→PG idempotente via `processed_events`) → `main.py`.
Regras aplicadas (skills): NewTypes, sem `Any`/`dict` cru em assinaturas,
exceções tipadas, `match` desnecessário (dispatch por handlers), ruff limpo,
todos os arquivos ≤156 LOC puras.

## Testes: 14 passed (ruff + pytest, 0.46s)
- `test_domain.py` (5): create/publish/invariants, erro carrega campos.
- `test_api.py` (6, integração real Mongo): 201, idempotência, 422/404/409.
- `test_slice.py` (2): 20 escritores concorrentes na mesma chave → 1 produto
  (`count == 1`); evento entregue 2x → 1 linha PG + 1 inbox.
- Bugs reais achados e corrigidos pelos testes: client Motor no import
  prendia o loop (→ lifespan + `app.state`); DuplicateKey lida dentro da
  transação abortada (→ leitura fora da txn); WriteConflict 112 no commit
  (→ retry no label transitório); exceções frozen+slots quebram traceback.
- Desvios declarados: `asyncio` em vez de `anyio` (Motor/aiokafka são nativos
  asyncio; prompt §5.2 manda asyncio não-bloqueante); integração mira
  `localhost` mapeado em vez de testcontainers (daemon docker só no host).

## Prova E2E na stack viva (11 containers Up)
- `POST :8101/products` → 201 DRAFT v1; `POST .../publish` → 200 PUBLISHED v2.
- `outbox unpublished = 0`; PG `catalog_product_search` = PUBLISHED v2;
  tópicos `atlas.catalog.Product{Created,Published}.v1` existem;
  grupo `catalog-projector` LAG 0 em ambos.
- Migração `001_catalog_projection.sql` aplicada no `atlas/pg`.

## Falta para o gate M2
Admin Angular + Control publicando via comando; Storefront exibindo com
estado PUBLISHING; 403 fora de escopo; CI do serviço em runner.
