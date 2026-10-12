-- Local dashboard sign-in (services/api/auth.py). Like `tenants`, this table is
-- read before any tenant context exists (login, tenant resolution), so it is
-- not RLS-protected. It stores only salted scrypt hashes, never passwords.
-- Users are created with `python -m scripts.admin create-user`.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash TEXT NOT NULL,
    -- NULL until the user creates a workspace from the web or an operator
    -- assigns one (create-user --tenant).
    tenant_id UUID REFERENCES tenants(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The admin CLI runs with the app role (docker compose run --rm api ...), as
-- it already does for tenants. The HTTP API itself only reads users and
-- attaches a user to a newly created workspace.
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO finops_app;
