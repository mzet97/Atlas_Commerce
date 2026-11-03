#!/usr/bin/env bash
# Local ceiling probe: 5k nav RPS + 50 checkouts/s for 2 minutes.
set -eu
RUN_DIR=${1:?run dir}
mkdir -p "$RUN_DIR"
cat > "$RUN_DIR/k6-ceiling.js" <<K6JS
import http from "k6/http";
import { check, sleep } from "k6";
export const options = {
  scenarios: {
    nav: { executor: "constant-arrival-rate", rate: 5000, timeUnit: "1s",
      duration: "2m", preAllocatedVUs: 600, maxVUs: 1200 },
    checkout: { executor: "constant-arrival-rate", rate: 50, timeUnit: "1s",
      duration: "2m", preAllocatedVUs: 40, maxVUs: 240, startTime: "15s" },
  },
  thresholds: { checks: ["rate>0.9"] },
};
let offer = __ENV.OFFER_ID || "";
export default function () {
  const c = http.get("http://localhost:8101/products?q=cafeteira");
  check(c, { "catalog 200": (r) => r.status === 200 });
  if (offer) {
    const tag = __VU + "-" + __ITER + "-" + Date.now();
    const cart = http.post("http://localhost:8106/carts",
      JSON.stringify({ customer_id: "ceil-" + __VU, correlation_id: "c-" + tag }),
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
        JSON.stringify({ quote_id: qid, customer_id: "ceil-" + __VU,
          card_last4: "4242", idempotency_key: "ceil-" + tag,
          correlation_id: "c-" + tag }),
        { headers: { "Content-Type": "application/json" }, timeout: "90s" });
      check(co, { settled: (r) => r.status === 201 || r.status === 202 });
    }
  }
  sleep(0.05);
}
K6JS
k6 run --summary-export "$RUN_DIR/k6-summary.json" "$RUN_DIR/k6-ceiling.js" > "$RUN_DIR/k6-run.log" 2>&1
echo "done: $RUN_DIR/k6-summary.json"
