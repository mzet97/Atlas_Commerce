# atlas-storefront

Customer experience: Next.js/TypeScript storefront + Python/FastAPI
microservices (one bounded context per service).

## Layout

```text
atlas-storefront/
├── apps/storefront-next/      # Next.js 16 + React 19; reads PG projections
│   └── e2e/                   # Playwright specs + seed.py (reproducible dataset)
├── services/catalog/          # Catalog owner (outbox → Kafka → PG projection)
├── services/offers/           # Offers owner (one active offer per key)
├── services/inventory/        # Inventory owner (CAS reservations, ledger)
├── services/order/            # Cart/Quote/Checkout saga (Reserve→PENDING→Authorize)
├── services/payment/          # Payment intents + HMAC webhook (dedup atômica)
└── services/psp-fake/         # Deterministic fake PSP (dev-only)
```

Each service: `domain.py`, `application.py`, `api.py`, `mongo_repo.py`,
`relay.py`, `projector.py`, `main.py` (OTel-instrumented), `tests/` +
`pyproject.toml` (uv). Infra lives in `atlas-platform-contracts`
(compose profiles `core`/`data`/`m2`/`m3`).

## Rules (from M0 audit)

- MongoDB write + outbox in the same transaction; PostgreSQL is a derived
  read model, never the checkout/stock authority.
- Events versioned per `atlas-platform-contracts`; N/N-1 compatibility.
- Money in minor units, never float. No PAN/CVV anywhere.

## Quick start

```sh
# from atlas-platform-contracts/infrastructure/base-compose
cp .env.example .env
docker compose --profile m2 --profile m3 up -d --build   # full stack, :3100
```

Status: M3+ vertical slices live (catalog→offers→inventory→checkout→payment,
search, recommendations, fulfillment). CI: root `.github/workflows/`
(`services.yaml` ruff+pytest, `storefront.yaml` build+Playwright e2e).
