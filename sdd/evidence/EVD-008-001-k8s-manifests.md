# EVD-008-001 — M8 increment-1: manifestos K8s (gate estrutural)

Status: PASS estrutural; `NOT_DEPLOYED` (sem cluster no ambiente).

## Escopo
`atlas-platform-contracts/infrastructure/k8s/`: namespace + configmap,
18 Deployments (5 APIs + 9 relay/projector workers + psp-fake +
control + storefront) e 8 Services. `validate.py` é o gate.

## Prova (observado)
- `python3 validate.py` → `ALL PASS (18 Deployments, 8 Services)`:
  namespace `atlas` pinado, selector≡labels, env completo por papel,
  probes só nas APIs servantoras, resources em tudo, Services ligados,
  secrets só via `atlas-secrets`, psp-fake com label `dev-only=true`.
- Dois achados do próprio gate, corrigidos: contagem 15→18 e `command`
  explícito no storefront (era CMD implícito da imagem).

## Decisões registradas
- Secrets fora do git (`atlas-secrets` nasce na M8-2 via SealedSecrets/ESO).
- `control-api` escuta `0.0.0.0:8000` em cluster (o bind `127.0.0.1:8102`
  é dev-only do compose).
- Infra (mongo/pg/kafka/keycloak/redis), ingress/TLS, NetworkPolicy do
  psp-fake, HPA/PDB e `dry-run=server` ficam p/ M8-2 com cluster real.

## Fora do escopo (OPEN, sem ornamento)
- Qualquer `kubectl apply`; L1+ (`NOT_MEASURED`); remotes/commits.
