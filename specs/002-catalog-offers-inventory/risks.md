# SPEC-002 risks

| # | Risco | Estado |
|---|---|---|
| R-M2-01 | `control-api` em `network_mode: host` (acoplado ao localhost) | Aceito p/ dev; rever no chart M8 |
| R-M2-02 | Projeção sem estado PUBLISHING confunde operador em lag alto | OPEN — TASK-002-009 |
| R-M2-03 | Role plana (`catalog_editor`) sem scope market/warehouse | OPEN — TASK-002-010; hoje qualquer mercado |
| R-M2-04 | `pg`/`redis` sem TLS e sem backup | Aceito p/ dev; HA+backup em M8, RPO/RTO a medir em M9 |
| R-M2-05 | Ofertas/inventário ainda inexistentes; preço/estoque mockados por ausência | OPEN — TASK-002-011 (M2-next) / M3 |
