# SPEC-002 tasks

| ID | Objetivo | Aceite | Estado |
|---|---|---|---|
| TASK-002-001 | Catalog owner + outbox | serviço no ar | PASS |
| TASK-002-002 | Relay + projector + migração | lag 0, outbox drenado | PASS |
| TASK-002-003 | Suite catalog (14 testes) | pytest verde + ruff limpo | PASS |
| TASK-002-004 | Concorrência mesma chave | 20 escritores → 1 produto | PASS |
| TASK-002-005 | Entrega duplicada idempotente | 2x evento → 1 linha + 1 inbox | PASS |
| TASK-002-006 | Control-api + audit próprio | 4 testes verdes | PASS |
| TASK-002-007 | 403 customer + audit denied | 403 + linha `denied` | PASS |
| TASK-002-008 | Storefront lê projeção | título publicado em `:3100` | PASS |
| TASK-002-009 | Estado PUBLISHING na UI | badge via `?v=` | PASS |
| TASK-002-010 | 403 por market/warehouse | ABAC + testes + audit | PASS |
| TASK-002-011 | Ofertas + inventário slice | owners Offer/Inventory | PASS |
| TASK-002-012 | E2E Playwright da fatia | admin→loja em Chromium (2 passed) | PASS |
| TASK-002-013 | Cupons/impostos/multi-armazém | regras por região | TODO (M2-next) |
| TASK-002-014 | E2E checkout completo | carrinho→pagamento | PASS (M3: `checkout_e2e.py` 12 checks, EVD-003-002) |
