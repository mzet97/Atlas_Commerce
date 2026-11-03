# EVD-007-002 — M7 completo: assistente LangGraph + ranking + TTL curadoria (2026-11-03)

Status: PASS (gate M7 fechado; bypass de prompt-injection = 0 provado).

## Assistente de compras (doc 08, ADR-0005)
- Serviço `assistant-api` (:8107, perfil m7): grafo LangGraph
  IntentAndSafety → CatalogSearchTool → ParallelOfferComparison →
  ClarifyNeeds? → RecommendationComposer → carrinho-PROPOSTA + link de
  checkout humano. O assistente NUNCA muta carrinho nem toca pagamento:
  a compra exige confirmação em tela confiável (REQ-AI-001).
- Tools = allowlist de leitura do doc 08 (`search_catalog`,
  `check_inventory_hint` via owners); `GET /tools` expõe o contrato e
  auditors podem verificar a ausência do conjunto proibido
  (charge_card/issue_refund/set_price/modify_stock — nem registrados).
- Conteúdo de catálogo entra no compositor QUOTED como "DADOS NÃO
  CONFIÁVEIS" (R-07); detector de injection com 7 padrões.
- LLM OpenAI-compatible configurável (LLM_BASE_URL/LLM_API_KEY/LLM_MODEL,
  .env.example); sem credencial o compositor usa fallback determinístico
  grounded — o grafo e os gates não dependem do provider.

## Evals (`assistant/evals/`, gate)
- `dataset.jsonl` (10 casos: buscas legítimas + 4 injections).
- `run.py` → **cases=10 retrieval_precision=1.00 injection_attempts=4
  injection_bypass=0 turn_p95_ms=169 — EVAL PASS** (gates: bypass=0 e
  precision ≥ 0.8). Gate TEST-007-005 (traceability) fechado.

## Ranking/explicabilidade/TTL de curadoria
- `ai_allowlist` ganha `weight` + `expires_at` (migration 005), curados
  via Control `ai:allow` (categoria catalog_editor); expirados deixam de
  aparecer sem reescrita (TTL por linha).
- Storefront `/recommendations`: ranking determinístico (peso do curador
  + disponibilidade − penalidade de já-comprado), explicação legível por
  item ("curadoria (peso 1.0) · estoque disponível") — sem ranking
  cross-owner (pedidos entram via projeção no mesmo read model).

## Ferramenta de busca para o grafo
- Catalog owner `GET /products?q=` (read model, PUBLISHED + oferta ativa
  + hint de estoque) — a tool `search_catalog` do doc 08.

## Evidência executada
- Suite assistant **5 passed** (registry sem write-tools, detector,
  downgrade de turn injection, proposta com conteúdo quoted + link).
- Live: `POST /assistant/chat` "quero uma cafeteira" → resposta
  grounded com Cafeteira M2 real (129.90 BRL, estoque 7) + link.
- Regressão: catalog 14, control 31 — ruff limpo.
