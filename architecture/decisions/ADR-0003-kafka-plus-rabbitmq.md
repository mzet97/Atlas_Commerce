# ADR-0003 — Kafka (eventos) + RabbitMQ (tarefas)

Status: PROPOSED. Data: 2026-10-27.

## Contexto
Log de eventos de domínio (replay, analytics) vs. tarefas pontuais
(notificar, gerar etiqueta) têm garantias distintas (doc 06 §3).

## Decisão
Kafka para eventos persistidos/CDC/analytics; RabbitMQ (quorum queues,
DLQ, retry idempotente) para workflows pontuais. Anti-padrão proibido:
emitir o mesmo evento nos dois brokers no request handler — outbox→Kafka
uma vez; tasks de Rabbit nascem de consumer/bridge idempotente.

## Estado
Kafka KRaft 4.0.0 no ar com o relay do Catalog publicando
(`atlas.catalog.*.v1`). RabbitMQ ainda não implantado (primeiro uso real:
M6 notifications/fulfillment).

## Consequências
Overhead operacional de dois brokers; documentar por caso qual é
obrigatório quando o primeiro uso de cada lado chegar.
