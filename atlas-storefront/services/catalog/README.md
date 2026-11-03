# atlas-catalog — Catalog owner service (M2 slice)

First real domain service. Owns `Product` aggregates + outbox; publishes
versioned events; NEVER reads PG projections to decide writes.

## Layout

```text
src/atlas_catalog/
  domain/        entities, events, errors (pure, no IO)
  application/   commands, handlers, ports
  infrastructure/mongo.py  motor repo (transactions + outbox)
  api.py         FastAPI (owner view)
  relay.py       outbox -> Kafka (python -m atlas_catalog.relay)
  projector.py   Kafka -> PG read model (python -m atlas_catalog.projector)
  main.py        uvicorn entry
tests/           pytest: domain (pure) + api/concurrency (needs stack)
migrations/      001_catalog_projection.sql
```

## Local dev (stack up: `--profile core --profile m2`)

```sh
cd services/catalog
uv sync --group dev
MONGO_URL=mongodb://localhost:27017/catalog?replicaSet=rs0 uv run pytest
```
