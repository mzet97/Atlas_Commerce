#!/bin/bash
# Seed hot SKU on the k8s1 cluster via Control (Local machine 192.168.1.11:8102)
CONTROL="http://192.168.1.11:8102"
INVENTORY="http://192.168.1.11:8104"
KEYCLOAK="http://192.168.1.11:8180"
TAG="l2-$(date +%s)"

TOKEN=$(curl -s -X POST "http://localhost:8180/realms/atlas/protocol/openid-connect/token" \
  -d 'client_id=atlas-storefront&username=cara.catalog&password=cara-dev-only&grant_type=password' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

PRODUCT=$(curl -s -X POST "$CONTROL/ops/products" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title":{"pt-BR":"Bench L2 SKU"},"idempotency_key":"l2-'$TAG'","correlation_id":"l2-'$TAG'"}')
SKU=$(echo "$PRODUCT" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST "$CONTROL/ops/products/$SKU/publish" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"expected_version":1,"correlation_id":"l2-'$TAG'"}' >/dev/null
OFFER=$(curl -s -X POST "$CONTROL/ops/offers" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"sku_id":"'$SKU'","seller_id":"atlas","market_id":"BR","channel":"web","currency":"BRL","price_minor":1999,"idempotency_key":"l2o-'$TAG'","correlation_id":"l2-'$TAG'"}')
OFFER_ID=$(echo "$OFFER" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST "$INVENTORY/positions/receive" -H "Content-Type: application/json" \
  -d '{"warehouse_id":"W1","sku_id":"'$SKU'","quantity":100000,"correlation_id":"l2-'$TAG'"}' >/dev/null
echo "$OFFER_ID"
