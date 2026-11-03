# SPEC-000 evidence (M0 — comandos reais, 2026-10-27 UTC)

## EVD-000-001 inventário
- `find ATLAS_COMMERCE_SDD_AGENT_HANDOFF -type f | sort` → 23 arquivos.
- `find … -exec sha256sum` → hashes em `sdd/source-manifest.md`. PASS.
- `git status` → `fatal: not a git repository…` → `NO_REPO`. PASS (fato).
- `grep -o INV-… / UC-…` → INV-001..012 e UC-001..UC-011 nos dois lados. PASS.

## EVD-000-002 leitura integral
- blueprint linhas 1–150 + 151–1171 lidas; prompt 600/600; docs 01–08
  integrais; 06 restante 80–92 lido. Resultado: PASS (leitura, não execução).

## EVD-000-003 diagramas
- 12 arquivos listados (`ls diagrams/`), leitura de conteúdo M0.
- Render Mermaid/PlantUML NÃO executado → pendente TASK-001-001 (M1).

## Divergências
- Nenhum teste/benchmark executado neste M0: `NOT_MEASURED` (honesto).
- Nenhum arquivo de origem modificado (só leitura + `sdd/` e `specs/` novos).
