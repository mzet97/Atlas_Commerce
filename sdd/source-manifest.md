# sdd/source-manifest.md — M0 Discovery/Recon

Data UTC: 2026-10-27. Estado: `NO_REPO` (não é repositório git).
Método: `find … -exec sha256sum`, `stat`, `git status`, `grep` de IDs.

| Caminho | SHA-256 (prefixo) | Bytes | Estado |
|---|---|---:|---|
| ATLAS_COMMERCE_SDD_AGENT_HANDOFF/atlas-commerce-blueprint.md | 5990fb33 | 72803 | READ |
| ATLAS_COMMERCE_SDD_AGENT_HANDOFF/PROMPT_MASTER_ATLAS_COMMERCE_SDD.md | d6e43e9b | 55073 | READ |
| atlas-commerce-discovery/README.md | 7cb79ea9 | 3245 | READ |
| docs/01-VISAO-E-ESCOPO.md | d72b8a2e | 5834 | READ |
| docs/02-DOMINIOS-E-INVARIANTES.md | fa29e30b | 7130 | READ |
| docs/03-CASOS-DE-USO-E-PROCESSOS.md | a1cb2869 | 8589 | READ |
| docs/04-MODELAGEM-DE-DADOS-CQRS.md | 42906b35 | 9265 | READ |
| docs/05-NFR-E-ESCALA.md | 2a8d63f9 | 5221 | READ |
| docs/06-ARQUITETURA-ALVO-E-ADRS.md | b1d616a6 | 10103 | READ |
| docs/07-SDD-BACKLOG-E-QUALIDADE.md | b8246179 | 6067 | READ |
| docs/08-I18N-IAM-AI.md | fd296d09 | 4657 | READ |
| diagrams/00-bounded-contexts.mmd | dc9d3ae6 | 969 | READ |
| diagrams/01-usecases-storefront.puml | 14130879 | 964 | READ |
| diagrams/02-usecases-admin.puml | d2101f52 | 1030 | READ |
| diagrams/03-er-catalog.mmd | 1f4f00d5 | 1848 | READ |
| diagrams/04-er-order-finance.mmd | 9f27464d | 2376 | READ |
| diagrams/05-er-admin.mmd | 0d2623f8 | 1335 | READ |
| diagrams/06-classes-order.mmd | 93cdb607 | 1400 | READ |
| diagrams/07-classes-inventory.mmd | 434cb39e | 1150 | READ |
| diagrams/08-state-order.mmd | 91446962 | 1062 | READ |
| diagrams/09-cqrs-projection.mmd | 7d8919e1 | 516 | READ |
| diagrams/10-sequence-checkout.mmd | ccdff2fc | 1769 | READ |
| diagrams/11-usecases-summary.mmd | 0b2e0216 | 604 | READ |

Total: 23 arquivos-fonte, 12 diagramas. Nenhum `MISSING | CORRUPT`.
Observação: blueprint consolida docs 01–08 + apêndices Mermaid/PlantUML; docs
modulares valem como referência específica em caso de divergência.
