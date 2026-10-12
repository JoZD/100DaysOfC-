import duckdb


def load_cur_view(con: duckdb.DuckDBPyConnection, bucket: str, prefix: str) -> None:
    """Register a `cur` view over a tenant's CUR 2.0 Parquet export.

    Requires the tenant's assumed-role credentials to already be set on the
    DuckDB S3 extension (httpfs) before calling this. Not wired into the
    rules engine yet — phase 1b, once cost-based rules (rightsizing,
    Savings Plan coverage) are added alongside the inventory-based ones.
    """
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW cur AS
        SELECT * FROM read_parquet('s3://{bucket}/{prefix}/*.parquet')
        """
    )
