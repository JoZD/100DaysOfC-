"""Apply migrations/*.sql in order. Idempotent enough for dev (files use
IF NOT EXISTS where possible); a real migration tool (alembic) replaces this
once the schema stabilizes.

Usage: python -m scripts.apply_migrations
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, text

import services.common.env  # noqa: F401  (loads .env)

# Migrations run as the admin/owner user, NOT the RLS-restricted app role.
engine = create_engine(
    os.environ.get(
        "ADMIN_DATABASE_URL",
        "postgresql+psycopg2://finops:finops@localhost:5432/finops",
    )
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def main() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        applied = {
            row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations"))
        }

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            print(f"skip  {path.name}")
            continue
        with engine.begin() as conn:
            conn.execute(text(path.read_text()))
            conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:f)"), {"f": path.name}
            )
        print(f"apply {path.name}")

    # 004 creates finops_app with a dev-only password. On a real server,
    # APP_DB_PASSWORD rotates it to the secret from the server's .env.
    app_password = os.environ.get("APP_DB_PASSWORD")
    if app_password:
        with engine.begin() as conn:
            # ALTER ROLE can't take bind parameters; quote_literal escapes safely.
            quoted = conn.execute(text("SELECT quote_literal(:p)"), {"p": app_password}).scalar()
            conn.execute(text(f"ALTER ROLE finops_app PASSWORD {quoted}"))
        print("set   finops_app password from APP_DB_PASSWORD")


if __name__ == "__main__":
    main()
