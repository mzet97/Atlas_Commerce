#!/usr/bin/env bash
# M8 deploy helper (dev gate). Secrets NEVER live in git: this script
# creates them from the compose .env (same dev-only values), then applies
# the manifests. On a real cluster swap the Secret for SealedSecrets/ESO.
#
#   HOST_INFRA_IP  IP reachable from pods for compose-published infra
#                  (mongo/pg/kafka/keycloak/redis/rabbit). Defaults to the
#                  k3d/k3s node gateway; override when topology differs.
#   DRY_RUN        pass " --dry-run=server" to validate server-side.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=${ENV_FILE:-../../infrastructure/base-compose/.env}
[ -f "$ENV_FILE" ] || ENV_FILE=./.env
set -a; source "$ENV_FILE"; set +a

HOST_INFRA_IP=${HOST_INFRA_IP:-192.168.1.11}
DRY_RUN=${DRY_RUN:-}

kubectl create namespace atlas ${DRY_RUN:+--dry-run=server} -o yaml ${DRY_RUN:+--validate=true} 2>/dev/null | kubectl apply -f - || true
kubectl -n atlas create secret generic atlas-secrets \
  --from-literal=PG_PASSWORD="$PG_PASSWORD" \
  --from-literal=KC_DB_PASSWORD="$KC_DB_PASSWORD" \
  --from-literal=KC_ADMIN_USER="$KC_ADMIN_USER" \
  --from-literal=KC_ADMIN_PASSWORD="$KC_ADMIN_PASSWORD" \
  --from-literal=PSP_WEBHOOK_SECRET="$PSP_WEBHOOK_SECRET" \
  --dry-run=client -o yaml | kubectl apply ${DRY_RUN:+--dry-run=server} -f -

kubectl apply ${DRY_RUN:+--dry-run=server} -R -f . --skip 20-infra-endpoints.yaml 2>/dev/null \
  || kubectl apply ${DRY_RUN:+--dry-run=server} -R -f .

# Infra endpoints carry the host IP: render it in (ExternalName has no env).
if command -v envsubst >/dev/null 2>&1; then
  envsubst < 20-infra-endpoints.yaml | kubectl apply ${DRY_RUN:+--dry-run=server} -f -
else
  sed "s/\${HOST_INFRA_IP}/${HOST_INFRA_IP}/g" 20-infra-endpoints.yaml \
    | kubectl apply ${DRY_RUN:+--dry-run=server} -f -
fi

echo "deploy complete (dry_run=${DRY_RUN:-no})"
