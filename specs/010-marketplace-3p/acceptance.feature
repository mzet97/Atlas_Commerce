Feature: Marketplace 3P
  Scenario: seller operator publishes in own tenant
    Given seller_operator paul com grant (seller=seller-acme, market=BR)
    When publica oferta seller-acme
    Then 201 ACTIVE
  Scenario: cross-tenant is forbidden
    Given paul com grant apenas seller-acme
    When publica oferta seller-outro
    Then 403 e linha auditada denied
  Scenario: buybox
    Given duas ofertas ativas no mesmo SKU (990 e 790)
    When o storefront lê o SKU
    Then exibe 7,90
  Scenario: settlement
    Given pedido CONFIRMED 2 linhas de sellers distintos
    When finance_analyst computa settlement
    Then bruto/comissão 10%/líquido por seller corretos
  Scenario: velocity fraud
    Given 5 intents AUTHORIZED do cliente em 60s
    When a 6ª intent chega
    Then DECLINED FRAUD_VELOCITY sem chamada ao PSP
