# EVD-001-005 — TASK-001-008: CI verde em runner (2026-11-03)

Status: PASS (runs verdes no GitHub Actions do monorepo).

## Migração
- Workflows consolidados de `atlas-*/.github/workflows/` (nunca executáveis
  num monorepo — GitHub só executa `.github/workflows/` da raiz) para 3
  workflows raiz, com `paths` filters e `concurrency` cancelamento.
- Repositório renomeado no GitHub: `Atalas_Commerce` → `Atlas_Commerce`
  (typo; redirect automático no lado GitHub; `git remote set-url` local).

## Workflows raiz
- `contracts.yaml` — parse de `contracts/**/*.yaml` + campos do envelope
  (portado do workflow original, agora paths-filtered).
- `services.yaml` — o gate real: stack compose COMPLETA
  (perfis core+data+m2+m3: mongo rs, pg, kafka, redis, keycloak, otel,
  smoke-api, 8 APIs, relays/projectors), `setup-realm.sh`, bancos
  `atlas`/`control` + todas as migrações (baked pg image, ver
  EVD-001-006), espera `/health` nas 8 APIs e então
  `uv sync` + `ruff check` + `pytest` para os 7 pacotes Python
  (psp-fake, payment, order, catalog, offers, inventory, control-api).
- `storefront.yaml` — job `build` (pnpm frozen, `tsc --noEmit`,
  `next build`) + job `e2e` (stack completa + realm + seed.py +
  Playwright chromium, 8 specs).

## Correções até o verde (todas com commit próprio)
1. `astral-sh/setup-uv` não mantém tag major flutuante → pin exato v10.3.3.
2. Compose valida `depends_on` contra perfis habilitados: habilitar
   `data` (e `core` p/ keycloak) junto de `m2`/`m3`.
3. Job e2e: aguardar Keycloak saudável ANTES do seed do realm (retry no
   bootstrap grant adicionado ao `setup-realm.sh`).
4. EXE001: `coupon_e2e.py` precisa de exec-bit no git (100755).

## Evidência de execução
- Runs (github.com/mzet97/Atlas_Commerce/actions): contracts PASS;
  services PASS (ruff + pytest 149 testes); storefront build PASS +
  e2e PASS (8 specs Playwright). Runs verdes referenciam os commits
  da série `3822316..540852f` (TASK-001-008 fechado no run posterior
  a `540852f`).
