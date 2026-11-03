# 01 — Visão, escopo, personas e linguagem ubíqua

## 1. Problema e proposta de valor
O Atlas Commerce conecta descoberta, escolha, pagamento, entrega, atendimento e devoluções de produtos físicos em mercados internacionais, proporcionando uma experiência coesa ao comprador e visibilidade operacional aos operadores. A operação precisa crescer horizontalmente sem comprometer o isolamento de domínios nem gerar pedidos pagos sem rastreabilidade ou reservas de estoque incoerentes.

## 2. Objetivos de negócio
- Permitir que consumidores encontrem e comprem produtos em seus idiomas, moedas e localidades elegíveis.
- Garantir preços explicáveis (preço base, descontos, frete, tributos, arredondamentos), estoque reservável, pagamentos reconciliados e pedidos rastreáveis.
- Operadores devem controlar catálogo, ofertas, inventário, promoções, pedidos, logística e atendimento por permissões granulares.
- Tornar mensuráveis conversão, receita, ticket médio, abandono, ruptura, tempo de processamento, reembolso e erro operacional.
- Demonstrar ao avaliador do portfólio separação adequada entre monólito modular e microserviços, CQRS poliglota, mensageria, streaming, IAM, observabilidade, testes e IA segura.

## 3. Personas / atores
| Ator | Responsabilidade | Limites |
|---|---|---|
| Visitante | Navegar, pesquisar, solicitar sugestão não personalizada, simular frete | Não acessa pedidos ou perfil de terceiros |
| Cliente autenticado | Carrinho, endereço, pedido, pagamento, devolução, avaliação, consentimento | Só opera seus próprios recursos |
| Atendente | Investigar pedidos, iniciar solicitação de reembolso autorizada | Não altera caixa nem permissões |
| Gestor de catálogo | Aprovar descrições, mídias, atributos e publicação de produto | Não altera saldo físico diretamente |
| Gestor de preços | Editar ofertas, tabela por canal/mercado, cupons | Aprovações por limite de desconto |
| Operador de estoque | Receber, transferir, ajustar e auditar produtos por depósito | Apenas depósitos permitidos; justificativa obrigatória |
| Operador de fulfillment | Picking, packing, expedição, eventos de entrega | Não autoriza captura financeira |
| Analista financeiro | Conciliação, estornos, relatórios financeiros | Segregação de funções |
| Auditor | Consultar trilha de alterações e eventos imutáveis | Somente leitura, evidências exportáveis |
| Superadministrador IAM | Gestão de roles, policies, MFA, sessões e identidade | Não é automaticamente gestor financeiro |
| Vendedor parceiro (fase 2) | Criar ofertas, administrar seu estoque e pedidos | Apenas tenant/seller próprio |
| Operadora de pagamento | Autorizar, capturar, informar chargeback/refund por webhook | Integração externa autenticada |
| Transportadora | Cotações, etiquetas, rastreio, confirmação de entrega | Integração externa autenticada |
| Agente AI | Assistir descoberta/comparação, propor carrinho | Ações sob credenciais delegadas e confirmação humana |

## 4. Jornadas centrais
**Compra:** descoberta → detalhamento → oferta → carrinho → simulação de preço/frete/imposto → checkout → reserva → autorização de pagamento → confirmação → fulfillment → entrega → pós-venda.

**Operação:** cadastro SKU/produto → oferta → recebimento de estoque → aprovação/promoção → publicação → monitoramento → atendimento → auditoria.

**Assistente:** intenção e preferências → recuperação de catálogo autorizado → comparação explicável → proposta de carrinho → consentimento → uso do checkout normal; nunca compra autônoma sem confirmação.

## 5. Escopo
### MVP operacional (vertical slice)
- IAM OIDC, RBAC/ABAC; produtos, SKUs, ofertas, disponibilidade; busca; carrinho; checkout; pedido; estoque reservado; pagamento fake; publicação de eventos; leitura projetada em PostgreSQL; visualização e gestão de produtos/estoque no Admin; localização; observabilidade; teste de falhas/integração/e2e.
### Fase 2
- PSP real sandbox, cupons e impostos por região, múltiplos armazéns, fretes/rastreamento, reembolso, avaliações, catálogo em múltiplos idiomas e agente AI com ferramentas somente leitura + carrinho condicionado.
### Fase 3
- Marketplace 3P, splits financeiros, sellers/settlement, antifraude, busca dedicada, recomendação e streaming analítico em escala, ativos multi-região e stress testing amplo.
### Fora de escopo inicial
- Emissão fiscal efetiva em todos os países, conta bancária da plataforma, armazenar PAN/CVV, prometer milhões de pedidos/s, compras autônomas por LLM, adesão legal automática a cada jurisdição.

## 6. Glossário (linguagem ubíqua)
- **Product:** item conceitual do catálogo, independente do vendedor.
- **Variant / SKU:** variação comercial identificável (cor, tamanho); **SKU** diferencia unidades estocáveis.
- **Offer:** proposta de venda para SKU, vendedor, mercado, canal e vigência.
- **Price Quote:** cotação congelada com expiração e breakdown de custos, impostos e descontos.
- **Stock Ledger:** movimento auditável de inventário por armazém/SKU.
- **Reservation:** alocação temporária de quantidade para um checkout.
- **Order:** contrato comercial imutável quanto a itens e valores capturados em snapshots.
- **Payment Intent:** intenção e tentativas de autorização/captura de pagamento.
- **Shipment:** agrupamento físico de itens enviados; um pedido pode ter vários.
- **Return / Refund:** fluxo logístico reverso distinto da devolução financeira.
- **Read Model:** projeção PostgreSQL orientada a uma consulta; não é a autoridade do comando.
- **Market:** contexto comercial e regulatório geográfico; **locale** é idioma/formatação; **currency** é denominação monetária.
