# EVD-009-001 — M9 increment-1: sonda de carga L0 (medido, sem inventar)

Status: PASS (números observados da sonda `/tmp/bench_l0.py`, stdlib).

## Método (ao vivo, stack compose)
- Leituras: 50 RPS × 60s (`n=3000`) em `GET :8101/products/{id}`.
- Escritas: 1 checkout/s × 60s (`n=60`, 4 workers) — cart→quote→checkout
  completos (saga reserve→authorize→confirm, PSP fake aprova).
- Oferta dedicada criada p/ a sonda (preço 100, 100 un. W1).

## Resultado (observado)
- `catalog-reads: n=3000 errors=0` — p50=3ms p95=4ms max=68ms.
- `checkouts: n=60 errors=0` — p50=111ms p95=143ms max=155ms.
- Teto da carta (`< 1.5s` p/ aceite PENDING): **folgado em 10x no L0**.

## Decisões registradas
- Sonda é probe descartável (`/tmp`, fora do deliverable); virar suite
  recorrente fica p/ M9-2 com níveis L1+ e SLOs propostos (não afirmados).
- Latência de checkout inclui 3 hops internos (inventory→payment→confirm);
  p95 143ms sugere headroom, não garantia, p/ L1.

## Fora do escopo (OPEN, sem ornamento)
- L1-L4 (`NOT_MEASURED`), soak, chaos, remotes/commits.
