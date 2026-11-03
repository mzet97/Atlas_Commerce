# M9 benchmark results

Layout per doc 05 §4: results/<run_id>/ with fingerprint, k6 script output
and honest verdicts. Never declare a stage without a measured run here.

- `20261103T152532/` — L1 (compose lab): 83k requests, checkout p95 148ms
  (SLO 1500ms ✓), navigation p95 2482ms @950/s single-replica (SLO ✗,
  bottleneck = Next SSR, med 88ms) — the "action" field records the fix
  path. Chaos drill in `chaos/`: catalog-api kill under load, RTO 2.9s
  (compose restart), storefront reads 100% during the outage (CQRS read
  model, INV-CQRS-001 in practice).
- L2/L3: blocked on this host (rootless, no cluster — EVD-008-002);
  harness is stage-parameterized and ready.
