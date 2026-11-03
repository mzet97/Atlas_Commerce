# atlas-control-api — Control modular monolith (M2 slice: catalog_ops)

Owns ONLY approvals, audit trails and cases. NEVER writes the canonical
state of Catalog/Offer/Inventory/Order/Payment: mutating calls go to the
owner service over an authenticated command channel; reads use projections.

## Modules

```text
src/atlas_control/
  auth.py         OIDC JWT verify (JWKS) + role/ABAC gate
  audit.py        admin_actions append-only log (control database)
  catalog_ops.py  create/publish/get forwarded to atlas-catalog
  main.py         FastAPI entry (lifespan clients)
```

## Rules enforced here
- Every mutation needs identity + `catalog_editor` role, else 403 AND an
  audit row with `result='denied'` (INV-007).
- The UI is never the perimeter: checks run on every request, server-side.
