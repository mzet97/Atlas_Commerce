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
