# Report M1 — Platform Foundation (2026-10-27) — PARCIAL

Entregue: 3 repos (`git init`, sem commits); compose core
(mongo rs0, pg:17, keycloak:26.2.5, redis:8.0.1, otel-lgtm, smoke-api);
realm `atlas` + 3 users; JWTs reais + introspecção; 3 workflows com
actionlint PASS. Evidências: EVD-001-002/003/004 + TASK-001-001.
Gate M1 OPEN: CI em runner, rebuild documentado, PKCE no browser.
Diagnósticos úteis: `--replSet`, init inline, OTLP na 4318, first/last
name no bootstrap, `/tmp` do container ≠ `/tmp` do host.
