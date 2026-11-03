import http from "k6/http";
import { check, sleep } from "k6";

/**
 * Atlas L1 benchmark (doc 05 stage 1): 1k catalog RPS + 20 checkouts/s in
 * the lab (compose). ~95% navigation, SKU-hot checkouts via the real saga.
 * Gates (SLOs §2): checkout p95 < 1.5s to PENDING accept; oversell = 0;
 * projection lag p99 < 5s (asserted by the post-run probe).
 */

const CATALOG = "http://localhost:8101";
const ORDER = "http://localhost:8106";
const STORE = "http://localhost:3100";

export const options = {
  scenarios: {
    navigation: {
      executor: "constant-arrival-rate",
      rate: 950,
      timeUnit: "1s",
      duration: "2m",
      preAllocatedVUs: 200,
      maxVUs: 600,
      exec: "nav",
    },
    checkout: {
      executor: "constant-arrival-rate",
      rate: 20,
      timeUnit: "1s",
      duration: "2m",
      preAllocatedVUs: 20,
      maxVUs: 120,
      startTime: "15s",
      exec: "checkout",
    },
  },
  thresholds: {
    "http_req_duration{scenario:navigation}": ["p(95)<400"],
    "http_req_duration{scenario:checkout}": ["p(95)<1500"],
    checks: ["rate>0.99"],
  },
};

let sku = __ENV.SKU_ID || "";
let offer = __ENV.OFFER_ID || "";

export function nav() {
  const res = http.get(`${CATALOG}/products?q=cafeteira`);
  check(res, { "catalog 200": (r) => r.status === 200 });
  const page = http.get(`${STORE}/`);
  check(page, { "storefront 200": (r) => r.status === 200 });
  sleep(0.1);
}

export function checkout() {
  if (!offer) return; // probe seeds the hot SKU before the run
  const tag = `${__VU}-${__ITER}-${Date.now()}`;
  const cart = http.post(
    `${ORDER}/carts`,
    JSON.stringify({ customer_id: `bench-${__VU}`, correlation_id: `b-${tag}` }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(cart, { "cart 201": (r) => r.status === 201 });
  http.post(
    `${ORDER}/carts/${cart.json("id")}/items`,
    JSON.stringify({ offer_id: offer, quantity: 1, correlation_id: `b-${tag}` }),
    { headers: { "Content-Type": "application/json" } },
  );
  let quoteId = "";
  for (let i = 0; i < 20; i++) {
    const q = http.post(`${ORDER}/carts/${cart.json("id")}/quote`);
    if (q.status === 201) {
      quoteId = q.json("id");
      break;
    }
    sleep(0.5);
  }
  check(quoteId, { "quote ready": (q) => q !== "" });
  const started = Date.now();
  const co = http.post(
    `${ORDER}/checkouts`,
    JSON.stringify({
      quote_id: quoteId,
      customer_id: `bench-${__VU}`,
      card_last4: "4242",
      idempotency_key: `bench-${tag}`,
      correlation_id: `b-${tag}`,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "90s" },
  );
  check(co, {
    "checkout settled": (r) => r.status === 201 || r.status === 202,
  });
  sleep(0.05);
}
