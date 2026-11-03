-- 005: refunds on the payment read model (M6). INV-006: estorno gera
-- registro auditável; a projeção carrega o acumulado, nunca edita histórico.
ALTER TABLE payment_intents
    ADD COLUMN IF NOT EXISTS refunded_minor INT NOT NULL DEFAULT 0;
