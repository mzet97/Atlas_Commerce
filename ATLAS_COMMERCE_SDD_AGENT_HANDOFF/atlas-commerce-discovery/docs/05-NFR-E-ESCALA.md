# 05 — NFRs, SLOs, capacidade, falhas e prova de escala

## 1. Distinção entre acesso e compra
**RPS de visualização** (CDN/cache/search), **checkout attempts/s** (cotação/reserva/autorização), **confirmed orders/s** (sucesso comercial durável), **payment TPS** (dependência externa), **events/s**, **AI tokens/s** e **storage IOPS** são dimensões diferentes.

Alvo de 1 milhão de pedidos/s, se sustentado, implica **86,4 bilhões de pedidos/dia**. Apenas um evento de 1 KiB por pedido implicaria ~88,5 TB/dia decimais antes de réplicas, múltiplos eventos, projeções, índices, pagamentos e logs. 1 milhão de pageviews/s pode ser majoritariamente atendido em edge, com pouquíssimas chamadas ao backend. Não equiparar métricas.

## 2. SLOs candidatos a pactuar — NÃO medidos
| SLI | Meta inicial proposta | Janela | Limite |
|---|---|---|---|
| Disponibilidade consulta de catálogo | 99.95% | 30 dias | rotas principais, regiões ativas |
| Disponibilidade aceite de checkout | 99.9% | 30 dias | exclui interrupção externa claramente discriminada |
| Latência p95 catálogo cache-hit | < 200 ms | 30 dias | API interna, sem navegação global |
| Latência p95 busca uncached | < 500 ms | 30 dias | dataset e hardware especificados |
| Latência p95 submissão checkout | < 1.5 s para aceite PENDING | 30 dias | NÃO espera confirmação do PSP |
| Projection lag p99 | < 5 s em carga nominal | 30 dias | lag por contexto; pico sob falha analisado |
| Pedidos duplicados devido a retries | 0 em suíte de fault injection | cada release | invariantes de idempotência |
| Overselling não autorizado | 0 em testes concorrentes | cada release | sob política sem backorder |
| Tratamento de pagamentos | 100% reconciliáveis | diário | diferenças sinalizadas, jamais omitidas |
| RTO serviço essencial | 30 min (proposta) | desastre simulado | testar restore realmente |
| RPO agregado confirmado | 5 min (proposta) | desastre simulado | exigência inferior demanda design mais caro |

Metas SLO exigem orçamento e hardware; só se tornam compromisso após avaliação.

## 3. Estágios de benchmark sugeridos
| Estágio | Catálogo RPS | Checkout attempts/s | Pedidos confirmados/s | Evidência |
|---|---:|---:|---:|---|
| L0 local funcional | 50 | 1 | depende PSP fake | correto / observável |
| L1 laboratório | 1.000 | 20 | mensurar | p50/p95/p99 + resources |
| L2 distribuído | 10.000 | 200 | mensurar | HPA, Kafka lag, backpressure |
| L3 estresse | 100.000 | 2.000 | mensurar | teste multi-nó, limite e custo |
| L4 hipótese de escala | 1.000.000 | 10.000+ | jamais prometer antes de medir | multi-região, storage/sharding e PSP throughput |

Esses números são **cargas artificiais a testar**, não capacidade comprovada, e não equivalem a 1 milhão de compras/s. Tráfego internacional precisa de CDN, roteamento geográfico e estratégia multi-região; on-premises sem rede distribuída pode não atender latência global.

## 4. Engenharia de desempenho
- **Carga:** k6 / Locust para tráfego HTTP+ecommerce journey; gRPC carga com ferramenta adequada; Kafka perf tooling; ferramentas de análise no frontend Lighthouse e Web Vitals.
- **Workload realista:** navegação ~95%, busca, carrinho, checkout, AI; distribuições explícitas por mercado, hot products, picos 10x, usuários novos/recorrentes, catálogos de 10^6 SKUs e grande skew.
- **Perf methodology:** warmup, steady state, spike, soak, chaos; carga aberta (arrival rate), não só usuários virtuais; percentis, erros, saturation, throughput, latência, CPU, memória, I/O, rede, replication lag e queue depth.
- **Isolamento:** experimentos por configuração de cluster, tiers de caching, réplica, partições e custo; `results/<run_id>/` com commit SHA, lockfiles, hardware, parâmetros, dashboards, traces, gráficos e raw data.
- **Custo:** infra em on-prem não é grátis; registrar gasto energético e capacidade física, IOPS e rede.
- **Queda controlada:** se PSP fora, estado pendente/rejeição sem cobrança falsa; se Redis fora, leitura fallback limitada; se Kafka fora, outbox acumula; se DB não autoritativo fora, operações críticas seguem política de disponibilidade.

## 5. Escala sob contenção
- Checkout e Inventory exigem particionamento cuidadoso por SKU/warehouse, concorrência otimista e hot-key mitigation sem quebrar invariantes; simplesmente adicionar pods não elimina serialização de um SKU único.
- Consumidores Kafka paralelizam por partições e grupos; a ordem é por partition key; throughput cresce até limites de partições, disco, rede e consumidores.
- RabbitMQ quorum queues replicadas para workflows/commands com DLQ, retry controlado, publisher confirms, manual ack, prefetch e dedup da aplicação.
- gRPC com deadlines, retry apenas seguro, bulkhead, circuit-breaker, propagação de identity/trace e quotas.
- Kubernetes HPA/KEDA conforme métricas, PDB, probes, requests/limits, topology spread, readiness, graceful shutdown. Cluster autoscaling só onde houver provisionador de nós.
- Capturar métricas cardinalidade controlada: nunca incluir customer_id/order_id como label de Prometheus; inserir nos traces/logs estruturados com redaction.
