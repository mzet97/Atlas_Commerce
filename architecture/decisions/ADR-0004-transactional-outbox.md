# ADR-0004 — Outbox transacional no MongoDB

Status: PROPOSED (com prova na fatia Catalog). Data: 2026-10-27.

## Contexto
Dual write (commit no banco + publish no broker) perde eventos em queda
entre as duas escritas.

## Decisão
Agregado + documento outbox na mesma transação local Mongo; relay publica
em Kafka e marca `published`; projector deduplica por
`(consumer_id, event_id)`. CDC de coleção bruta NÃO é contrato — o envelope
versionado (`contracts/asyncapi/domain-event-envelope.yaml`) é.

## Evidência até aqui
EVD-002-001: `test_slice` prova entrega duplicada → 1 linha; E2E vivo com
`outbox unpublished = 0` e lag 0. Replica set single-node obrigatório até
no dev (`mongo --replSet`, `mongo-init` no compose).

## Consequências
Transações locais obrigatórias; replay por reprocessamento do log;
`processed_events` cresce (retenção a definir em M6/M9).
