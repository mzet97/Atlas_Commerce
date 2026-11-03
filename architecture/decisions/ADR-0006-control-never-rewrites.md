# ADR-0006 — Control não reescreve estado do Storefront

Status: PROPOSED (com prova na fatia Admin). Data: 2026-10-27.

## Contexto
Dois produtos, um domínio canônico; split-brain nasce quando o Admin escreve
direto nas coleções dos owners.

## Decisão
O Control possui só approvals/audit/cases (banco `control`, tabela
`admin_actions`) e executa mudanças de negócio por comandos autenticados ao
serviço dono; leitura via projeções. EVD-002-002: create/publish via
`:8102/ops/*` com JWT+role, 403 auditado, sem acesso ao Mongo do Catalog.

## Consequências
Disponibilidade do Admin depende dos owners; contratos e compatibilidade
N/N-1 viram requisito permanente (buf breaking + OpenAPI diff no CI).
