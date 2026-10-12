"""Local dashboard authentication.

Users live in the `users` table (scripts.admin create-user). POST /auth/login
checks the password and returns a short-lived HS256 token signed with
AUTH_SECRET; the web server keeps it in an httpOnly cookie and sends it back
as a bearer token. Nothing here talks to an external identity provider.
"""

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException

ISSUER = "finops-api"

# scrypt parameters (n=2**14, r=8, p=1: ~16 MiB, tens of ms per check).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
MIN_PASSWORD_LENGTH = 12


@lru_cache(maxsize=1)
def _auth_secret() -> str:
    secret = os.environ.get("AUTH_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET must be set to at least 32 characters — see .env.example")
    return secret


def _session_hours() -> int:
    return int(os.environ.get("SESSION_HOURS", "12"))


# --- Passwords ------------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), expected)


# Checked against unknown emails so a miss costs the same time as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def check_credentials(stored_hash: str | None, password: str) -> bool:
    if stored_hash is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, stored_hash)


# --- Tokens ---------------------------------------------------------------------


def issue_token(user_id: str, email: str) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(hours=_session_hours())
    token = jwt.encode(
        {"sub": user_id, "email": email, "iss": ISSUER, "exp": expires_at},
        _auth_secret(),
        algorithm="HS256",
    )
    return token, expires_at


class AuthenticatedUser:
    def __init__(self, user_id: str, email: str | None):
        self.user_id = user_id
        self.email = email


def get_current_user(authorization: str | None = Header(None)) -> AuthenticatedUser:
    """Verify a token issued by /auth/login and return the caller's identity.

    The tenant a request can see is ALWAYS derived from this user id (see
    tenancy.resolve_tenant), never from anything the client sent in the URL/body.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = jwt.decode(
            token,
            _auth_secret(),
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
    return AuthenticatedUser(user_id=claims["sub"], email=claims.get("email"))


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
