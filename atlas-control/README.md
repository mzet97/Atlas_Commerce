# atlas-control

Admin experience: Angular/TypeScript portal + Python/FastAPI **modular
monolith** (one process, strict module boundaries).

## Layout (grows per SPEC)

```text
atlas-control/
├── apps/control-angular/                 # created in M1 via ng new
├── control-api/src/atlas_control/
│   ├── modules/{catalog_ops,inventory_ops,pricing_ops,approvals,audit,reports,iam}/
│   └── shared/{auth,telemetry,errors}/
├── tests/
├── deploy/compose/ deploy/helm/
└── specs/ docs/
```

## Rules (from M0 audit)

- Owns ONLY approvals, audit, cases. NEVER writes the canonical state of
  Catalog/Offer/Inventory/Order/Payment — commands go to owner services.
- Reads via projections, honoring `PUBLISHING` lag states.
- Sensitive actions require `requested_by != approved_by` (four-eyes).

Status: scaffold M1-increment-1. No modules yet (SPEC-004 defines hardening).
