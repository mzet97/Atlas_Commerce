# ADR-0002 — CQRS: escrita MongoDB, leitura PostgreSQL

Status: PROPOSED (com prova na fatia Catalog). Data: 2026-10-27.

## Contexto
Escritas transacionais com outbox + leituras denormalizadas por consulta
(doc 04, diagrama 09).

## Decisão
MongoDB (replica set, transações locais) é a autoridade dos comandos;
PostgreSQL recebe projeções via outbox→Kafka→workers idempotentes
(`processed_events` na mesma transação da projeção).

## Evidência até aqui
EVD-002-001/002: produto criado/publicado no owner aparece na projeção;
`availability_hint` nunca decide saldo (INV-CQRS-001); lag do projector = 0
no demo. Regra operacional: Keycloak/observabilidade usam stores próprios
— CQRS não se impõe a infraestrutura (doc 06 §5).

## Consequências
Eventual consistency + `PUBLISHING`: a UI ainda não exibe o estado
intermediário (TODO M2-next). Reversão: voltar a leitura direta do owner
exige reescrever a Storefront; projeções são descartáveis por construção.
