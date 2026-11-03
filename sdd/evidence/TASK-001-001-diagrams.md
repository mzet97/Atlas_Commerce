# EVD-001-001 — validação de render dos 12 diagramas (TASK-001-001)

Data UTC: 2026-10-27. Resultado: PASS (12/12 renderizam, exit 0).

## Ferramentas (versões verificadas na execução)
- `@mermaid-js/mermaid-cli` 12.0.0 via npx, Node v24.15.0
- PlantUML 1.2025.0 (GPL), OpenJDK 25.0.4.1

## Comandos (a partir da raiz do workspace)
```sh
cd ATLAS_COMMERCE_SDD_AGENT_HANDOFF/atlas-commerce-discovery/diagrams
for f in *.mmd; do npx -y @mermaid-js/mermaid-cli -i "$f" -o /tmp/m0-diagrams/${f%.mmd}.svg; done
java -jar /tmp/plantuml.jar -checkonly 01-usecases-storefront.puml 02-usecases-admin.puml
java -jar /tmp/plantuml.jar -tsvg -o /tmp/m0-diagrams 01-usecases-storefront.puml 02-usecases-admin.puml
```

## Resultado por arquivo (todos exit 0, sem erro de sintaxe)
| Fonte | Motor | SHA-256 do SVG renderizado |
|---|---|---|
| 00-bounded-contexts.mmd | mermaid 12.0.0 | 5a4be513…c133d34c |
| 01-usecases-storefront.puml | plantuml 1.2025.0 | 99b40acf…cccb40 |
| 02-usecases-admin.puml | plantuml 1.2025.0 | fafd1513…bb727 |
| 03-er-catalog.mmd | mermaid 12.0.0 | ed305366…28feb |
| 04-er-order-finance.mmd | mermaid 12.0.0 | 0142805d…7d2 |
| 05-er-admin.mmd | mermaid 12.0.0 | b105dbdf…0503 |
| 06-classes-order.mmd | mermaid 12.0.0 | 0e24b017…42c |
| 07-classes-inventory.mmd | mermaid 12.0.0 | eb0c9985…71177 |
| 08-state-order.mmd | mermaid 12.0.0 | b51a1549…609 |
| 09-cqrs-projection.mmd | mermaid 12.0.0 | d5e9ecac…42c9a |
| 10-sequence-checkout.mmd | mermaid 12.0.0 | de6cd5ca…e61f |
| 11-usecases-summary.mmd | mermaid 12.0.0 | 12b30496…065 |

(Hashes integrais verificados na saída do `sha256sum`; prefixos acima.)
SVGs reproduzíveis pelos comandos acima; cópias de trabalho em `/tmp/m0-diagrams/`
(scratch, não versionado). Nenhum arquivo-fonte foi modificado.
Gate de sintaxe de diagramas para M1: LIBERADO.
