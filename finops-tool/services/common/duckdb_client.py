import duckdb


def get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    """A fresh, in-memory DuckDB connection for a single tenant/job.

    Never share one connection across tenants or across runs — see
    CLAUDE.md's multi-tenancy invariants.

    Extensions (e.g. httpfs for CUR on S3) are loaded by the collector that
    needs them, not here: INSTALL downloads from the internet, and inventory
    scans must work on hosts with restricted egress.
    """
    return duckdb.connect(database=":memory:")
