# EVD-001-007 — TASK-001-010: Authorization Code + PKCE no browser (2026-11-03)

Status: PASS (login real via redirect Keycloak, Playwright verde).

## Implementação (storefront-next, zero dependências novas)
- `lib/auth.ts` — PKCE S256 puro (verifier 48B → SHA-256 base64url),
  state + verifier em cookies httpOnly de curta vida (600s), troca de
  código no token endpoint, URL pública (browser) ≠ URL interna (server)
  para funcionar atrás do compose (`KC_PUBLIC_URL`/`KC_INTERNAL_URL`).
- Rotas: `/login` (307 → authorize com challenge S256), `/callback`
  (valida state cookie ↔ query, troca code, seta `atlas_session`),
  `/logout` (limpa sessão local).
- Header do layout mostra o usuário logado: `currentUser()` verifica o
  JWT da sessão (RS256 + exp) contra o JWKS do realm (cache 1h) — nunca
  confia em claim sem verificação; cache de 60s por token.
- Origem derivada do header Host (não de `request.url`): atrás do
  mapeamento 3100→3000 do compose o `redirect_uri` saía como :3000 e o
  fluxo quebrava.

## Realm
- `atlas-storefront` redirectUris: `http://localhost:3000/*` e
  `http://localhost:3100/*` (standard flow, PKCE, público).

## Evidência (Playwright, chromium, stack viva)
`pnpm e2e` → **8 passed**:
- login via redirect → formulário Keycloak → credenciais
  `alice.customer` → volta para `/` com `alice.customer` no header;
- `/callback?code=x&state=tampered` sem cookies do fluxo → `?auth_error=1`,
  sem sessão;
- logout → sessão limpa (link "entrar" de volta).
Suite completa: slice (2), search (2), recommendations (1), auth (3).

## Correções na maré (registradas)
- Userinfo roundtrip substituído por verificação JWKS local: token sem
  escopo `openid` recebe 403 do userinfo e derrubava o header; a sessão
  só nasce de exchange bem-sucedido, e a assinatura é verificada
  localmente — mesmo rigor, sem dependência do escopo.
