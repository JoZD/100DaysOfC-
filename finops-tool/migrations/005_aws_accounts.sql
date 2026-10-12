-- One tenant (a workspace, e.g. the whole company) owns MANY AWS
-- accounts. Before this, tenants carried a single role_arn/external_id, so a
-- workspace could only ever see one account. The per-account assume-role config
-- moves to aws_accounts, which is tenant data and therefore RLS-protected.

ALTER TABLE tenants ADD CONSTRAINT tenants_name_key UNIQUE (name);

CREATE TABLE IF NOT EXISTS aws_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    role_arn TEXT NOT NULL,
    external_id TEXT NOT NULL,
    -- false for placeholder accounts (seed data) or paused scans
    scan_enabled BOOLEAN NOT NULL DEFAULT true,
    last_scan_at TIMESTAMPTZ,
    last_scan_status TEXT,          -- 'ok' | 'failed'
    last_scan_error TEXT,           -- exception type + message only, never AWS bodies
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

ALTER TABLE aws_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE aws_accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_aws_accounts ON aws_accounts
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Carry existing single-account tenants over. The seeded dev tenant points at
-- a fake account (000000000000), so it must never be scanned.
INSERT INTO aws_accounts (tenant_id, name, role_arn, external_id, scan_enabled)
SELECT id, name, role_arn, external_id,
       role_arn NOT LIKE 'arn:aws:iam::000000000000:%'
FROM tenants;

ALTER TABLE findings ADD COLUMN IF NOT EXISTS aws_account_id UUID REFERENCES aws_accounts(id);
UPDATE findings f SET aws_account_id = a.id
FROM aws_accounts a WHERE a.tenant_id = f.tenant_id AND f.aws_account_id IS NULL;
ALTER TABLE findings ALTER COLUMN aws_account_id SET NOT NULL;

ALTER TABLE tenants DROP COLUMN role_arn;
ALTER TABLE tenants DROP COLUMN external_id;

GRANT SELECT, INSERT, UPDATE, DELETE ON aws_accounts TO finops_app;
