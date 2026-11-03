# ADR-0001 — Storefront em microserviços, Control em monólito modular

Status: PROPOSED. Data: 2026-10-27.

## Contexto
Duas experiências com cadência distinta (loja elástica, operação auditável)
sobre um domínio canônico único. Ver `sdd/glossary.md` (ownership).

## Decisão
`atlas-storefront`: um serviço Python por bounded context real, emergindo
por fatia vertical (Catalog primeiro, EVD-002-001). `atlas-control`: um
FastAPI em monólito modular (`catalog_ops`, ...), que nunca persiste estado
canônico alheio (EVD-002-002: banco `control` só tem `admin_actions`).

## Alternativas
- Monólito único: rejeitado — cadências e perímetros de falha distintos.
- Microserviços para tudo de saída: rejeitado — serviços vazios por
  antecipação são proibidos pelo SDD; só o Catalog existe até aqui.

## Consequências
Admin depende das APIs dos owners → exige contract testing + comandos
autenticados (pendente: testes de contrato automatizados).
