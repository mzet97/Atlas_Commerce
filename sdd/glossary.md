# sdd/glossary.md — linguagem ubíqua (M0, fonte: docs 01–02)

| Termo | Definição |
|---|---|
| Product | Item conceitual do catálogo, independente do vendedor |
| Variant / SKU | Variação comercial; SKU diferencia unidades estocáveis |
| Offer | Proposta de venda: SKU + seller + market + canal + vigência + preço |
| Price Quote | Cotação congelada com TTL, breakdown e assinatura/versão |
| Stock Ledger | Movimento auditável de inventário por armazém/SKU |
| Reservation | Alocação temporária vinculada a checkout, com expiração e idempotency key |
| Order | Contrato comercial com snapshot imutável de itens/valores |
| Payment Intent | Intenção + tentativas de autorização/captura; sem PAN/CVV |
| Shipment | Agrupamento físico de itens; um pedido pode ter vários |
| Return / Refund | Fluxo logístico reverso ≠ devolução financeira |
| Read Model | Projeção PostgreSQL por consulta; nunca autoridade do comando |
| Market / Locale / Currency | Contexto regulatório / idioma-formatação / denominação — independentes |
| Approval | Solicitação + decisão four-eyes com hashes before/after e justificativa |
| Outbox / Inbox | Entrega recuperável / consumo deduplicado de eventos |
