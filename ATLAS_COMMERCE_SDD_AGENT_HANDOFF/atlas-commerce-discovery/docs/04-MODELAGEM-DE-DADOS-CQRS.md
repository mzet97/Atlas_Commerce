# 04 — Modelo conceitual, diagramas ER, MongoDB Write Model e PostgreSQL Read Model

## 1. O que ER significa aqui
Diagramas entidade-relacionamento definem **conceitos e relações de negócio**, sem implicar que todos os dados residam no PostgreSQL. O comando será persistido no MongoDB pelos microserviços donos do agregado. PostgreSQL conterá projeções denormalizadas/read-optimized, deliberadamente diferentes das coleções Mongo. Os arquivos `03-er-catalog.mmd`, `04-er-order-finance.mmd`, `05-er-admin.mmd` mostram as visões conceituais/read-model, e `06-classes-order.mmd` e `07-classes-inventory.mmd` mostram classes de domínio.

## 2. Entidades globais conceituais (IDs imutáveis)
**Merchant/Seller** `seller_id`, nome, status; **Market** `market_id`, país e regras; **Category** `category_id`, parent_id, taxonomy; **Product** `product_id`, title localized, descriptions, attributes, lifecycle; **SKU** `sku_id`, product_id, dimensions, GTIN optional; **Offer** `offer_id`, sku_id, seller_id, market_id, channel, currency, price, validity, status.

**Warehouse** `warehouse_id`, region, operations; **StockPosition** `warehouse_id + sku_id`, on_hand, reserved, safety_stock, version; **StockMovement** `movement_id`, stock_key, movement_type, quantity, reason, actor; **Reservation** `reservation_id`, checkout_id, sku_id, warehouse_id, qty, status, expires_at.

**Customer** `customer_id`, identity_sub, preferences; **Address** `address_id`, customer_id, normalized geography; **Cart** `cart_id`, customer_id/guest_id; **CartLine** `cart_line_id`, sku_id, offer_id, quantity; **Quote** `quote_id`, version, currency, totals, expires_at; **Order** `order_id`, customer_id, order_number, totals, shipping snapshot; **OrderLine** `order_line_id`, sku/offer snapshot, price, qty, tax, discount; **OrderTransition** `transition_id`, from, to, reason, occurred_at.

**PaymentIntent** `payment_intent_id`, order_id, amount_minor, currency, status; **PaymentAttempt** `attempt_id`, PSP reference, status; **Capture** `capture_id`, attempt_id, amount; **Refund** `refund_id`, capture_id, amount, reason; **Shipment** `shipment_id`, order_id, carrier, tracking; **ShipmentLine** `shipment_line_id`, order_line_id, quantity; **Return** `return_id`, order_id, reason, disposition.

**AdminAction** `action_id`, actor_sub, action, resource_type, resource_id, before_hash, after_hash, justification, correlation_id; **Approval** `approval_id`, requested_by, approved_by, request, result, timestamps; **ScopeGrant** `grant_id`, subject_sub, role, resource_scope.

## 3. MongoDB write model: document boundaries
| Collection por service DB | Exemplo de documento e índices | Observações |
|---|---|---|
| `catalog.products` | `{_id, version, status, localized, variants[], media[], attrs}`; índice unique `slug+market` só onde aplicável | variants embedded se limites controlados; SKU imutável |
| `offers.offers` | `{_id, sku_id, seller_id, market_id, channel, currency, price_minor, valid_from, valid_to, version}` | índices por SKU/market/status e validação de intervalos no domínio |
| `inventory.positions` | `{_id:warehouse_id:sku_id, on_hand, reserved, safety_stock, version}` | compare-and-set/conditional update com disponibilidade suficiente |
| `inventory.movements` | `{_id, position_id, delta, reason, actor, time}` | append-only lógico; reconciliação automatizada |
| `inventory.reservations` | `{_id, checkout_id, lines[], status, expires_at, version}` | TTL pode acelerar limpeza; nunca substitui transição de domínio explícita |
| `orders.orders` | `{_id, customer_id, state, snapshot:{lines, totals, address}, reservation_refs[], payment_ref, version}` | snapshot evita inconsistência histórica |
| `payments.intents` | `{_id, order_id, status, provider, amount_minor, currency, attempts[], version}` | não inclui PAN/CVV; idempotency key única |
| `checkout.sessions` | `{_id, quote, customer_id, idempotency_key, state, expires_at}` | expiração explícita |
| `control.approvals` | `{_id, request, actor, checker, decision, state, version}` | pertence somente ao monólito Control |

