-- Once a pooled connection has had app.current_tenant_id set (even with
-- set_config(..., true)), Postgres resets it to '' — not NULL — when the
-- transaction ends. ''::uuid raises an error, so a query on a reused
-- connection without tenant context crashed instead of seeing zero rows.
-- NULLIF makes "no tenant context" uniformly mean "no rows".
ALTER POLICY tenant_isolation_findings ON findings
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
ALTER POLICY tenant_isolation_aws_accounts ON aws_accounts
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
