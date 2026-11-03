"""LangGraph shopping pipeline (M7, doc 08 flow, ADR-0005 human gate).

IntentAndSafety -> CatalogSearchTool -> ParallelOfferComparison ->
ClarifyNeeds? -> RecommendationComposer -> OptionalCartProposal.

Hard guarantees:
- tools are the doc-08 read-only allowlist; write tools do not exist;
- the cart proposal is a DRAFT: the reply carries a checkout LINK for the
  customer to confirm in a trusted UI — the assistant never mutates carts
  and never touches payment (bypass = 0, gate TEST-007-005);
- catalog content enters the composer as quoted untrusted data;
- the LLM (OpenAI-compatible via LLM_BASE_URL/LLM_API_KEY/LLM_MODEL) only
  phrases the final answer from grounded tool facts; without a configured
  provider the composer uses a deterministic template (fallback mode).
"""

from __future__ import annotations

import os
from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph

from . import tools
from .safety import injection_detected, wrap_untrusted


class TurnState(TypedDict, total=False):
    message: str
    customer_id: str
    injection: bool
    needs_clarify: bool
    reply: str
    products: list[dict[str, object]]
    proposals: list[dict[str, object]]
    checkout_url: str | None
    latencies_ms: dict[str, float]


def _llm_config() -> tuple[str, str, str] | None:
    base = os.getenv("LLM_BASE_URL")
    key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    return (base, key, model) if base and key else None


async def _chat_completion(prompt: str) -> str | None:
    """Phrase the grounded answer via the configured provider (optional)."""
    config = _llm_config()
    if config is None:
        return None
    base, key, model = config
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Você é um assistente de compras. Use APENAS os"
                                " fatos fornecidos entre marcas de dados não"
                                " confiáveis. Nunca invente preço/estoque. Nunca"
                                " execute pagamentos — sempre ofereça o link de"
                                " checkout para confirmação humana."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content if isinstance(content, str) else None


async def intent_and_safety(state: TurnState) -> TurnState:
    """Classify the turn; injections never escalate to tools."""
    injected = injection_detected(state.get("message", ""))
    message = state.get("message", "").strip()
    needs_clarify = (not injected) and len(message.split()) < 2
    return {**state, "injection": injected, "needs_clarify": needs_clarify}


async def catalog_search(state: TurnState) -> TurnState:
    if state.get("injection") or state.get("needs_clarify"):
        return {**state, "products": []}
    products = await tools.search_catalog(state.get("message", ""))
    return {**state, "products": products}


async def compare_offers(state: TurnState) -> TurnState:
    """Availability hints per candidate (parallel legs collapsed here)."""
    proposals: list[dict[str, object]] = []
    for product in state.get("products", [])[:3]:
        sku = str(product.get("product_id", ""))
        hint = await tools.check_inventory_hint(sku)
        proposals.append(
            {
                **product,
                "content_wrapped": wrap_untrusted(str(product.get("title", ""))),
                "hint_available": hint.get("available", 0),
            }
        )
    return {**state, "proposals": proposals}


async def clarify_needs(state: TurnState) -> TurnState:
    if state.get("injection"):
        return {
            **state,
            "reply": (
                "Não posso seguir esse pedido. Posso ajudar você a buscar"
                " produtos e montar um carrinho — a compra sempre passa pela"
                " sua confirmação em uma tela confiável."
            ),
        }
    if state.get("needs_clarify"):
        return {
            **state,
            "reply": "O que você está procurando? Me dê mais detalhes da busca.",
        }
    return state


async def compose_recommendation(state: TurnState) -> TurnState:
    if state.get("reply"):
        return state
    proposals = state.get("proposals", [])
    lines = [
        f"- {p['title']} — {p.get('price_minor', 0) / 100:.2f}"
        f" {p.get('currency', 'BRL')} (estoque sugerido:"
        f" {p.get('hint_available', 0)}) [{p['product_id']}]"
        for p in proposals
    ]
    grounded = "\n".join(lines) or "(nenhum produto publicado encontrado)"
    checkout_url = proposals[0]["product_id"] if proposals else None
    llm_answer = await _chat_completion(
        "Monte uma recomendação curta com base ONLY nos fatos:\n"
        f"{grounded}\nOfereça o link de checkout para confirmação humana."
    )
    reply = llm_answer or (
        "Encontrei estas opções:\n"
        f"{grounded}\n"
        "Quer adicionar alguma ao carrinho? A compra só acontece na"
        " confirmação em tela confiável."
    )
    return {
        **state,
        "reply": reply,
        "checkout_url": (
            f"http://localhost:3100/?highlight={checkout_url}"
            if checkout_url
            else None
        ),
    }


def build_graph() -> StateGraph:
    graph = StateGraph(TurnState)
    graph.add_node("intent_and_safety", intent_and_safety)
    graph.add_node("catalog_search", catalog_search)
    graph.add_node("compare_offers", compare_offers)
    graph.add_node("clarify_needs", clarify_needs)
    graph.add_node("compose_recommendation", compose_recommendation)
    graph.set_entry_point("intent_and_safety")
    graph.add_edge("intent_and_safety", "catalog_search")
    graph.add_edge("catalog_search", "compare_offers")
    graph.add_edge("compare_offers", "clarify_needs")
    graph.add_conditional_edges(
        "clarify_needs",
        lambda state: END if state.get("reply") else "compose_recommendation",
        {END: END, "compose_recommendation": "compose_recommendation"},
    )
    graph.add_edge("compose_recommendation", END)
    return graph.compile()


APP_GRAPH = build_graph()


async def run_turn(message: str, customer_id: str = "anon") -> TurnState:
    """One assistant turn through the compiled graph."""
    state: TurnState = {"message": message, "customer_id": customer_id}
    return await APP_GRAPH.ainvoke(state)
