import boto3


def assume_tenant_role(
    role_arn: str,
    external_id: str,
    session_name: str,
    region: str = "us-east-1",
    duration_seconds: int = 900,
) -> boto3.Session:
    """Assume a tenant's read-only role for a single job run.

    ExternalId is mandatory: without it, anyone who learns a tenant's role
    ARN could assume it from another AWS account (the "confused deputy"
    problem). See CLAUDE.md.
    """
    if not external_id:
        raise ValueError("external_id is required for every cross-account AssumeRole call")

    # Resolve the VM's ambient credentials afresh for each job. Never retain a
    # default/global boto3 session across runs or supply source keys in config.
    sts = boto3.Session().client("sts", region_name=region)
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
        ExternalId=external_id,
        DurationSeconds=duration_seconds,
    )
    creds = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )
