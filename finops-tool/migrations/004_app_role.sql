-- The docker-compose POSTGRES_USER is a superuser, and superusers bypass RLS
-- entirely (even with FORCE). The API must therefore connect as a
-- non-superuser app role. Migrations keep running as the admin user.
--
-- Dev-only credentials; in prod this role is provisioned outside migrations
-- with a secret-managed password.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'finops_app') THEN
        CREATE ROLE finops_app LOGIN PASSWORD 'finops_app';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO finops_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, findings TO finops_app;
