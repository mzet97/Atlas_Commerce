import http from "k6/http";
import { check, sleep } from "k6";
import { Counter } from "k6/metrics";

const CATALOG = "http://192.168.1.51:30101";
const ORDER = "http://192.168.1.51:30106";
const OFFER = __ENV.OFFER_ID || "";
const STAGE = __ENV.STAGE || "L2";

const checkoutsAttempted = new Counter("checkouts_attempted");
const checkoutsConfirmed = new Counter("checkouts_confirmed");

export const options = {
  scenarios: {
    nav: {
      executor: "constant-arrival-rate",
      rate: parseInt(__ENV.NAV_RATE || "10000"),
      timeUnit: "1s",
      duration: __ENV.DURATION || "5m",
      preAllocatedVUs: 2000,
      maxVUs: 8000,
    },
    checkout: {
      executor: "constant-arrival-rate",
      rate: parseInt(__ENV.CHK_RATE || "200"),
      timeUnit: "1s",
      duration: __ENV.DURATION || "5m",
      preAllocatedVUs: 200,
      maxVUs: 1000,
      startTime: "30s",
    },
  },
  thresholds: {
    "http_req_duration{scenario:checkout}": ["p(95)<1500"],
    checks: ["rate>0.95"],
  },
};

export default function () {
  const tag = __VU + "-" + __ITER + "-" + Date.now();
  const c = http.get(`${CATALOG}/products?q=cafeteira`);
  check(c, { "catalog 200": (r) => r.status === 200 });
  if (!offer) return;
  const cart = http.post(
    `${ORDER}/carts`,
    JSON.stringify({ customer_id: `bench-${__VU}`, correlation_id: `c-${tag}` }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(cart, { "cart 201": (r) => r.status === 201 });
  if (cart.status === 201) {
    http.post(
      `${ORDER}/carts/${cart.json("id")}/items`,
      JSON.stringify({ offer_id: offer, quantity: 1, correlation_id: `c-${tag}` }),
      { headers: { "Content-Type": "application/json" } }
    );
    let qid = "";
    for (let i = 0; i < 15; i++) {
      const q = http.post(`${ORDER}/carts/${cart.json("id")}/quote`);
      if (q.status === 201) { qid = q.json("id"); break; }
      sleep(0.5);
    }
    if (qid) {
      const co = http.post(
        `${ORDER}/checkouts`,
        JSON.stringify({
          quote_id: qid, customer_id: `bench-${__VU}`, card_last4: "4242",
          idempotency_key: `stg-${STAGE}-${tag}`, correlation_id: `c-${tag}`,
        }),
        { headers: { "Content-Type": "application/json" }, timeout: "90s" }
      );
      checkoutsAttempted.add(1);
      check(co, { "checkout settled": (r) => r.status === 201 || r.status === 202 });
      if (co.status === 201) checkoutsConfirmed.add(1);
    }
  }
  sleep(0.05);
}
