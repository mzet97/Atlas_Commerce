-- 001: Control-owned audit trail (append-only by convention: no UPDATE/DELETE
-- grants are issued, and rows are never modified by the application).
CREATE TABLE IF NOT EXISTS admin_actions (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_sub TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    result TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS admin_actions_actor_idx ON admin_actions (actor_sub);
CREATE INDEX IF NOT EXISTS admin_actions_action_idx ON admin_actions (action);
