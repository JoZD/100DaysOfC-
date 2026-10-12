"""Sign-in endpoint for the dashboard. See auth.py for the token format."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from services.api.auth import CurrentUser, check_credentials, issue_token
from services.api.db import SessionLocal

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/auth/login")
def login(body: LoginRequest) -> dict:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT id, email, password_hash FROM users WHERE email = :e"),
            {"e": body.email.strip().lower()},
        ).first()
    if not check_credentials(row[2] if row else None, body.password) or row is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token, expires_at = issue_token(str(row[0]), row[1])
    return {"access_token": token, "expires_at": expires_at.isoformat()}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT u.email, t.name FROM users u LEFT JOIN tenants t ON t.id = u.tenant_id "
                 "WHERE u.id = CAST(:id AS uuid)"),
            {"id": user.user_id},
        ).first()
    if row is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"email": row[0], "workspace": row[1]}
