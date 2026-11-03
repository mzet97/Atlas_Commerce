# 03 — Casos de uso, contratos de negócio e processos

Os diagramas UML PlantUML estão em `../diagrams/01-usecases-storefront.puml` e `02-usecases-admin.puml`. Todos os casos prioritários abaixo são independentes da tecnologia.

## UC-001 — Pesquisar e comparar produtos
**Ator primário:** visitante/cliente. **Gatilho:** termo de busca, filtro, navegação por categoria ou pergunta à IA.

**Pré-condições:** produtos publicados e com oferta elegível para o mercado. **Fluxo:** selecionar mercado/locale → pesquisar com paginação → filtrar → abrir detalhe → comparar variações e ofertas. **Alternativos:** sem resultados → sugestões; preço indisponível → detalhar indisponibilidade; projeção desatualizada → resolver a oferta ao entrar no checkout.

**Pós-condições:** resultados exibidos; impressões e buscas observáveis sem PII. **Regra:** produtos não publicados não aparecem, mesmo se projeção antiga retorná-los; ACL aplicada onde pertinente.

## UC-002 — Preparar carrinho e obter cotação
**Ator:** cliente/visitante. **Pré-condição:** SKU comercializável. **Fluxo:** adicionar SKU → validar quantidade → escolher entrega/CEP → consultar ofertas, impostos e opções de frete → gerar `PriceQuote` versionada com TTL → apresentar total e detalhamento.

**Alternativos:** promo vencida, mudança de preço, oferta expirada, item restrito/região proibida, falha de transportadora, estoque insuficiente; apresentar re-cotação ou suspender checkout. **Pós-condição:** cotação assinada e expirada explicitamente; nenhuma cobrança executada.

## UC-003 — Finalizar checkout (P0)
**Ator:** cliente autenticado. **Gatilho:** confirmar pedido após revisar cotação.

**Pré-condições:** sessão válida, consentimento/termos quando necessários, quote vigente, endereço elegível, pagamento tokenizado e meios externos disponíveis.

**Fluxo principal:**
1. Receber `SubmitCheckout` com `idempotency_key`, quote_id e customer_id autenticado.
2. Validar quote, limites, elegibilidade e prevenção básica de fraude.
3. Criar checkout único e reservar inventário no serviço proprietário com comando idempotente.
4. Criar pedido em `PENDING_PAYMENT` com snapshot comercial e referência das reservas.
5. Criar/confirmar `PaymentIntent` usando idempotência no PSP.
6. Receber e verificar resultado final (síncrono autenticado ou webhook validado); tratar estado intermediário.
7. Confirmar pedido e reservas, publicar evento durável de confirmação.
8. Informar número de pedido sem esperar e-mail ou etapas logísticas.

**Fluxos alternativos:** falta de estoque → não criar pedido confirmável; PSP timeout → estado `PAYMENT_PENDING` e reconciliação; recusa → `PAYMENT_FAILED` e liberar reserva conforme política; reserva expirou com pagamento aprovado → iniciar compensação/refund + incidente; evento duplicado → deduplicar; caída do worker entre DB/evento → outbox/CDC retoma.

**Pós-condição:** a operação retorna status inequívoco (`CONFIRMED`, `PENDING`, `REJECTED`) e referencia para consulta; não afirma compra concluída no timeout.

### Cenários Given/When/Then
- **UC003-T01:** Given saldo=1, When dois checkouts reservam simultaneamente, Then exatamente um obtém reserva e o saldo não fica negativo.
- **UC003-T02:** Given pagamento pendente, When cliente reenvia mesmo idempotency_key, Then é retornada mesma operação sem segunda cobrança.
- **UC003-T03:** Given pagamento aprovado e serviço de pedidos indisponível, When worker retoma, Then saga reconcilia para confirmação ou compensação sem perda silenciosa.
- **UC003-T04:** Given projeção PostgreSQL atrasada, When checkout inicia, Then disponibilidade final é revalidada no Inventory autoritativo.
- **UC003-T05:** Given webhook duplicado e fora de ordem, When processado, Then transições inválidas são rejeitadas e nenhum reembolso/captura é duplicado.

## UC-004 — Rastrear, cancelar ou devolver pedido
**Ator:** cliente; operador de atendimento. **Fluxo:** consultar timeline → solicitar cancelamento dentro das regras → verificar estágio logístico e captura → efetuar reversão/autorização → informar status e prazo. Devolução após envio gera RMA, aprovação e solicitação de reembolso distinta de logística reversa. **Alternativos:** item entregue, prazo expirado, estorno parcial, pedido multi-remessa.

