# 08 — Internacionalização, IAM e compras assistidas por IA

## Internacionalização / localização
- Idiomas iniciais `pt-BR`, `en-US`, `es-ES`; catálogos localizados por `LocaleText(product_id, locale, title, description)` e traduções por mercado. Para SEO usar rotas localizadas, `hreflang`, metadata, sitemap, canonical por região.
- Contexto de mercado (BR/US/UE), moeda de transação (BRL/USD/EUR) e locale são configurações **independentes**. Exemplo: cliente pt-BR comprando em loja US com preço USD não implica converter compulsoriamente para BRL.
- Preço cotado por `Money(amount_minor, currency, exponent)` e regras de arredondamento por moeda; PSP de pagamento usa moeda definida no quote e valores congelados. Conversão FX exibida somente como estimativa se não existir oferta/cotação autoritativa nessa moeda.
- Tributos por market/tax-region e datas de vigência; endereço geocodificado/validado; elegibilidade de envio e restrições de catálogo definidas por política, não por traduções.
- UI com formatação ICU/Intl, tradução de erro de validação, textos longos, RTL como teste de expansibilidade, acessibilidade e fuso-horário normalizado (UTC persistido, exibição local).
- Compliance: LGPD/GDPR, retenção, consentimento e integrações fiscais serão especificados com especialistas legais por país antes de ativação em produção.

## Identidade e autorização
- Perfis: customer, catalog_editor, pricing_manager, inventory_operator, fulfillment_operator, finance_analyst, support_agent, auditor, iam_admin e seller_operator (fase 3).
- Ações: `catalog:write`, `catalog:publish`, `offer:price:update`, `inventory:adjust`, `inventory:read`, `orders:read`, `payments:refund`, `audit:read`, `roles:grant`; scopes por `market`, `warehouse`, `seller` e `tenant`.
- IAM valida identidade e grants; domínio valida ownership, estado da operação, limite e abrangência. Admin UI não recebe role superuser irrestrita por padrão.
- Tokens OIDC validados por issuer/audience/signature/expiry; admin com MFA, rate limiting e policies de sessão; serviços internal gRPC autenticados por identidade de workload e autorização independente.
- Four-eyes com `requested_by != approved_by`; ações com risco financeiro exigem aprovação registrada; auditoria append-only e trilhas exportáveis.

## Assistente AI de compras: Boundaries
**Responsabilidade:** recomendações contextualizadas, comparação de SKU/ofertas, explicação de restrições, orientação de compra; não substitui engine de preço, inventário ou pagamento.

**Fluxo LangGraph candidato:**
`UserPrompt → IntentAndSafety → CatalogSearchTool → ParallelOfferComparison → ClarifyNeeds?(conditional) → RecommendationComposer → OptionalCartProposal → HumanApproval → CartMutationTool → CheckoutLink`

**Tools permitidas:** `search_catalog`, `get_product_details`, `get_offer_quote`, `check_inventory_hint`, `compare_offers`, `get_shipping_options`, `get_customer_cart` (se autorizado), `propose_cart_change` (somente após confirmação). Nenhuma tool `charge_card`, `issue_refund`, `set_price`, `modify_stock` ou credenciais administrativas.

**Confiabilidade:** retrieval grounded com IDs, preços e disponibilidade com timestamp; regras de validação por API; conteúdo de produto como untrusted input; prompt injection em reviews/descrições não define política; tool allowlist + auth scopes + schema strict; mensagens moderadas, logs redigidos, rate budgets por usuário, observabilidade de latency/tokens/cost, traces segregados, TTL/checkpoint e exclusão mediante consentimento.

**Human in the loop:** o agente fornece uma proposta de alteração com lista detalhada; o usuário confirma explicitamente; aplicação revalida no domínio Cart; no checkout o cliente revê oferta, valor e forma de pagamento e confirma numa UI confiável. O prompt nunca é evidência de consentimento de cobrança.

**Avaliação:** dataset de intenções de compra, cenários ambíguos e consultas multilíngues; retrieval precision, tool choice validity, groundedness, preference adherence, hallucination of stock/price, prompt-injection success rate, approval bypass=0, custo por conversa e p95 turn latency.

## Requisitos transversais de privacidade
- Não enviar endereço completo, pagamento, sessões, tokens nem PII para provedor de modelos sem fundamento jurídico, minimização e opt-in aplicável.
- Modelo self-hosted possível; impor quotas para que inferência de IA não consuma capacidade do checkout transacional.
- O assistente deve ter fallback para pesquisa manual caso LLM esteja indisponível.
