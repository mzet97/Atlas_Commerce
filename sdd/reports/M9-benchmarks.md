# Report M9 — Benchmarks (2026-10-28) — PARCIAL (increment-1, L0 medido)

Medido (sonda `/tmp/bench_l0.py`, stack compose ao vivo): leituras
`n=3000 errors=0` p50=3ms p95=4ms max=68ms @50RPS/60s; checkouts
`n=60 errors=0` p50=111ms p95=143ms max=155ms @1/s (saga completa).
Teto da carta (<1.5s p/ aceite): folgado 10x no L0.
Evidência: EVD-009-001-l0-bench. Gate M9 OPEN: L1-L4, soak, chaos.
