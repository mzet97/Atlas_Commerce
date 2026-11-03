# sdd/risks.md — matriz risco × impacto × mitigação (M0)

| # | Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|---|
| R-01 | Divergência IDs `INV-*` vs `INV-<DOM>-*` | Alta | Média | OPEN-01: tabela de equivalência em M1; docs vencem até lá |
| R-02 | Ordem saga reserva/pedido/pagamento indefinida | Média | Alta | OPEN-02: ADR-007 PROPOSED; default blueprint até decisão |
| R-03 | Dual write (publicar evento fora da transação) | Média | Alta | Outbox mesma sessão Mongo + replica set local obrigatório |
| R-04 | Leitura defasada decidir saldo/pagamento | Média | Alta | INV-CQRS-001: autoridade é Mongo/PSP; `availability_hint` nunca confirma |
| R-05 | Oversell em SKU quente | Média | Alta | CAS condicional + teste 2 escritores concorrentes (gate M2) |
| R-06 | Webhook PSP forjado/duplicado | Média | Alta | Assinatura + idempotency key + reconciliação; sem PAN/CVV |
| R-07 | Prompt injection via descrição/review | Média | Alta | Conteúdo de catálogo = untrusted; allowlist + bypass = 0 |
| R-08 | PII em logs/eventos/traces | Média | Alta | Minimização, redaction, cardinalidade controlada (sem IDs em labels) |
| R-09 | Escala prometida sem prova (1M pedidos/s = 86,4 bi/dia) | Baixa | Alta | L0–L4 como cargas artificiais; nunca declarar sem benchmark |
| R-10 | Conformidade LGPD/GDPR/fiscal/PCI afirmada sem base | Baixa | Alta | Tratar como requisito de design; sem especialista, sem ativação |
