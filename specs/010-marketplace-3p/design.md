# Design

- Tenancy: tabela `sellers` no DB control (migração 006); gate ABAC por
  (seller, id) no command_channel (ScopeGrant existente).
- Oferta: unicidade já por (sku, seller, market, channel) — 3P reusa o
  aggregate Offer sem migração; buybox na LATERAL da leitura (ORDER BY
  price ASC).
- Settlement: Control lê projeções (orders_view + order_lines +
  available_offer_view) e escreve relatório em `settlements` (control DB)
  — ADR-0006 preservada; payouts fora de banda.
- Antifraude: contador owner-side (`count_authorized_since`), janela 60s,
  limite 5; intent DECLINED local, PSP intocado.
