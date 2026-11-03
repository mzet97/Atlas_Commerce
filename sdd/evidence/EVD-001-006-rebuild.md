# EVD-001-006 — TASK-001-009: rebuild determinístico (2026-11-03)

Status: PASS (ciclo `down -v && up --build` fim-a-fim, smoke completo).

## Ciclo (host de dev, docker via distrobox-host-exec)
1. `docker compose --profile core --profile data --profile m2 --profile m3
   down -v` → todos os volumes removidos (mongo-data, pg-data, kc-data,
   redis-data, kafka-data).
2. `up -d --build` → 26 containers Up; `/health` 200 nas 8 APIs
   (:8100 smoke, :8101 catalog, :8102 control, :8103 offers,
   :8104 inventory, :8105 payment, :8106 order, :8190 psp-fake).

## Bootstrap determinístico do Postgres (a peça que faltava)
As migrações de leitura viviam aplicadas "à mão" no volume antigo; o
rebuild quebrou (`catalog_product_search` inexistente — encontrado também
no CI). Fix estrutural: a imagem `pg` agora ASSA o bootstrap
(`base-compose/pg/Dockerfile` via `additional_contexts`):
- `initdb/01-atlas-databases.sh` cria `atlas` + `control` e aplica, na
  ordem, as migrações do control-api (control DB: `admin_actions`,
  `finance_approvals`, `scope_grants`) e de todos os serviços de leitura
  (atlas DB: `catalog_product_search`, `available_offer_view`,
  `inventory_availability_view`, `payment_intents`, `payment_webhooks`,
  `orders_view`, `order_lines`, `notification_queue`, `ai_allowlist`,
  `processed_events`). `000_create_db.sql` é pulado (DBs já criados).
- Motivo do bake: bind mounts de dirs do repo falham neste host
  (filesystem NTFS/ntfs3 + SELinux negam leitura a containers, mesmo
  root; relabel `:z` não se aplica). Baked image funciona em qualquer
  host e é o mesmo caminho do CI.

## Realm + smoke
- `setup-realm.sh` idempotente recriou realm/roles/clients/usuários
  (incl. `pam.pricing` pricing_manager + grant market=BR, novo para
  TASK-002-013).
- Seed E2E (`e2e/seed.py`) → dataset "Cafeteira M2" visível na loja,
  busca e recomendações (8/8 Playwright verde após o rebuild).

## Aprendizados registrados
- Compose valida `depends_on` contra o conjunto de perfis habilitados:
  subir `m2/m3` exige também `core`/`data` (afetava CI e local).
- Deps de Keycloak: esperar `/realms/master/.well-known` antes do seed
  (retry no grant bootstrap do script).
