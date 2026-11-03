# Report M3 — Checkout/PSP (2026-10-28) — COMPLETO (increment-1 e 2)

Entregue: PSP fake determinístico (6 testes) + Payment owner — intents
idempotentes, webhook HMAC com dedup atômica, reconciliação só via verdade
do PSP (21 testes); Order owner — Cart/Quote(TTL)/saga checkout
Reserve→PENDING→Authorize→CONFIRMED com compensações (21 testes);
compose profile `m3` (payment :8105, order :8106, psp-fake :8190);
drills `t01_t05.py` e `checkout_e2e.py` ALL PASS ao vivo;
`duplicate_paid_order=0` provado no owner e na projeção. Corrida
charge×webhook encontrada e corrigida (convergência p/ o webhook).
Evidências: EVD-003-001/002. Stack: 26 containers.
