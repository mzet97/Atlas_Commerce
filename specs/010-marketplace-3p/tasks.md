| ID | Objetivo | Aceite | Estado |
|---|---|---|---|
| TASK-010-001 | Registro de sellers | iam_admin cria; lista pública p/ operadores | PASS |
| TASK-010-002 | Tenancy no publish | paul.seller publica seller-acme 201; seller-outro 403 auditado | PASS |
| TASK-010-003 | Oferta concorrente | 2 sellers ativos no mesmo SKU; buybox = menor preço | PASS |
| TASK-010-004 | Split settlement | bruto/comissão/líquido corretos + audit | PASS |
| TASK-010-005 | Velocity antifraude | 6ª intent em 60s DECLINED FRAUD_VELOCITY | PASS |
| TASK-010-006 | Regressão 1P | sweep completo verde | PASS |
