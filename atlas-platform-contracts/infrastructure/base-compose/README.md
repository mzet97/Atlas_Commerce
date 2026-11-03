# Base compose (M1 core profile)

Dev/demo only. Docker runs on the **host**; always prefix with
`distrobox-host-exec` from this container.

```sh
cd atlas-platform-contracts/infrastructure/base-compose
cp .env.example .env   # change secrets; .env is git-ignored
distrobox-host-exec docker compose --profile core up -d --build
distrobox-host-exec docker compose ps
curl http://localhost:8100/health
```

## Host ports

| Service | Host | Container |
|---|---|---|
| smoke-api | 8100 | 8000 |
| mongo | 27017 | 27017 |
| postgres | 5432 | 5432 |
| redis | 6379 | 6379 |
| keycloak | 8180 | 8080 |
| grafana (otel-lgtm) | 3300 | 3000 |
| OTLP gRPC/HTTP | 4319/4320 | 4317/4318 (4317 taken on host) |

Keycloak admin: values from `.env` (dev only). Grafana: `admin/admin`.
Tear down: `... docker compose --profile core down -v` (drops dev data).
