# Spec

REQ-MKT-001 Sellers registrados via Control (iam_admin) como tenants.
REQ-MKT-002 seller_operator publica ofertas SOMENTE no próprio seller
(escopo seller + market; cross-tenant 403 auditado).
REQ-MKT-003 Oferta concorrente: unicidade (sku, seller, market, channel);
buybox = menor preço ativo por SKU na leitura.
REQ-MKT-004 Split settlement: relatório auditável por pedido
(bruto/comissão 10%/líquido por seller) no DB do Control.
REQ-MKT-005 Antifraude velocity: >5 intents AUTHORIZED/cliente/60s →
DECLINED FRAUD_VELOCITY sem tocar o PSP.
