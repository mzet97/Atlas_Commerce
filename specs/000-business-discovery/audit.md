# SPEC-000 audit — inventário resumido (detalhe em `sdd/source-manifest.md`)

- 23 arquivos-fonte: blueprint (72803 B, `5990fb33`), prompt master
  (55073 B, `d6e43e9b`), README discovery, docs 01–08, 12 diagramas.
- Todos `READ`; nenhum `MISSING | CORRUPT | CONFLICT` estrutural.
- `git status`: `NO_REPO` — workspace sem git, sem branch, sem diff.
- UC-001..UC-011 presentes no blueprint e no doc 03 (grep confirmado).
- INV-001..INV-012 presentes no blueprint e no doc 02 (grep confirmado).
- Divergências registradas como OPEN-01..OPEN-06 em
  `sdd/decisions-open.md`; nenhuma resolvida silenciosamente.
- Duplicação blueprint × docs: blueprint consolida; docs modulares vencem
  como referência específica (precedência do prompt §1.1).
