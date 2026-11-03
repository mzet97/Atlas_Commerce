# atlas-storefront

Customer experience: Next.js/TypeScript storefront + Python/FastAPI
microservices (one bounded context per service, emerging per vertical slice).

## Layout (grows per SPEC, never empty services by anticipation)

```text
atlas-storefront/
├── apps/storefront-next/      # created in M1 via create-next-app
├── services/<context>/        # one per owner: catalog, offers, inventory, ...
├── workers/                   # projection / notification workers
├── tests/                     # integration, contracts, e2e, load, chaos
├── deploy/compose/            # local profiles (M1)
├── deploy/helm/               # on-prem charts (M8)
└── specs/ docs/               # this repo's SDD specs
```

## Rules (from M0 audit)

- MongoDB write + outbox in the same transaction; PostgreSQL is a derived
  read model, never the checkout/stock authority.
- Events versioned per `atlas-platform-contracts`; N/N-1 compatibility.
- Money in minor units, never float. No PAN/CVV anywhere.

## Quick start (M1 target, not yet green)

```sh
# planned: compose core profile + smoke
docker compose --profile core up
```

Status: scaffold M1-increment-1. No services yet (SPEC-002 defines the first).
