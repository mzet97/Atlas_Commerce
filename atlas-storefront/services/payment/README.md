# atlas-payment — M3 payment vertical (owner of money movement)

Saga participant (ADR-0007): Reserve→Order(PENDING)→Authorize(200/402/202).
Money in minor units, integer only. No PAN/CVV: only `card_last4` transits.

## Rules

- Intent is idempotent on `idempotency_key`: same key returns the same intent.
- PSP outcomes map to intent status:
  `approved → AUTHORIZED`, `declined → DECLINED`,
  `timeout/5xx → UNKNOWN` (reconcile later, never assume).
- Webhooks are HMAC-SHA256 verified (`X-PSP-Signature` + `X-PSP-Timestamp`,
  ±5min window) and deduplicated on `(provider_ref, event)`.
- Webhook for a terminal intent is recorded but a no-op (out-of-order safe).
- `UNKNOWN` resolves ONLY via `POST /intents/{id}/reconcile`, which queries
  the PSP status endpoint — never by retrying the charge.
- `duplicate_paid_order=0`: one PSP provider_ref backs at most one
  AUTHORIZED intent; double webhooks/charges cannot double-pay.
