"""Auth flow tests."""
from __future__ import annotations


def test_register_login_me_refresh(client):
    # register
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "teacher@example.com", "password": "StrongPass123", "full_name": "John Gichaga"},
    )
    assert r.status_code == 201
    tokens = r.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]

    access = tokens["access_token"]

    # /me
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["email"] == "teacher@example.com"
    assert r.json()["full_name"] == "John Gichaga"

    # duplicate email
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "teacher@example.com", "password": "StrongPass123", "full_name": "X"},
    )
    assert r.status_code == 409

    # login
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@example.com", "password": "StrongPass123"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]

    # wrong password
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401

    # refresh
    r = client.post(
        "/api/v1/auth/refresh",
        params={"refresh_token": tokens["refresh_token"]},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]

    # garbage refresh token
    r = client.post("/api/v1/auth/refresh", params={"refresh_token": "not.a.token"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
