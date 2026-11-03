# atlas-control

Admin experience: Angular/TypeScript portal + Python/FastAPI **modular
monolith** (one process, strict module boundaries).

## Layout

```text
atlas-control/
├── apps/control-angular/      # Angular 22 admin SPA (OIDC code+PKCE,
│                              #   client atlas-control public at :4200)
│   ├── src/app/core/          # auth (oidc-client-ts), API interceptor
│   └── src/app/features/      # dashboard, orders, finance, coupons, returns
├── control-api/
│   ├── src/atlas_control/     # modules (flat, strict boundaries):
│   │   ├── catalog_ops.py     #   publish products via owner contract
│   │   ├── pricing_ops.py     #   offers (ABAC: market grants)
│   │   ├── stock_ops.py       #   inventory (ABAC: warehouse grants)
│   │   ├── order_ops.py       #   coupons (pricing_manager) + order cancel
│   │   ├── finance_ops.py     #   reconcile/refund + four-eyes approvals
│   │   ├── fulfillment_ops.py #   ship + returns/RMA queue
│   │   ├── ai_ops.py          #   recommendation allowlist curation
│   │   ├── command_channel.py #   owner forwarding + 403 auditing + threshold
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
- Sensitive actions require `requested_by != approved_by` (four-eyes)
  at or above `APPROVAL_THRESHOLD_MINOR`; below it one audited operator.

## Quick start

```sh
# stack (control-api on :8102 host-network, admin UI on :4200):
# atlas-platform-contracts/infrastructure/base-compose (profiles m2+)
# login as any seeded operator, e.g. erin.finance / erin-dev-only
```

Status: control-api M4/M6 hardening live; Angular admin live (OIDC
code+PKCE, finance/orders/coupons/returns modules, e2e admin.spec green).
CI: root `.github/workflows/services.yaml` (ruff+pytest) +
`storefront.yaml#control-ui` (ng build).
