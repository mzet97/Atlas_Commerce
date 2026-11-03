#!/bin/sh
# Idempotent Atlas realm bootstrap (dev only). Uses master bootstrap admin.
# env: KC_URL (default http://localhost:8180), KC_ADMIN_USER, KC_ADMIN_PASSWORD
set -eu
KC_URL="${KC_URL:-http://localhost:8180}"
: "${KC_ADMIN_USER:?}" : "${KC_ADMIN_PASSWORD:?}"
API="$KC_URL/admin/realms"

token() {
  # Keycloak may still be warming up; retry the bootstrap-admin grant.
  for i in 1 2 3 4 5; do
    T=$(curl -s -m 15 -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
      -d "client_id=admin-cli" -d "username=$KC_ADMIN_USER" \
      -d "password=$KC_ADMIN_PASSWORD" -d "grant_type=password" \
      | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
    [ -n "$T" ] && { echo "$T"; return 0; }
    sleep 5
  done
  echo "bootstrap admin grant never returned a token" >&2
  return 1
}
T=$(token)

call() { # method path [json]
  code=$(curl -s -m 15 -o /dev/null -w "%{http_code}" -X "$1" "$API$2" \
    -H "Authorization: Bearer $T" -H "Content-Type: application/json" ${3:+-d "$3"})
  echo "$1 $2 -> $code"
}

call POST "" '{"realm":"atlas","enabled":true,"displayName":"Atlas Commerce"}'
call POST "/atlas/roles" '{"name":"customer"}'
for r in catalog_editor pricing_manager inventory_operator fulfillment_operator \
         finance_analyst support_agent auditor iam_admin seller_operator; do
  call POST "/atlas/roles" "{\"name\":\"$r\"}"
done
call POST "/atlas/clients" '{"clientId":"atlas-storefront","publicClient":true,"directAccessGrantsEnabled":true,"standardFlowEnabled":true,"redirectUris":["http://localhost:3000/*","http://localhost:3100/*"]}'
call POST "/atlas/clients" '{"clientId":"atlas-control","publicClient":false,"secret":"atlas-control-dev-secret","serviceAccountsEnabled":true,"directAccessGrantsEnabled":true,"standardFlowEnabled":true,"redirectUris":["http://localhost:4200/*"]}'
mkuser() { # username password role email firstname lastname (profile avoids first-login UPDATE_PROFILE)
  call POST "/atlas/users" "{\"username\":\"$1\",\"enabled\":true,\"email\":\"$4\",\"emailVerified\":true,\"firstName\":\"$5\",\"lastName\":\"$6\",\"credentials\":[{\"type\":\"password\",\"value\":\"$2\",\"temporary\":false}]}"
  ID=$(curl -s -m 15 "$API/atlas/users?username=$1" -H "Authorization: Bearer $T" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
  ROLE=$(curl -s -m 15 "$API/atlas/roles/$3" -H "Authorization: Bearer $T")
  curl -s -m 15 -o /dev/null -w "map $1->$3 -> %{http_code}\n" -X POST \
    "$API/atlas/users/$ID/role-mappings/realm" \
    -H "Authorization: Bearer $T" -H "Content-Type: application/json" -d "[$ROLE]"
}
mkuser alice.customer "alice-dev-only" customer "alice@example.com" Alice Customer
mkuser erin.finance "erin-dev-only" finance_analyst "erin@example.com" Erin Finance
mkuser felix.finance "felix-dev-only" finance_analyst "felix@example.com" Felix Finance
mkuser gina.fulfillment "gina-dev-only" fulfillment_operator "gina@example.com" Gina Fulfillment
mkuser boss.admin "boss-dev-only" iam_admin "boss@example.com" Boss Admin
mkuser cara.catalog "cara-dev-only" catalog_editor "cara@example.com" Cara Catalog
mkuser pam.pricing "pam-dev-only" pricing_manager "pam@example.com" Pam Pricing
# cara also operates stock in the demo (separate role, least privilege kept:
# no pricing/finance roles, scopes below).
ID=$(curl -s -m 15 "$API/atlas/users?username=cara.catalog" -H "Authorization: Bearer $T" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
ROLE=$(curl -s -m 15 "$API/atlas/roles/inventory_operator" -H "Authorization: Bearer $T")
curl -s -m 15 -o /dev/null -w "map cara.catalog->inventory_operator -> %{http_code}\n" -X POST \
  "$API/atlas/users/$ID/role-mappings/realm" \
  -H "Authorization: Bearer $T" -H "Content-Type: application/json" -d "[$ROLE]"
# Scope grants live in the Control database (resolved by verified sub).
# psql goes through the compose pg container: plain docker where available
# (CI/standard hosts), distrobox-host-exec on this dev workstation.
psql_exec() {
  if command -v docker >/dev/null 2>&1; then
    docker exec -i atlas-base-pg-1 psql "$@"
  elif command -v distrobox-host-exec >/dev/null 2>&1; then
    distrobox-host-exec docker exec -i atlas-base-pg-1 psql "$@"
  else
    echo "no docker CLI: scope grants NOT seeded" >&2; return 0
  fi
}
if [ -n "${PG_PASSWORD:-}" ]; then
  # user -> granted scopes (least privilege per role)
  grant() { # user_id scope_type scope_id
    psql_exec -U postgres -d control \
      -c "INSERT INTO scope_grants(actor_sub, scope_type, scope_id) VALUES ('$1', '$2', '$3') ON CONFLICT DO NOTHING;" \
      2>&1 | tail -n 1
  }
  for scope in "market BR" "warehouse W1"; do
    st=${scope%% *}; sid=${scope##* }
    grant "$ID" "$st" "$sid"
  done
  PAM=$(curl -s -m 15 "$API/atlas/users?username=pam.pricing" -H "Authorization: Bearer $T" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
  grant "$PAM" "market" "BR"
else
  echo "PG_PASSWORD unset: scope grants NOT seeded (run with compose .env sourced)"
fi
echo DONE
