# atlas-control

Admin experience: Angular/TypeScript portal (planned) + Python/FastAPI
**modular monolith** (one process, strict module boundaries).

## Layout

```text
atlas-control/
├── apps/control-angular/      # planned (M5+: ng new, OIDC code+PKCE)
├── control-api/
│   ├── src/atlas_control/     # modules (flat, strict boundaries):
│   │   ├── catalog_ops.py     #   publish products via owner contract
│   │   ├── pricing_ops.py     #   offers (ABAC: market grants)
│   │   ├── stock_ops.py       #   inventory (ABAC: warehouse grants)
│   │   ├── finance_ops.py     #   reconcile + four-eyes approvals
│   │   ├── fulfillment_ops.py #   ship CONFIRMED orders
│   │   ├── ai_ops.py          #   recommendation allowlist curation
│   │   ├── command_channel.py #   owner forwarding + 403 auditing
│   │   ├── auth.py            #   Keycloak JWT verify + role/scope checks
│   │   └── audit.py           #   admin_actions ledger (own DB)
│   ├── migrations/            # SQL applied to the `control` DB
│   └── tests/                 # pytest against live stack (real JWTs)
└── .github/ → root workflows  # CI consolidated in monorepo root
```

## Rules (from M0 audit)

- Owns ONLY approvals, audit, cases. NEVER writes the canonical state of
  Catalog/Offer/Inventory/Order/Payment — commands go to owner services.
- Reads via projections, honoring `PUBLISHING` lag states.
- Sensitive actions require `requested_by != approved_by` (four-eyes).

## Quick start

```sh
# stack (control-api on :8102, host network, dev-only):
# see atlas-platform-contracts/infrastructure/base-compose (profile m2)
```

Status: control-api M4 hardening live (four-eyes finance approvals,
fulfillment, AI curation). Angular app not scaffolded yet — planned.
CI: root `.github/workflows/services.yaml` (ruff + pytest).
