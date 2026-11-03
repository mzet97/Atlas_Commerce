-- 003: maker-checker approvals for money-moving commands (M4).
-- A request captures WHO asked; execution requires a DIFFERENT approver.
-- One PENDING request per (action, intent): partial unique index.
CREATE TABLE IF NOT EXISTS finance_approvals (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_correlation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    decided_by TEXT,
    decided_at TIMESTAMPTZ,
    execution_status INT
);
CREATE UNIQUE INDEX IF NOT EXISTS finance_approvals_pending_uniq
    ON finance_approvals (action, intent_id) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS finance_approvals_status_idx
    ON finance_approvals (status);
