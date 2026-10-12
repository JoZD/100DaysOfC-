import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import services.common.env  # noqa: F401  (loads .env)

# The app connects as a NON-superuser role: Postgres superusers (and table
# owners without FORCE) bypass row-level security, which would silently turn
# off tenant isolation. Migrations use ADMIN_DATABASE_URL instead.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://finops_app:finops_app@localhost:5432/finops",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
