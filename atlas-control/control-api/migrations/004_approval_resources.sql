-- 004: approvals generalize beyond payment reconciles (M4).
-- resource_type names what intent_id points at ('payment_intent' legacy
-- default, 'order' for operational cancels). The partial unique index on
-- (action, intent_id) already dedupes per action/target pair.
ALTER TABLE finance_approvals
    ADD COLUMN IF NOT EXISTS resource_type TEXT NOT NULL DEFAULT 'payment_intent';
