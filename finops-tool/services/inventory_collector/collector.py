import boto3
import duckdb
import pandas as pd

# Typed schemas for each inventory view. Views are always registered with
# these columns and types, even when an account has zero resources, so rule
# SQL never hits a binder error (missing column, or VARCHAR where it expects
# a number) on an empty account.
EC2_VOLUMES_SCHEMA = {
    "region": "string",
    "volume_id": "string",
    "size_gb": "Int64",
    "volume_type": "string",
    "state": "string",
}
EC2_ADDRESSES_SCHEMA = {
    "region": "string",
    "allocation_id": "string",
    "public_ip": "string",
    "association_id": "string",
}


def list_enabled_regions(session: boto3.Session, home_region: str) -> list[str]:
    """Regions enabled for the tenant account (opt-in regions excluded unless opted in)."""
    ec2 = session.client("ec2", region_name=home_region)
    resp = ec2.describe_regions(AllRegions=False)
    return sorted(r["RegionName"] for r in resp["Regions"])


def collect_ec2_volumes(session: boto3.Session, region: str) -> list[dict]:
    ec2 = session.client("ec2", region_name=region)
    volumes: list[dict] = []
    for page in ec2.get_paginator("describe_volumes").paginate():
        for v in page["Volumes"]:
            volumes.append(
                {
                    "region": region,
                    "volume_id": v["VolumeId"],
                    "size_gb": v["Size"],
                    "volume_type": v["VolumeType"],
                    "state": v["State"],
                }
            )
    return volumes


def collect_ec2_addresses(session: boto3.Session, region: str) -> list[dict]:
    ec2 = session.client("ec2", region_name=region)
    resp = ec2.describe_addresses()
    return [
        {
            "region": region,
            "allocation_id": a.get("AllocationId"),
            "public_ip": a.get("PublicIp"),
            "association_id": a.get("AssociationId"),
        }
        for a in resp["Addresses"]
    ]


def load_inventory_views(
    con: duckdb.DuckDBPyConnection, session: boto3.Session, regions: list[str]
) -> dict[str, int]:
    """Collect inventory across `regions` and register it as DuckDB views.

    Returns row counts per view, for logging.
    """
    volumes: list[dict] = []
    addresses: list[dict] = []
    for region in regions:
        volumes.extend(collect_ec2_volumes(session, region))
        addresses.extend(collect_ec2_addresses(session, region))

    register_view(con, "ec2_volumes", volumes, EC2_VOLUMES_SCHEMA)
    register_view(con, "ec2_addresses", addresses, EC2_ADDRESSES_SCHEMA)
    return {"ec2_volumes": len(volumes), "ec2_addresses": len(addresses)}


def register_view(
    con: duckdb.DuckDBPyConnection, name: str, rows: list[dict], schema: dict[str, str]
) -> None:
    con.register(name, pd.DataFrame(rows, columns=list(schema)).astype(schema))
