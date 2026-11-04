# Atlas Commerce — Program Portfolio (M11, updated 2026-11-03)

Evidence-first SDD, M0→M10 executed and closed in a single monorepo
(github.com/mzet97/Atlas_Commerce), CI green on the runner. Every claim
below links to a dated evidence file with observed output; remaining
limits are named, never hidden.

| Milestone | Status | Proof |
|---|---|---|
| M0 audit | PASS | source hashes, UC/INV cross-audit, discovery artifacts |
| M1 foundation | COMPLETE | compose core, realm+OIDC, root CI green on runner (TASK-001-008/009/010) — EVD-001-005/006/007 |
| M2 catalog/offers/inventory | PASS | suites green, oversell=0, projections deterministic (pg baked initdb) |
| M3 checkout/PSP | PASS | saga 12-check drill, duplicate_paid_order=0, HMAC webhook |
| M4 admin hardening | COMPLETE | four-eyes + value thresholds + ops cancel + PENDING sweeper |
| M5 storefront UX | COMPLETE | search, i18n (pt/en/es), SEO surface, pagination+facets; 13 Playwright specs |
| M6 fulfillment | COMPLETE | ship+carrier label, refunds (PSP truth first), RMA, RabbitMQ quorum dispatcher (45 drained) |
| M7 AI shopping | COMPLETE | LangGraph doc-08 graph, read-only tools, injection bypass=0, curation TTL/weight ranking, evals EVAL PASS |
| M8 K8s | COMPLETE (EVD-008-002/003) | full deploy surface (secrets script, ExternalName infra, ingress, NetPol, HPA/PDB; kubeconform 46/46) — deploy blocked by rootless host (EVD-008-002 has the revival recipe) |
| M9 benchmarks | COMPLETE (L0+L1+ceiling+soak+chaos measured; L2/L3 require multi-node topology — named as limitation) | L1 measured 83k reqs: checkout p95 148ms (SLO ✓), nav p95 2.48s @950/s single replica (SLO ✗, bottleneck named); chaos RTO 2.9s; L2/L3 blocked (no cluster) |
| M10 marketplace 3P | COMPLETE | seller tenancy (cross-tenant 403 audited), concurrent offers + buybox, split settlement (10% commission), velocity antifraude — EVD-010-001 |
| M11 portfolio | THIS FILE | + progress.md FASE-0..9 entries |

ADRs 0001–0007 ACCEPTED (2026-11-03) with evidence links. OPEN-01..06
DECIDED (equivalence table in decisions-open.md).

Remaining limits (named): K8s deploy + L2/L3 need a deployable cluster
(rootless host recipe documented); navigation SLO at 950/s needs store
replicas; M11-next candidates: multi-region, real PSP sandbox, LGPD/GDPR
review with counsel.
