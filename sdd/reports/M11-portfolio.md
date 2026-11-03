# Atlas Commerce — Program Portfolio (M11, 2026-10-28)

Evidence-first SDD, M0→M9 executed end-to-end. Every claim below links to
a dated evidence file with observed command output; open items are named,
never hidden. Three repos remain uncommitted pending user review.

| Milestone | Status | Proof |
|---|---|---|
| M0 audit | PASS | source hashes, UC/INV cross-audit, 9 discovery artifacts |
| M1 foundation | partial PASS | compose core UP, realm + OIDC smoke, 3 CI workflows |
| M2 catalog/offers/inventory | PASS | 14+12+13+8 tests, E2E product→stock→store, oversell=0, Playwright |
| M3 checkout/PSP | COMPLETE | PSP fake + payment (21) + order saga (21), T01-T05 + checkout drills ALL PASS, duplicate_paid_order=0 |
| M4 admin hardening | partial | four-eyes reconcile (maker≠checker, 403 self-approval), control 21 tests |
| M5 search | partial | PG trigram (OPEN-05 PG-only), Playwright 5 passed |
| M6 fulfillment | partial | CONFIRMED→SHIPPED + notification queue (transport deferred), drill 5/5 |
| M7 AI allowlist | partial | recommendations = allowlisted∩ACTIVE only, negative test green |
| M8 K8s | partial | 18 Deployments + 8 Services, structural gate green, NOT_DEPLOYED (no cluster) |
| M9 benchmarks | partial | L0 measured: reads p95=4ms (n=3000), checkouts p95=143ms (n=60), 0 errors |
| M10 3P | DEFERRED | no third-party integration started |
| M11 portfolio | THIS FILE | milestone reports M0–M9 under `sdd/reports/` |

Deferred by design (not started, not claimed): K8s deploy, L1–L4,
refunds (no PSP refund), RabbitMQ dispatch, i18n/SEO, ML ranking,
remotes/CI runners (no remote), commits (awaiting review).
