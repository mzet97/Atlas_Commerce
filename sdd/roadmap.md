# sdd/roadmap.md — milestones e dependências (M0, fonte: prompt §12 + doc 07)

```
M0 (SPEC-000) — Discovery/Recon, sem código ........... ESTE CICLO
M1 (SPEC-001) — Platform Foundation ................... após gate M0
M2 (SPEC-002) — Catalog/Offers/Inventory slice ........ após M1
M3 (SPEC-003) — Cart/Quote/Checkout/Order/PSP fake .... após M2
M4 (SPEC-004) — Admin hardening ....................... após M2, parcial // com M3
M5 (SPEC-005) — Storefront UX/busca/SEO/i18n .......... após M2, parcial // com M3
M6 (SPEC-006) — Fulfillment/Returns/Notifications ..... após M3
M7 (SPEC-007) — AI Shopping ........................... após M2/M3
M8 (SPEC-008) — Kubernetes on-prem .................... PARCIAL (EVD-008-002/003: deploy surface completa + cluster k8s1)
M9 (SPEC-009) — Benchmark L0–L4 ....................... PARCIAL (L0+L1 medidos, teto bracketado, L2/L3 bloqueados por topologia)
M10 (SPEC-010) — Marketplace 3P ....................... ENTREGUE (EVD-010-001)
M11 (SPEC-011) — Portfólio internacional .............. transversal, ao final
```

Gate M0: fontes rastreáveis, ownership único, 5 cenários UC003-T01..T05
auditáveis, ADRs abertas explicitadas, SPEC-001/002 propostas.
Repos `atlas-storefront`, `atlas-control`, `atlas-platform-contracts` só
após gate M0 (§17 do prompt).
