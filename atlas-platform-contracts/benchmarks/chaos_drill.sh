#!/usr/bin/env bash
# M9 chaos drill: kill catalog-api under light load, measure RTO (health)
# + convergence (outbox drains; storefront reads survive via projections).
set -u
RUN_DIR=${1:-results/chaos}
mkdir -p "$RUN_DIR"
cat > "$RUN_DIR/k6-light.js" <<'K6JS'
import http from "k6/http";
import { check, sleep } from "k6";
export const options = {
  scenarios: { nav: { executor: "constant-arrival-rate", rate: 100,
    timeUnit: "1s", duration: "90s", preAllocatedVUs: 50, maxVUs: 120 } },
  thresholds: { checks: ["rate>0.9"] },
};
export default function () {
  const r = http.get("http://localhost:3100/");
  check(r, { "storefront 200": (x) => x.status === 200 });
  sleep(0.2);
}
K6JS
( k6 run --quiet --summary-export "$RUN_DIR/k6-chaos.json" "$RUN_DIR/k6-light.js" > /dev/null 2>&1 ) &
LOAD_PID=$!
sleep 12
T0=$(date +%s%3N)
distrobox-host-exec docker rm -f atlas-base-catalog-api-1 >/dev/null 2>&1
echo "killed catalog-api at $(date -Is)" >> "$RUN_DIR/events.log"
cd /var/mnt/4TB/TI/git/Atlas_Commerce/atlas-platform-contracts/infrastructure/base-compose
distrobox-host-exec docker compose --profile core --profile data --profile m2 --profile m3 up -d catalog-api >/dev/null 2>&1
until curl -sf -m 2 http://localhost:8101/health >/dev/null 2>&1; do sleep 1; done
T1=$(date +%s%3N)
echo "RTO_ms=$((T1 - T0))" | tee -a "$RUN_DIR/events.log"
kill "$LOAD_PID" 2>/dev/null || true
wait "$LOAD_PID" 2>/dev/null || true
