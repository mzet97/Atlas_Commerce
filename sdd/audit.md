# sdd/audit.md — M0 auditoria de domínio (SPEC-000)

## 1. Cobertura
Lidos integralmente: blueprint (1171 linhas), prompt master (600 linhas),
docs 01–08, README, 12 diagramas. Verificação por `grep`:
UC-001..UC-011 presentes no blueprint e no doc 03;
INV-001..INV-012 presentes no blueprint e no doc 02.

## 2. Consistências confirmadas (CONFIRMED)
- Ownership único por agregado: Control nunca escreve no Mongo dos owners;
  altera por comando autenticado, lê por projeção (docs 02, 04, 06).
- Sequência checkout: `ReserveStock → PlaceOrder(PENDING_PAYMENT) →
  Authorize → Confirm/Release`, 3 ramos PSP (200/402/202), saga com
  compensação; sem transação ACID global (docs 03, 04, diagrama 10).
- CQRS: Mongo + outbox na mesma transação → CDC → Kafka (chave por agregado)
  → workers idempotentes (`processed_events`) → PostgreSQL (10 projeções) →
  Redis cache-aside; `availability_hint` não decide saldo (doc 04, diag. 09).
- Dinheiro em unidade mínima (`amount_minor`) ou Decimal, nunca float;
  `Money(amount_minor, currency, exponent)` (docs 02, 08).
- Admin: four-eyes `requested_by != approved_by`, auditoria append-only com
  before/after hashes, 403 fora de escopo auditado (docs 02, 08, diag. 05).
- IA: 8 tools allowlisted (`search_catalog`, `propose_cart_change`, …);
  proibidas `charge_card`, `issue_refund`, `set_price`, `modify_stock`;
  aprovação humana explícita, `approval bypass = 0` (doc 08).

## 3. Conflitos e divergências (→ decisions-open.md)
- OPEN-01: IDs de invariantes divergem — docs usam `INV-001..INV-012`,
  prompt §3.2 usa `INV-STOCK-001`, `INV-ORDER-001`, etc. Sem tabela de
  equivalência. Precedência: docs modulares como referência; mapear em M1.
- OPEN-02: ordem reserva↔pedido↔autorização é ADR pendente; blueprint §03
  fixa Reserva→Pedido→Autorização, prompt §4.1 deixa a ordem como ADR.
  Adotar blueprint como default PROPOSED até ADR-007.
- OPEN-03: blueprint traz linha `INV-03` (tabela aceitação, estoque zero no
  carrinho) que não existe no doc 02; tratar como caso de aceitação, não
  invariante nova.
- OPEN-04: PSP fake — cenários determinísticos exigidos pelo prompt
  (`APPROVED/DECLINED/TIMEOUT/UNKNOWN/DUPLICATE/OUT_OF_ORDER/REFUND`) ainda
  sem contrato de webhook assinado versionado.
- OPEN-05: SLOs do doc 05 são propostas não medidas; L0–L4 são cargas
  artificiais, não capacidade comprovada.

## 4. Diagramas
12/12 presentes e sintaticamente plausíveis (Mermaid/PlantUML revisados por
leitura; sem render executado neste M0 — validação de render vai para M1).
Mapa: 00 contextos, 01–02 usecases, 03–05 ER, 06–07 classes, 08 estado,
09 projeção, 10 sequência, 11 sumário.

## 5. Gate M0
Fontes localizadas e rastreáveis: OK. Ownership único: OK.
5 cenários críticos auditáveis (UC003-T01..T05): OK.
ADRs 001–006 como PROPOSED, ADR-007 (ordem da saga) a abrir: OK.
Nenhum código criado neste M0, conforme §17 do prompt.
