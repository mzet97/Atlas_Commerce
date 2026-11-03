# ADR-0005 — IA com escrita condicionada à aprovação humana

Status: PROPOSED (não implementado). Data: 2026-10-27.

## Contexto
LLM não é autoridade de preço, estoque, pagamento ou IAM (INV-009).

## Decisão
Grafo LangGraph com tools allowlisted (`search_catalog`, `propose_cart_change`
após confirmação etc.); proibidas `charge_card`, `issue_refund`, `set_price`,
`modify_stock`, grants. Prompt nunca é consentimento de cobrança; o checkout
normal revalida tudo. Fallback para busca manual com LLM fora do ar.

## Consequências
Avaliação obrigatória em M7: groundedness, tool-choice, taxa de
prompt-injection, `approval bypass = 0`, custo/latência por conversa.
