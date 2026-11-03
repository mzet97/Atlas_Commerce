# atlas-psp-fake — deterministic PSP simulator (DEV/TEST ONLY)

Replaces a real acquirer in M3 slices. Deterministic scenarios, no randomness:

| Trigger | Behavior |
|---|---|
| card ending `0002` | business decline (`approved=false, code=DECLINED`), HTTP 200 |
| `amount_minor == 666` | TIMEOUT: sleeps 12s (client timeout is 10s) then approves |
| `amount_minor == 999` | UNKNOWN: HTTP 500, outcome only via `GET /charges/{ref}` (=approved) |
| same idempotency key | DUPLICATE: returns the ORIGINAL response untouched |
| default | approved with `provider_ref` |
| `X-Chaos: duplicate` | webhook delivered twice (dedup drill) |
| `X-Chaos: delay:3` | webhook delayed 3s (out-of-order drill) |

Webhooks are HMAC-SHA256 signed (`X-PSP-Signature`, `X-PSP-Timestamp`,
±5min window) and POSTed to `PSP_CALLBACK_URL`. No PAN is stored: only the
card's last 4 digits are kept in memory for scenario routing.