## UC-005 — Administrar publicação de produto (P0)
**Ator:** gestor de catálogo. **Fluxo:** criar rascunho → inserir traduções, atributos, mídia e SKU → validar dados obrigatórios por categoria/mercado → submeter aprovação → operador autorizado aprova → Control registra auditoria e envia comando ao Catalog → catálogo publica `ProductPublished` → projeções de pesquisa atualizam.

**Alternativos:** reprovação com justificativa, mídia inválida, produto duplicado, versão concorrente desatualizada, indisponibilidade dos serviços. **Regra:** publicar produto não implica criar Oferta automaticamente.

## UC-006 — Ajustar inventário (P0)
**Ator:** operador de estoque, supervisor. **Fluxo:** selecionar SKU e depósito → informar tipo e motivo do movimento → validar autorização de escopo → pedir aprovação se acima de limite → `AdjustStock` com idempotência → serviço Inventory registra movement e atualiza posição atomicamente → eventos e leituras atualizam. **Alternativos:** reserva ativa impede reduzir abaixo do disponível; divergência física exige reconciliação e incidente.

## UC-007 — Definir oferta/preço/promoção
**Ator:** gestor comercial. **Fluxo:** escolher SKU, vendedor, canal, moeda/mercado e período → simular descontos/pricing → exigir aprovação conforme limite → publicar offer → evento atualiza vitrine e cache. **Regra:** nenhuma alteração retroativa altera um Order já confirmado.

## UC-008 — Monitorar operação e reprocessar falha
**Ator:** SRE / operador. **Fluxo:** abrir painéis de checkout/payment/reservation/Kafka/RabbitMQ → pesquisar trace/correlation_id → identificar mensagem em DLQ → abrir incidente → reprocessar com autorização e dry-run → confirmar idempotência e acompanhar impacto. **Regra:** reprocesso não pode gerar compra/pagamento duplicado.

## UC-009 — Assistente de compras
**Ator:** cliente. **Fluxo:** interpretar preferências → buscar dados por ferramentas autorizadas → comparar itens e justificar opções → solicitar explicitamente consentimento para alterar carrinho → enviar proposta à API de Cart → abrir checkout convencional. **Alternativos:** catálogo vazio, suspeita de prompt injection, resposta sem confiança, tool lenta, usuário não autoriza. **Regra:** não invocar `capture_payment` nem mutação não permitida.

## UC-010 — Gestão de acesso
**Ator:** administrador IAM. **Fluxo:** registrar ou vincular identidade → conceder papel e escopo (`warehouse`, `market`, `seller`) → exigir MFA quando aplicável → publicar alteração da política → auditoria. **Alternativos:** conflito de atribuições e acesso a recurso fora do escopo retornam 403.

## UC-011 — Financeiro e conciliação
**Ator:** analista financeiro. **Fluxo:** importar lotes/transações externas → correlacionar PaymentIntent/Capture/Refund → registrar diferença → abrir caso de conciliação → gerar evidências e relatório. **Regra:** status financeiro não é inferido de ordem temporal de mensagens; provider transaction ID e reconciliação decidem.

## Catálogo de testes de aceitação por domínio
| Requisito | Dado | Quando | Então |
|---|---|---|---|
| CAT-01 | SKU sem tradução es-ES | cliente acessa espanhol | fallback explícito, sem quebrar checkout |
| PRC-02 | cupom uso único já consumido | segunda compra tenta aplicar | rejeita aplicação duplicada |
| INV-03 | estoque disponível 0 | adicionar produto ao carrinho | carrinho pode mostrar indisponível, mas não promete checkout |
| ORD-04 | pagamento duplicado via webhook | reprocessa | apenas uma transição válida |
| ADM-05 | gestor de catálogo sem permissão de estoque | chama ajuste via API | HTTP 403 e auditoria de tentativa |
| AI-06 | prompt malicioso pede envio sem confirmação | agente executa | nenhuma mutação de pedido/pagamento |
| OPS-07 | RabbitMQ/Kafka temporariamente indisponível | grava comando | o comando não afirma publicação; outbox/recovery garante retomada |
| COM-08 | cotação expirou | cliente confirma | exige re-cotação e revisão da diferença |
