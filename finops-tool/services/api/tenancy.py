from fastapi import HTTPException
from sqlalchemy import text


def resolve_tenant(db, user_id: str) -> str:
    """Map the signed-in user to their tenant and arm RLS for this transaction.

    set_config(..., true) scopes the tenant context to this transaction
    only, so a pooled connection can't leak it into another request
    (SET doesn't accept bind parameters; set_config does). RLS on
    `findings` and `aws_accounts` (001/003/005) enforces isolation using this value;
    the explicit WHERE in each query is belt-and-braces on top.
    """
    row = db.execute(
        text("SELECT tenant_id FROM users WHERE id = CAST(:user_id AS uuid)"),
        {"user_id": user_id},
    ).first()
    if row is None:
        # Token is valid but the user was deleted since sign-in.
        raise HTTPException(status_code=401, detail="User no longer exists")
    tenant_id = row[0]
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="No workspace assigned to this user yet")
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    return str(tenant_id)
