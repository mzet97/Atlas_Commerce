-- 002: ABAC scope grants. A grant binds an actor to one scope
-- (market or warehouse). Checked server-side on every mutation.
CREATE TABLE IF NOT EXISTS scope_grants (
    actor_sub TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (actor_sub, scope_type, scope_id)
);
