# ADR-0007 — Ordem da saga checkout (reserva ↔ pedido ↔ autorização)

Status: PROPOSED (OPEN-02/OPEN-03). Data: 2026-10-27.

## Contexto
Timeouts do PSP, reserva expirada pós-pagamento e worker morto entre commit
e ack impedem transação ACID global (docs 03–04, diagrama 10).

## Decisão (default até evidência contrária)
Reserva→Pedido(`PENDING_PAYMENT`)→Autorização, com ramos 200/402/202:
autorizado confirma; recusado libera a reserva; incerto vira
`PAYMENT_PENDING` + `ReconciliationRequired` e reconcilia depois.
Saga persistida, idempotency key fim a fim, compensações explícitas.

## Alternativa
Pedido→reserva→autorização: rejeitada por ora — pedido sem lastro de
estoque amplia a janela de oversell sob contenção (doc 02 §4).

## Falta
SPEC-003 implementa a saga e decide em definitivo com testes de falha
(UC003-T01..T05); este ADR só vira ACCEPTED após esses testes passarem.
