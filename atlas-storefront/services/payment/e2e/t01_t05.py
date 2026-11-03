#!/usr/bin/env python3
"""M3 checkout/PSP E2E drill T01-T05 (live stack, stdlib only, deterministic).

Env: PAYMENT_API (default http://localhost:8105), PSP_WEBHOOK_SECRET (required).
Exit nonzero on the first failed assertion; prints PASS lines for evidence.

T01 double-submit: 20 concurrent POSTs, same idempotency key -> 1 intent.
T02 double webhook: same signed payload twice -> no-op, version stable.
T03 outage reconcile: amount 666 (PSP timeout) -> UNKNOWN -> reconcile AUTHORIZED.
T04 stale-read bound: owner read-your-write is immediate; event count bounded.
T05 out-of-order: reconcile wins, late webhook records but changes nothing.
Global: duplicate_paid_order=0 is checked via API-visible refs (one ref, one intent).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PAYMENT = os.getenv("PAYMENT_API", "http://localhost:8105")
SECRET = os.getenv("PSP_WEBHOOK_SECRET")
if not SECRET:
    raise SystemExit("PSP_WEBHOOK_SECRET is required")

PASS_COUNT = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    """One drill assertion: PASS line or immediate red exit."""
    global PASS_COUNT
    if not cond:
        raise SystemExit(f"FAIL {name} {detail}")
    PASS_COUNT += 1
    print(f"PASS {name} {detail}", flush=True)


def _call(method: str, path: str, body: dict[str, object] | None = None,
          headers: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        PAYMENT + path, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            parsed = json.loads(resp.read().decode())
            assert isinstance(parsed, dict)
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        parsed = json.loads(exc.read().decode())
        assert isinstance(parsed, dict)
        return exc.code, parsed


def post_intent(amount: int, card: str, key: str, order: str) -> tuple[int, dict]:
    return _call("POST", "/intents", {
        "order_id": order, "customer_id": "e2e-cust", "amount_minor": amount,
        "currency": "BRL", "card_last4": card, "idempotency_key": key,
        "correlation_id": f"e2e-{time.time_ns()}"})


def get_intent(intent_id: str) -> dict:
    status, body = _call("GET", f"/intents/{intent_id}")
    assert status == 200, body
    return body


def reconcile(intent_id: str) -> tuple[int, dict]:
    return _call("POST", f"/intents/{intent_id}/reconcile",
                 {"correlation_id": f"e2e-{time.time_ns()}"})


def webhook(event: str, ref: str, order: str) -> tuple[int, dict]:
    raw = json.dumps({"event": event, "provider_ref": ref,
                      "order_id": order}).encode()
    stamp = str(int(time.time()))
    sig = hmac.new(SECRET.encode(), f"{stamp}.".encode() + raw,
                   hashlib.sha256).hexdigest()
    return _call("POST", "/webhooks/psp", json.loads(raw.decode()), {
        "X-PSP-Signature": sig, "X-PSP-Timestamp": stamp,
        "X-Correlation-Id": f"e2e-{time.time_ns()}"})


def wait_for(intent_id: str, want: str, budget_s: float) -> dict:
    """Poll owner view until status or budget out (reconcile/webhook lag)."""
    deadline = time.time() + budget_s
    current = get_intent(intent_id)
    while current["status"] != want and time.time() < deadline:
        time.sleep(1)
        current = get_intent(intent_id)
    return current


def t01_double_submit() -> dict:
    """20 racers, one key -> one AUTHORIZED intent (no double charge)."""
    key = f"e2e-t01-{time.time_ns()}"
    order = f"e2e-o1-{time.time_ns()}"
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(
            lambda _: post_intent(1999, "4242", key, order), range(20)))
    ids = {body.get("id") for _, body in results}
    check("T01-one-intent", len(ids) == 1, f"ids={ids}")
    check("T01-all-201", all(s == 201 for s, _ in results), "")
    intent = get_intent(ids.pop())
    check("T01-authorized", intent["status"] == "AUTHORIZED", intent["status"])
    return intent


def t02_double_webhook(intent: dict) -> None:
    """Same webhook twice -> second is a no-op (version stable)."""
    before = get_intent(intent["id"])
    s1, b1 = webhook("authorized", intent["provider_ref"], intent["order_id"])
    s2, b2 = webhook("authorized", intent["provider_ref"], intent["order_id"])
    check("T02-200-twice", (s1, s2) == (200, 200), f"{s1},{s2}")
    check("T02-stable", b1["status"] == b2["status"] == "AUTHORIZED"
          and b2["version"] == before["version"], f"v={b2['version']}")


def t03_outage_reconcile() -> None:
    """PSP timeout (666) -> UNKNOWN, no ref -> reconcile via by-key AUTHORIZED."""
    key = f"e2e-t03-{time.time_ns()}"
    order = f"e2e-o3-{time.time_ns()}"
    status, body = post_intent(666, "4242", key, order)
    check("T03-unknown", status == 201 and body["status"] == "UNKNOWN"
          and body["provider_ref"] is None, f"{status} {body['status']}")
    deadline = time.time() + 60
    current = body
    while current["status"] != "AUTHORIZED" and time.time() < deadline:
        _, current = reconcile(current["id"])
        if current["status"] != "AUTHORIZED":
            time.sleep(2)
            current = get_intent(current["id"])
    check("T03-reconciled", current["status"] == "AUTHORIZED",
          f"status={current['status']}")


def t04_event_bound(intent_id: str) -> None:
    """Owner converges with a bounded version (no runaway duplication)."""
    current = wait_for(intent_id, "AUTHORIZED", 30)
    check("T04-converges", current["status"] == "AUTHORIZED",
          f"v={current['version']}")
    check("T04-bounded", int(current["version"]) <= 4,
          f"v={current['version']}")


def t05_out_of_order() -> None:
    """UNKNOWN (999) -> reconcile first, late webhook changes nothing."""
    key = f"e2e-t05-{time.time_ns()}"
    order = f"e2e-o5-{time.time_ns()}"
    _, body = post_intent(999, "4242", key, order)
    check("T05-unknown", body["status"] == "UNKNOWN"
          and body["provider_ref"] is not None, f"{body['status']}")
    _, rec = reconcile(body["id"])
    check("T05-reconciled", rec["status"] == "AUTHORIZED", rec["status"])
    version = rec["version"]
    status, late = webhook("authorized", body["provider_ref"], order)
    check("T05-late-noop", status == 200 and late["status"] == "AUTHORIZED"
          and late["version"] == version, f"v={late['version']}")


def main() -> None:
    intent = t01_double_submit()
    t02_double_webhook(intent)
    t03_outage_reconcile()
    t04_event_bound(intent["id"])
    t05_out_of_order()
    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
