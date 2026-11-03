# Atlas Commerce — Discovery & Domain Modeling v0.1

**Data:** 27/10/2026 · **Estado:** especificação inicial, não implementação · **Linguagem:** português (termos de domínio em inglês para APIs)

## Problema
Projetar uma plataforma internacional de comércio eletrônico on-premises/cloud-native, com uma experiência de compra e uma experiência administrativa separadas. O **Storefront** será Next.js + microserviços FastAPI. O **Control** será Angular + monólito modular FastAPI. Compartilham contratos e serviços de negócio, **não** a propriedade das coleções de dados.

## Organização de código futura
Os sistemas serão **repositórios Git diferentes** (`atlas-storefront`, `atlas-control`) e compartilharão um terceiro repositório leve de contratos/templates (`atlas-platform-contracts`). Este pacote ainda **não** cria esses repositórios nem o código de produção.

## Ordem de leitura (business-first)
1. [Visão, personas, escopo e glossário](docs/01-VISAO-E-ESCOPO.md)
2. [Bounded contexts, entidades e invariantes](docs/02-DOMINIOS-E-INVARIANTES.md)
3. [Casos de uso e processos de negócio](docs/03-CASOS-DE-USO-E-PROCESSOS.md)
4. [Modelos ER, documentos de escrita e CQRS](docs/04-MODELAGEM-DE-DADOS-CQRS.md)
5. [Qualidade, SLOs, escala e plano de carga](docs/05-NFR-E-ESCALA.md)
6. [Arquitetura-alvo e decisões arquiteturais](docs/06-ARQUITETURA-ALVO-E-ADRS.md)
7. [Plano SDD, testes, critérios de pronto](docs/07-SDD-BACKLOG-E-QUALIDADE.md)
8. [Internacionalização, IAM e assistente AI](docs/08-I18N-IAM-AI.md)

## Diagramas editáveis
- `diagrams/*.mmd`: diagramas Mermaid (visualizáveis no GitHub e editores compatíveis).
- `diagrams/*.puml`: UML de casos de uso em PlantUML.

## Premissas a validar com stakeholders
- Modelo comercial **1P em MVP** (a plataforma é vendedora) e **3P em expansão** (marketplace de vendedores); o modelo de dados já separa Product de Offer.
- Mercados prioritários: BR, US e UE; idiomas iniciais pt-BR, en-US e es-ES. Idioma ≠ moeda ≠ país.
- Itens físicos no MVP; produtos digitais, assinatura, B2B, leilões e recommerce fora do primeiro release.
- PSP externo: integração simulada em desenvolvimento; dados brutos de cartão nunca são persistidos.
- Motor de frete via adaptadores; entregas e fulfillment podem ocorrer em múltiplos pacotes.
- Cobertura e carga são metas demonstráveis, não alegações sem benchmark.

## Gates para encerrar a fase Discovery
- [ ] Glossário, premissas e mapa de bounded contexts revisados.
- [ ] Use cases críticos com fluxos alternativos e Given/When/Then aprovados.
- [ ] Owner de toda entidade, comando, evento e projeção definido.
- [ ] Diagrama ER conceitual, diagrama de classes e diagramas UML de casos de uso versionados.
- [ ] Invariantes de estoque, dinheiro, pedidos e autorização validadas.
- [ ] Trade-offs de CQRS, escala, consistência e administração documentados em ADRs.
- [ ] NFRs e cenário de benchmark com ambiente, medição e critérios de aprovação definidos.

> **Atenção:** Este pacote define o problema e o desenho inicial. Não contém aplicativos implementados, cluster Kubernetes provisionado, testes executados ou capacidade de milhões de compras/s validada.
