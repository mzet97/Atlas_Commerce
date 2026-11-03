# 02 — DDD: bounded contexts, agregados, ownership e invariantes

## 1. Bounded contexts
| Contexto | Agregado/entidades principais | Comandos chave | Eventos publicados | Owner |
|---|---|---|---|---|
| Identity & Access | Identity reference, MemberGrant, Policy | Conceder/revogar acesso | AccessChanged | Keycloak + Control IAM (policy metadata) |
| Product Information (PIM) | Product, Variant, Category, Media, Attribute | CreateProduct, UpdateProduct, PublishProduct | ProductPublished, ProductUpdated | Catalog Service |
| Merchandising | Offer, PriceList, Promotion, Coupon | PublishOffer, UpdatePrice, ApplyPromotion | OfferPublished, PriceChanged | Pricing/Offer Service |
| Inventory | StockPosition, StockMovement, Reservation, Warehouse | ReceiveStock, ReserveStock, ConfirmReservation, ReleaseReservation | StockAdjusted, StockReserved, ReservationExpired | Inventory Service |
| Discovery | SearchDocument, Facets | SearchProducts, SuggestProducts | SearchObserved (analytics) | Search/Discovery Service (read owner) |
| Basket | Cart, CartLine | AddItem, RemoveItem, ClearCart | CartUpdated, CartAbandoned | Cart Service |
| Checkout | CheckoutSession, PriceQuote | QuoteOrder, SubmitCheckout | CheckoutSubmitted, CheckoutExpired | Checkout Service |
| Order Management | Order, OrderItem, OrderStatusHistory | PlaceOrder, ConfirmOrder, CancelOrder | OrderPlaced, OrderConfirmed, OrderCancelled | Order Service |
| Payments | PaymentIntent, PaymentAttempt, Capture, Refund, SettlementRef | Authorize, Capture, Refund | PaymentAuthorized, PaymentFailed, PaymentCaptured, Refunded | Payment Service |
| Fulfillment | FulfillmentOrder, Package, Shipment, TrackingEvent | StartPicking, Ship, ConfirmDelivery | ShipmentCreated, Dispatched, Delivered | Fulfillment Service |
| Returns | ReturnRequest, ReturnItem, RMA | RequestReturn, InspectReturn, ApproveRefund | ReturnApproved, RefundRequested | Returns Service |
| Reviews | Review, ModerationDecision | PostReview, ModerateReview | ReviewApproved | Reviews Service |
| Customer Profile | Customer, Address, Preferences, Consent | UpdateProfile, ChangeConsent | CustomerProfileChanged | Customer Service |
| Communications | Notification, Template, DeliveryAttempt | SendNotification | NotificationSent/Failed | Notification Service |
| Shopping Assistant | Conversation, ToolInvocation, Recommendation, Consent | Ask, Compare, ProposeCart | AssistantRecommendationViewed | AI Service |
| Admin Control Plane | Approval, AdminCase, AuditRecord, JobRequest | ApproveChange, RequestInventoryAdjustment, AssignCase | AdminApprovalGranted, AdminActionAudited | Control Modular Monolith |
| Analytics | SalesProjection, FunnelMetric, DemandProjection | RebuildProjection, QueryMetric | — | Analytics consumers/read models |

**Ownership é por contexto, não por aplicação web.** O Control mantém apenas suas entidades administrativas; para cadastrar ou ajustar itens/estoque chama os serviços donos do catálogo, preços e inventário. Isso evita dual-write e divergências.

## 2. Agregados e limites transacionais
1. `Product`: identidade, variantes e lifecycle do item; referências a categorias; nunca contém estoque ou preço corrente como verdade autoritativa.
2. `Offer`: seller_id, sku_id, market_id, price_rule_version, janela de validade e status; garante no máximo uma oferta ativa para chave de canal/escopo definida.
3. `StockPosition`: chave warehouse_id+sku_id; saldo on_hand, reserved e version; operação condicional atômica; ledger de movimentos.
4. `Reservation`: quantidade, tempo de expiração, idempotency_key, order_id/checkout_id, status; uma reserva confirmada não expira automaticamente.
5. `Order`: snapshot imutável de itens, ofertas, moeda, impostos, descontos, endereço de entrega e totais; mudanças após compra geram compensações, não reescrita histórica.
6. `PaymentIntent`: provider, idempotency_key, tentativas, capture/refund, status; deduplicar webhooks; não armazenar dados brutos de cartão.
7. `Approval`: request, proposed_changes, requestor, approver, policy, before/after hashes, proof and reason.

## 3. Invariantes não negociáveis
**INV-001 Inventory:** `available = on_hand - reserved - safety_stock >= 0` para estoque físico com venda bloqueada sem saldo. Pré-venda é política separada e explícita.

**INV-002 Reservation:** reprocessar `ReserveStock(checkout_id, sku_id, quantity)` com mesma chave retorna a mesma reserva, nunca duplica redução.

**INV-003 Monetary:** valores monetários em inteiros de unidade mínima (por moeda) ou `Decimal` com escala determinada; nunca float. Soma dos componentes e regras de arredondamento deve reproduzir o total.

**INV-004 Quote:** confirmação só com cotação válida, assinatura/versão conhecida, oferta ativa, estoque autorizado e moeda consistente; re-cotação exigida quando vencida.

**INV-005 Order:** `OrderConfirmed` requer pagamento autorizado/capturado conforme política, e reserva confirmada; eventos duplicados não avançam duas vezes a máquina de estados.

**INV-006 Payments:** nunca executar cobrança por inferência de sucesso HTTP; o estado final decorre de resposta autenticada do PSP e reconciliação. Estorno e captura geram registros auditáveis, não edits in place.

**INV-007 Authorization:** toda mutação administrativa exige identidade, permissões por ação+escopo, justificativa quando aplicável e registro de auditoria; UI não é perímetro de segurança.

**INV-008 Localization:** preço e moeda são autoridade do Offer/Quote; a UI não converte preço autoritativo com cotação aproximada do cliente.

**INV-009 Agent:** a IA não pode confirmar pedidos, mover dinheiro ou alterar estoque por conta própria. O usuário confirma as transações por um fluxo confiável fora do LLM.

**INV-010 Event consistency:** `event_id` único; `aggregate_id`, `aggregate_version`, `occurred_at`, `schema_version`, `correlation_id`, `causation_id`, `tenant_id?`, `traceparent` presentes; projeções idempotentes e capazes de reconstrução.

**INV-011 Privacy:** PII mínima em logs/eventos, criptografia e mecanismos de exclusão/anonimização considerando requisitos legais e retenção contábil.

**INV-012 Administrative integrity:** um ajuste de estoque e uma mudança de preço acima de limite seguem aprovação de operador distinto (four-eyes), com justificativa e trilha de auditoria.

## 4. Exemplo de conflito a solucionar com política
Duas compras concorrentes tentam reservar a última unidade. Ambas podem observar `available=1` em PostgreSQL atrasado. O serviço de Inventory aplica reserva condicional no MongoDB com `version` e disponibilidade como condição; apenas uma vence. Checkout rejeita ou re-cota a outra. Redis, PostgreSQL e Kafka não decidem disponibilidade final.

## 5. Domínio comercial: first-party e extensibilidade
Modelagem separa `Product → SKU → Offer → Seller → Market` desde o princípio; `Seller` inicial é a própria plataforma. Assim, incluir 3P depois é uma evolução de domínio, não uma migração disruptiva do vínculo entre produto e preço.
