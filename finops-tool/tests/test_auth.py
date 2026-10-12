"""Local sign-in: password hashing, tokens, /auth/login and the admin user commands."""

import argparse
import io
import sys
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from services.api import auth
from services.api.db import SessionLocal
from services.api.main import app
from tests.test_rls import _db_available

SECRET = "x" * 40


@pytest.fixture(autouse=True)
def auth_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", SECRET)
    auth._auth_secret.cache_clear()
    yield
    auth._auth_secret.cache_clear()


def test_password_hash_roundtrip_and_salting():
    first, second = auth.hash_password("correct horse"), auth.hash_password("correct horse")
    assert first != second and "correct horse" not in first
    assert auth.verify_password("correct horse", first)
    assert not auth.verify_password("wrong horse", first)
    assert not auth.verify_password("correct horse", "garbage")
    assert not auth.check_credentials(None, "anything")


def test_token_roundtrip_and_rejections(monkeypatch):
    token, _ = auth.issue_token("user-1", "a@example.com")
    user = auth.get_current_user(f"Bearer {token}")
    assert (user.user_id, user.email) == ("user-1", "a@example.com")

    expired = jwt.encode({"sub": "u", "iss": auth.ISSUER, "exp": datetime.now(UTC) - timedelta(1)},
                         SECRET, algorithm="HS256")
    forged = jwt.encode({"sub": "u", "iss": auth.ISSUER, "exp": datetime.now(UTC) + timedelta(1)},
                        "y" * 40, algorithm="HS256")
    wrong_issuer = jwt.encode({"sub": "u", "iss": "other", "exp": datetime.now(UTC) + timedelta(1)},
                              SECRET, algorithm="HS256")
    for bad in (None, "Token abc", f"Bearer {expired}", f"Bearer {forged}", f"Bearer {wrong_issuer}"):
        with pytest.raises(HTTPException) as exc:
            auth.get_current_user(bad)
        assert exc.value.status_code == 401


def test_short_secret_is_refused(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "short")
    auth._auth_secret.cache_clear()
    with pytest.raises(RuntimeError):
        auth.issue_token("u", "e")


@pytest.mark.skipif(not _db_available(), reason="Postgres not running")
def test_admin_create_user_and_login(monkeypatch):
    from scripts import admin

    email = "Test-Login-User@Example.Invalid"
    password = "a-long-test-password"
    with SessionLocal() as db:
        try:
            monkeypatch.setattr(sys, "stdin", io.StringIO(password + "\n"))
            admin.create_user(db, argparse.Namespace(email=email, tenant=None, password_stdin=True))
            stored = db.execute(text("SELECT password_hash FROM users WHERE email = :e"),
                                {"e": email.lower()}).scalar_one()
            assert stored.startswith("scrypt$") and password not in stored

            client = TestClient(app)
            assert client.post("/auth/login", json={"email": email, "password": "nope"}).status_code == 401
            assert client.post("/auth/login", json={"email": "missing@example.invalid",
                                                    "password": password}).status_code == 401
            response = client.post("/auth/login", json={"email": email, "password": password})
            assert response.status_code == 200
            token = response.json()["access_token"]
            me = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()
            assert me == {"email": email.lower(), "workspace": None}
            # No workspace yet: tenant data is unreachable until one is created.
            assert client.get("/findings", headers={"Authorization": f"Bearer {token}"}).status_code == 404
        finally:
            db.rollback()
            db.execute(text("DELETE FROM users WHERE email = :e"), {"e": email.lower()})
            db.commit()
