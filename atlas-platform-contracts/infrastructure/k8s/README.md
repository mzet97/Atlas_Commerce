# k8s (M8 increment-1): app-layer manifests, structural gate only

15 Deployments (5 APIs + relay/projector workers + psp-fake) and 8
ClusterIP Services in namespace `atlas`. Images `atlas-*:dev` are built
from the repo Dockerfiles; `atlas-secrets` (pg-dsn, control-pg-dsn,
psp-webhook-secret) does NOT exist yet.

## Status: NOT_DEPLOYED (honest)

No cluster exists in this environment (no kubectl/kind/k3d), so nothing
was applied. What IS proven: `python3 validate.py` parses every document
and enforces the Atlas contract (namespace, selector wiring, env
completeness, probes on serving APIs only, resources, secret refs,
psp-fake `dev-only` label).

## M8-increment-2 (OPEN)

- `atlas-secrets` via SealedSecrets/ESO (never plaintext in git).
- Infra: mongo RS, postgres, kafka, keycloak, redis (StatefulSets or
  managed), ingress + TLS, NetworkPolicy isolating psp-fake.
- HPA on APIs + PDBs; `kubectl apply --dry-run=server` against a real
  cluster; image digests pinned per release.
