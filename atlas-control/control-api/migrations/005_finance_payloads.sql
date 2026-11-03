-- 005: refund parameters ride with the approval (M6): the checker executes
-- exactly what the maker filed, so the request carries its own payload.
ALTER TABLE finance_approvals
    ADD COLUMN IF NOT EXISTS payload JSONB;
