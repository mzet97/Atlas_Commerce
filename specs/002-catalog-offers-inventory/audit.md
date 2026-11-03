# SPEC-002 audit — inventário do incremento (2026-10-27)

Novos: `services/catalog/` (14 py + migração + Dockerfile + README),
`control-api/` (5 py + migração + Dockerfile + README),
`apps/storefront-next/` (scaffold manual mínimo + Dockerfile),
serviços `kafka`, `catalog-{api,relay,projector}`, `control-api`,
`storefront-next` no compose (perfis core+m2), banco `control`,
`setup-realm.sh` + usuário `cara.catalog`.
Originais do discovery intactos. Segredos só em `.env` local.