**Outbox em MongoDB:** dentro da transação local do agregado, salvar alteração de domínio e documento outbox imutável na mesma sessão transacional. Usar replica set mesmo no ambiente local para exercitar transações/change streams. Debezium MongoDB Connector/Kafka Connect captura outbox (configuração explícita de rota/SMT ou consumidor bridge) e emite para Kafka. Consumidores de projetos read usam **inbox/dedup** com event_id e `aggregate_version` para idempotência e reordenação controlada. CDC de toda a coleção **não** é automaticamente um contrato de eventos de negócio: o envelope outbox é o contrato.

## 4. PostgreSQL query model proposto
Apenas as tabelas necessárias às consultas, derivadas de eventos; PostgreSQL não recebe `INSERT` diretamente do frontend nem é owner das mutações de compra.

| Projeção | Campos e índices fundamentais | Consulta |
|---|---|---|
| `catalog_product_search` | product_id PK, normalized_text, localized fields, category_id, status, projection_version; GIN search/facets | listagem e busca |
| `available_offer_view` | offer_id PK, sku_id, seller_id, market_id, currency, price_minor, availability_hint, updated_at | PDP, oferta; `availability_hint` não confirma saldo |
| `customer_order_summary` | order_id PK, customer_id, order_number, state, total_minor, currency, placed_at, projection_version | meus pedidos |
| `order_detail_view` | order_id PK, lines JSONB, payment_state, shipment_info JSONB, timeline | detalhe do pedido |
| `inventory_admin_view` | warehouse_id+sku_id PK, on_hand, reserved, available, source_version, projected_at | grade administrativa; comandos revalidam na autoridade |
| `payments_reconciliation_view` | payment_intent_id, order_id, provider_ref, captures/refunds, discrepancy_code | financeiro |
| `admin_audit_search` | action_id, actor_sub, resource, timestamp, result, metadata redacted | auditoria |
| `funnel_metrics_hourly` | hour, market_id, impressions, carts, checkouts, confirmed_orders | business analytics |
| `projection_offsets` | projection_name+partition/aggregate key, offset/version, processed_at | controle de reconstrução |
| `processed_events` | consumer_id+event_id PK, aggregate_id, version, applied_at | deduplicação dentro da transação da projeção |

**Observação de integridade:** relações entre projections são consistentes eventualmente. FK pode ser útil dentro de uma projeção, mas não deve impedir o reprocessamento fora de ordem sem staging/upsert. Projetar view específica para query > copiar modelo de escrita para PG.

## 5. Pipeline CQRS e garantias
```text
HTTP/gRPC Command → validation + policy → MongoDB aggregate + outbox (same local transaction)
                          ↓                                 ↓
                response accepted                 CDC outbox → Kafka topic (per domain)
                                                        ↓
                                      projection workers (idempotent)
                                                        ↓
                                          PostgreSQL read models
                                                        ↓
                                             Redis cache → Query API
```
- Produto atualizado pode levar tempo para refletir na pesquisa; expor versão e métricas de projection lag.
- Read-your-writes administrativo: resposta do comando inclui versão; UI pode oferecer estado `PUBLISHING` até projeção atingir `source_version`; nunca assume leitura imediatamente consistente.
- Pagamento/estoque: a confirmação é por serviço autoritativo e resultado da saga, não consulta ao read model.
- Falha de event publisher: outbox é reprocessada; monitorar backlog; eventos particionados por agregado para preservar ordem **por chave**, não ordem global.
- Falha de consumer: retry com backoff, DLQ/quarantine e replay/audit; idempotência de projeções; reconstrução reprocessando log/snapshot.
- Redis: cache-aside com TTL, jitter, keys versionadas e invalidação por evento; cache não pode validar estoque/pagamento.

## 6. Consistência e interações multi-serviço
Não existe transação ACID única abrangendo RabbitMQ, Kafka, MongoDB, PostgreSQL e PSP. Use saga com estados persistidos, comandos idempotentes e compensações; veja `10-sequence-checkout.mmd`.

## 7. Catálogo de índices mínimos / privacidade
- IDs: UUIDv7/ULID com política temporal e desambiguação por domínio; chaves naturais (GTIN, e-mail) não substituem IDs imutáveis.
- MongoDB: índices únicos para chaves de idempotência, composto de estoque, TTL em coleções temporárias com limpeza orientada a domínio, shard keys escolhidas com distribuição mensurável; evitar hotspot de SKU popular.
- PostgreSQL: índice por `(customer_id, placed_at DESC)` pedidos; `(market_id, category_id, status)` catálogo; `(warehouse_id, sku_id)` inventário; FULLTEXT/GIN para MVP.
- PII: tratar endereços conforme finalidade; cópia em snapshot de pedido depende de política de retenção; criptografia em trânsito/repouso e controle de acesso.
