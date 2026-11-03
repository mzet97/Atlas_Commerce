"""Payment API tests: intents, signed webhooks, reconciliation (PSP faked)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import pytest
from conftest import unique
from httpx import AsyncClient

from atlas_payment import application
from atlas_payment.api import app as payment_app

SECRET = os.environ["PSP_WEBHOOK_SECRET"]


def _signed(raw: bytes) -> dict[str, str]:
    stamp = str(int(time.time()))
    digest = hmac.new(
        SECRET.encode(), f"{stamp}.".encode() + raw, hashlib.sha256
    ).hexdigest()
    return {"X-PSP-Signature": digest, "X-PSP-Timestamp": stamp}


async def _post_intent(
    http: AsyncClient,
    amount: int = 1999,
    card: str = "4242",
    key: str | None = None,
    order: str | None = None,
) -> dict[str, object]:
    response = await http.post(
        "/intents",
        json={
            "order_id": order or unique("order"),
            "customer_id": unique("cust"),
            "amount_minor": amount,
            "currency": "BRL",
            "card_last4": card,
            "idempotency_key": key or unique("idem"),
            "correlation_id": unique("corr"),
        },
    )
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


def _fake_charge(result: dict[str, object] | Exception):
    async def _charge(*args: object, **kwargs: object) -> dict[str, object]:
        if isinstance(result, Exception):
            raise result
        return result

    return _charge


class TestCreate:
    async def test_approved_intent(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given PSP approves / When intent created / Then AUTHORIZED."""
        ref = unique("psp")
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"approved": True, "provider_ref": ref,
                          "decline_code": None}),
        )
        intent = await _post_intent(api)
        assert (intent["status"], intent["provider_ref"]) == ("AUTHORIZED", ref)

    async def test_declined_intent(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given card 0002 / When intent created / Then DECLINED, no auth."""
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"approved": False, "provider_ref": "psp-d1",
                          "decline_code": "DECLINED"}),
        )
        intent = await _post_intent(api, card="10002")
        assert (intent["status"], intent["decline_code"]) == ("DECLINED", "DECLINED")

    async def test_timeout_is_unknown(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given PSP timeout / When intent created / Then UNKNOWN, no ref."""
        monkeypatch.setattr(
            application, "psp_charge", _fake_charge(application.PSPError("timeout"))
        )
        intent = await _post_intent(api)
        assert intent["status"] == "UNKNOWN"
        assert intent["provider_ref"] is None

    async def test_unknown_500_keeps_ref(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given PSP 500 with ref / When created / Then UNKNOWN with ref."""
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"unknown": True, "provider_ref": "psp-u1"}),
        )
        intent = await _post_intent(api)
        assert (intent["status"], intent["provider_ref"]) == ("UNKNOWN", "psp-u1")

    async def test_same_key_replays_without_recharge(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given created / When same key again / Then same intent, 1 charge."""
        calls: list[str] = []

        async def _charge(*args: object, **kwargs: object) -> dict[str, object]:
            calls.append("x")
            return {"approved": True, "provider_ref": unique("psp"),
                    "decline_code": None}

        monkeypatch.setattr(application, "psp_charge", _charge)
        key = unique("idem")
        first = await _post_intent(api, key=key)
        second = await _post_intent(api, key=key, order=unique("order"))
        assert first["id"] == second["id"]  # winner stands, new order ignored
        assert len(calls) == 1  # PSP charged exactly once


class TestWebhook:
    async def _timeout_intent(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, object]:
        monkeypatch.setattr(
            application, "psp_charge", _fake_charge(application.PSPError("timeout"))
        )
        return await _post_intent(api)

    async def test_bad_signature_rejected(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given forged webhook / When delivered / Then 401, state kept."""
        intent = await self._timeout_intent(api, monkeypatch)
        raw = json.dumps({"event": "authorized", "provider_ref": "psp-x",
                          "order_id": intent["order_id"]}).encode()
        response = await api.post(
            "/webhooks/psp", content=raw,
            headers={"X-PSP-Signature": "forged", "X-PSP-Timestamp": "0"},
        )
        assert response.status_code == 401
        current = await api.get(f"/intents/{intent['id']}")
        assert current.json()["status"] == "UNKNOWN"

    async def test_authorized_webhook_moves_unknown(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given UNKNOWN / When authorized webhook / Then AUTHORIZED."""
        intent = await self._timeout_intent(api, monkeypatch)
        raw = json.dumps({"event": "authorized", "provider_ref": "psp-w1",
                          "order_id": intent["order_id"]}).encode()
        response = await api.post("/webhooks/psp", content=raw, headers=_signed(raw))
        assert response.status_code == 200
        assert response.json()["status"] == "AUTHORIZED"

    async def test_double_webhook_is_deduped(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given webhook applied / When same webhook again / Then 1 record."""
        intent = await self._timeout_intent(api, monkeypatch)
        raw = json.dumps({"event": "authorized", "provider_ref": "psp-w2",
                          "order_id": intent["order_id"]}).encode()
        headers = _signed(raw)
        first = await api.post("/webhooks/psp", content=raw, headers=headers)
        second = await api.post("/webhooks/psp", content=raw, headers=headers)
        assert first.json()["status"] == second.json()["status"] == "AUTHORIZED"
        repo = payment_app.state.repo  # type: ignore[attr-defined]
        count = await repo.database.webhooks.count_documents(
            {"provider_ref": "psp-w2", "event": "authorized"})
        assert count == 1

    async def test_webhook_on_terminal_is_noop(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given AUTHORIZED / When late declined webhook / Then kept AUTHORIZED."""
        ref = unique("psp")
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"approved": True, "provider_ref": ref,
                          "decline_code": None}),
        )
        intent = await _post_intent(api)
        raw = json.dumps({"event": "declined", "provider_ref": ref,
                          "order_id": intent["order_id"]}).encode()
        response = await api.post("/webhooks/psp", content=raw, headers=_signed(raw))
        assert response.json()["status"] == "AUTHORIZED"


class TestReconcile:
    async def test_reconcile_unknown_via_status(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given UNKNOWN with ref / When reconciled / Then PSP truth wins."""
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"unknown": True, "provider_ref": "psp-u2"}),
        )

        async def _status(ref: str) -> str:
            assert ref == "psp-u2"
            return "declined"

        monkeypatch.setattr(application, "psp_status", _status)
        intent = await _post_intent(api)
        response = await api.post(
            f"/intents/{intent['id']}/reconcile",
            json={"correlation_id": unique("corr")},
        )
        assert response.json()["status"] == "DECLINED"

    async def test_reconcile_terminal_is_noop(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given AUTHORIZED / When reconciled / Then untouched, no PSP call."""
        monkeypatch.setattr(
            application, "psp_charge",
            _fake_charge({"approved": True, "provider_ref": unique("psp"),
                          "decline_code": None}),
        )
        intent = await _post_intent(api)
        response = await api.post(
            f"/intents/{intent['id']}/reconcile",
            json={"correlation_id": unique("corr")},
        )
        assert (response.json()["status"], response.json()["version"]) == (
            "AUTHORIZED", intent["version"])

    async def test_get_missing_is_404(self, api: AsyncClient) -> None:
        """Given unknown id / When fetched / Then 404."""
        response = await api.get("/intents/pi-nope")
        assert response.status_code == 404
