# SPEC-000 spec — problema, escopo e requisitos

## Problema
E-commerce internacional 1P (plataforma vendedora) com jornadas de compra e
operação separadas, sem pedidos pagos sem rastreabilidade nem reservas
incoerentes (doc 01, blueprint §01).

## Atores
Visitante, cliente, atendente, gestor catálogo/preços, operador
estoque/fulfillment, financeiro, auditor, superadmin IAM, vendedor parceiro
(fase 2), PSP/transportadora (externos), agente AI (doc 01 §3).

## Requisitos (→ `sdd/requirements.md`)
REQ-CAT-001/002, REQ-OFF-001, REQ-INV-001/002, REQ-CART-001, REQ-ORD-001,
REQ-PAY-001, REQ-ADM-001/002, REQ-I18N-001, REQ-AI-001, REQ-CQRS-001,
REQ-OBS-001. Invariantes INV-001..INV-012 (doc 02) + mapeamento OPEN-01.

## Fluxos P0 auditados
UC-003 checkout (8 passos + 5 Gherkin T01..T05), UC-005 publicação produto,
UC-006 ajuste inventário, UC-002 cotação, UC-010 acesso, UC-009 assistente.

## Fora de escopo desta spec
Código, containers, K8s, benchmarks, PSP real, 3P, produtos digitais,
conformidade certificada (LGPD/GDPR/PCI como design, não atestado).

## Definition of Done (M0)
Fontes rastreáveis, ownership único, 5 cenários críticos auditáveis,
ADRs abertas explicitadas, SPEC-001/002 propostas. Sem afirmação de
capacidade, teste ou cobertura não executados.
