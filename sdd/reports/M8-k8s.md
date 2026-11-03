# Report M8 — K8s (2026-10-28) — PARCIAL (increment-1, NOT_DEPLOYED)

Entregue: 18 Deployments + 8 Services (namespace+configmap) com gate
estrutural `validate.py` verde (seletores, env, probes, resources,
secrets só via `atlas-secrets`, psp-fake `dev-only`). Nada aplicado:
sem cluster no ambiente. Evidência: EVD-008-001-k8s-manifests. Gate M8
OPEN: secrets (SealedSecrets/ESO), infra stateful, ingress/TLS,
NetworkPolicy, HPA/PDB, dry-run=server.
