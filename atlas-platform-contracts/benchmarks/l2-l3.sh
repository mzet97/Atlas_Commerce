#!/usr/bin/env bash
# Atlas L2/L3 benchmarks (doc 05 stages 2–3) — requires a live cluster
# (post unlock-cluster.sh / deploy.sh). Parameterized by stage:
#
#   bash l2-l3.sh <SKU> <OFFER> [L2|L3] [TARGET_NODE_OR_LB]
#
#   L2: 10k nav RPS + 200 checkouts/s, 5 min steady  (cluster, multi-pod+HPA)
#   L3: 100k nav RPS + 2000 checkouts/s, 3 min       (multi-node — só com
#        nós reais suficientes; o script mede e reporta o teto honestamente)
#
# A carga roda DENTRO do cluster (um pod k6 via kubectl run) ou de fora
# contra o NodePort/LB — o harness escolhe pelo argumento de destino.
# Resultados + fingerprint em results/<run_id>/ (doc 05 §4).
set -euo pipefail
cd "$(dirname "$0")"

SKU="${1:?SKU do hot path}"; OFFER="${2:?OFFER do hot path}"
STAGE="${3:-L2}"
TARGET="${4:-in-cluster}"

case "$STAGE" in
  L2) NAV=10000; CHK=200; DUR=5m ;;
  L3) NAV=100000; CHK=2000; DUR=3m ;;
  *) echo "stage deve ser L2 ou L3"; exit 1 ;;
esac

RUN_ID="$(date +%Y%m%dT%H%M%S)-$STAGE"
RUN_DIR="results/$RUN_ID"
mkdir -p "$RUN_DIR"

commit=$(git rev-parse HEAD 2>/dev/null || echo unknown)
{
  echo "{"
  echo "  \"stage\": \"$STAGE\", \"target\": \"$TARGET\","
  echo "  \"nav_rate\": $NAV, \"checkout_rate\": $CHK, \"duration\": \"$DUR\","
  echo "  \"commit\": \"$commit\","
  echo "  \"kernel\": \"$(uname -r)\", \"cpus\": $(nproc),"
  echo "  \"generated\": \"$(date -Is)\""
  echo "}"
} > "$RUN_DIR/fingerprint.json"

cat > "$RUN_DIR/k6-stage.js" <<K6JS
import http from "k6/http";
import { check, sleep } from "k6";
export const options = {
  scenarios: {
    nav: { executor: "constant-arrival-rate", rate: $NAV, timeUnit: "1s",
      duration: "$DUR", preAllocatedVUs: 2000, maxVUs: 8000 },
    checkout: { executor: "constant-arrival-rate", rate: $CHK, timeUnit: "1s",
      duration: "$DUR", preAllocatedVUs: 200, maxVUs: 1000, startTime: "30s" },
  },
  thresholds: {
    "http_req_duration{scenario:checkout}": ["p(95)<1500"],
    checks: ["rate>0.9"],
  },
};
let offer = __ENV.OFFER_ID || "";
export default function () {
  const c = http.get("http://localhost:8101/products?q=cafeteira");
  check(c, { "catalog 200": (r) => r.status === 200 });
  if (offer) {
    const tag = __VU + "-" + __ITER + "-" + Date.now();
    const cart = http.post("http://localhost:8106/carts",
      JSON.stringify({ customer_id: "stg-" + __VU, correlation_id: "c-" + tag }),
      { headers: { "Content-Type": "application/json" } });
    http.post("http://localhost:8106/carts/" + cart.json("id") + "/items",
      JSON.stringify({ offer_id: offer, quantity: 1, correlation_id: "c-" + tag }),
      { headers: { "Content-Type": "application/json" } });
    let qid = "";
    for (let i = 0; i < 15; i++) {
      const q = http.post("http://localhost:8106/carts/" + cart.json("id") + "/quote");
      if (q.status === 201) { qid = q.json("id"); break; }
      sleep(0.4);
    }
    if (qid) {
      const co = http.post("http://localhost:8106/checkouts",
        JSON.stringify({ quote_id: qid, customer_id: "stg-" + __VU,
          card_last4: "4242", idempotency_key: "stg-" + tag,
          correlation_id: "c-" + tag }),
        { headers: { "Content-Type": "application/json" }, timeout: "90s" });
      check(co, { settled: (r) => r.status === 201 || r.status === 202 });
    }
  }
  sleep(0.05);
}
K6JS

TARGET_URL=""
if [ "$TARGET" = "in-cluster" ]; then
  # k6 dentro do cluster: NodePort do catalog/order via hostNetwork pods
  NODEIP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
  TARGET_URL="http://${NODEIP}"
  sed -i "s#http://localhost:8101#${TARGET_URL}:8101#; s#http://localhost:8106#${TARGET_URL}:8106#" \
    "$RUN_DIR/k6-stage.js"
fi

if command -v k6 >/dev/null 2>&1; then
  K6=k6
else
  K6="/home/mzet/.local/bin/k6"
fi
OFFER_ID="$OFFER" "$K6" run --summary-export "$RUN_DIR/k6-summary.json" \
  "$RUN_DIR/k6-stage.js" > "$RUN_DIR/k6-run.log" 2>&1

python3 - "$RUN_DIR" "$STAGE" <<'PYEOF'
import json, glob, sys, os
run_dir, stage = sys.argv[1], sys.argv[2]
p = os.path.join(run_dir, "k6-summary.json")
s = json.load(open(p))
m = s["metrics"]
key = [k for k in m if k.startswith("http_req_duration{scenario:checkout}")]
out = {
  "stage": stage,
  "http_reqs": m["http_reqs"]["count"],
  "checkout_p95_ms": round(m[key[0]]["p(95)"], 1) if key else None,
  "checkout_slo_1500ms_crossed": m[key[0]]["thresholds"]["p(95)<1500"] if key else None,
  "checks_rate": round(m["checks"]["value"], 4),
}
json.dump(out, open(os.path.join(run_dir, "summary.json"), "w"), indent=2)
print(json.dumps(out, indent=1))
PYEOF
echo "resultado em $RUN_DIR/summary.json"
