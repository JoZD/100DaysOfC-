-- The app connects as the table owner in dev, and Postgres exempts table
-- owners from RLS by default — without FORCE, the tenant_isolation policy
-- from 001 was not actually being enforced.
ALTER TABLE findings FORCE ROW LEVEL SECURITY;
