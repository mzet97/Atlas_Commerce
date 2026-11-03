# EVD-001-004 — M1 increment-3: realm OIDC + CI mínima (2026-10-27)

Status: PASS parcial (auth real provada; CI de runner segue OPEN sem remote).

## Realm `atlas` (script `setup-realm.sh`, idempotente: rerun → 409+204)
- `POST /admin/realms` → 201; 10 roles → 201 (`customer`,
  `catalog_editor`, `pricing_manager`, `inventory_operator`,
  `fulfillment_operator`, `finance_analyst`, `support_agent`, `auditor`,
  `iam_admin`, `seller_operator`); 2 clients → 201 (`atlas-storefront`
  público PKCE+direct-grant p/ smoke, `atlas-control` confidencial);
  2 users → 201 + role-maps → 204.
- Diagnóstico registrado: direct grant falhava com
  `resolve_required_actions` ("Account is not fully set up") porque o
  user-profile declarativo exige first/last name no 1º login; script agora
  cria usuários com email+nome (fix no próprio script).

## Smoke OIDC (tokens reais, segredos redigidos)
- `alice.customer` → JWT iss `http://localhost:8180/realms/atlas`,
  roles `[customer, default-roles-atlas, offline_access, uma_authorization]`.
- `boss.admin` → roles incluem `iam_admin`.
- Introspecção via `atlas-control`+secret → `active=True`,
  `username=alice.customer`, `azp=atlas-storefront`. Assinatura válida
  verificada server-side; sem PAN/senha em evidência (payloads decodificados
  só p/ username/roles/iss).

## CI mínima (real, sem ornamento)
- 3 workflows: contracts (parse YAML + envelope INV-010 + guard `.env`),
  storefront-guard e control-guard (hygiene + `git diff --check`).
- `actionlint 1.7.7` nativo nos 3 arquivos → PASS (docker-mount evitado:
  `/tmp` do container ≠ `/tmp` do host; binário direto usado).
- Check python do workflow contracts executado localmente → parsed + fields OK.
- "CI verde em runner" segue OPEN: repos sem remote (sem push autorizado).

## Falta para o gate M1
CI em runner (requer remote), rebuild determinístico documentado fim-a-fim,
smoke admin via Authorization Code + PKCE (browser).
