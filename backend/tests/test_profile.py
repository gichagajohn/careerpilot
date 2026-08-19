"""Master profile CRUD tests — the single source of truth."""
from __future__ import annotations


def _put_profile(client, headers, **overrides):
    data = {
        "full_name": "John Gichaga",
        "nationality": "Kenyan",
        "location": "Nairobi, Kenya",
        "phone": "0114094974",
        "email": "johngichaga8@gmail.com",
        "profession": "Mathematics and Computer Studies Teacher",
        "professional_registration": "Teacher Service Commission (TSC) registered teacher",
    }
    data.update(overrides)
    return client.put("/api/v1/profile", json=data, headers=headers)


def test_profile_upsert_and_read(client, auth_headers):
    r = _put_profile(client, auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "John Gichaga"
    # phone round-trips through encryption at rest
    assert body["phone"] == "0114094974"

    r = client.get("/api/v1/profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["location"] == "Nairobi, Kenya"
    assert r.json()["professional_registration"].startswith("Teacher Service Commission")


def test_profile_requires_auth(client):
    assert client.get("/api/v1/profile").status_code == 401


def test_education_experience_skills_certifications(client, auth_headers):
    _put_profile(client, auth_headers)

    # education
    r = client.post(
        "/api/v1/profile/education",
        json={
            "degree": "Bachelor of Education (Arts)",
            "institution": "Gretsa University",
            "field": "Mathematics and Computer Studies",
            "classification": "First Class Honours",
            "start_date": "2022",
            "end_date": "2025",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    edu_id = r.json()["id"]

    # experience
    r = client.post(
        "/api/v1/profile/experience",
        json={
            "organization": "Huruma Girls Senior School",
            "role": "Mathematics and Computer Studies Teacher",
            "start_date": "2026-01",
            "is_current": True,
            "subjects": ["Mathematics", "Computer Studies"],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    # skills
    r = client.post(
        "/api/v1/profile/skills",
        json={"name": "Python", "category": "technical", "level": "proficient"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    # duplicate skill rejected
    assert (
        client.post(
            "/api/v1/profile/skills",
            json={"name": "Python"},
            headers=auth_headers,
        ).status_code
        == 409
    )

    # certification
    r = client.post(
        "/api/v1/profile/certifications",
        json={"name": "TSC Registration", "issuer": "Teachers Service Commission"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    # full profile read
    r = client.get("/api/v1/profile", headers=auth_headers)
    body = r.json()
    assert len(body["education"]) == 1
    assert body["education"][0]["classification"] == "First Class Honours"
    assert len(body["experience"]) == 1
    assert body["experience"][0]["subjects"] == ["Mathematics", "Computer Studies"]
    assert len(body["skills"]) == 1
    assert len(body["certifications"]) == 1

    # update education
    r = client.put(
        f"/api/v1/profile/education/{edu_id}",
        json={"degree": "Bachelor of Education (Arts)", "institution": "Gretsa University",
              "classification": "First Class Honours", "notes": "Updated"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Updated"

    # cross-user isolation: a second user cannot see or edit this profile's items
    r2 = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "StrongPass123", "full_name": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    # The second user gets their OWN empty profile (not a 404, and never the
    # first user's data), and still cannot touch the first user's entries.
    other = client.get("/api/v1/profile", headers=other_headers)
    assert other.status_code == 200
    assert other.json()["id"] != body["id"]
    assert other.json()["education"] == []
    assert other.json()["profile_complete"] is False
    assert (
        client.put(f"/api/v1/profile/education/{edu_id}", json={}, headers=other_headers).status_code
        == 404
    )


# ── Regression tests for the "Master profile not found" bug ─────────────


def test_first_login_gets_empty_profile_not_404(client, auth_headers):
    """A freshly registered user must be able to open the Profile page."""
    r = client.get("/api/v1/profile", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["profile_complete"] is False
    assert body["education"] == [] and body["skills"] == []


def test_first_time_setup_then_profile_loads_normally(client, auth_headers):
    """The onboarding flow: empty profile → PUT → complete profile."""
    assert client.get("/api/v1/profile", headers=auth_headers).json()["profile_complete"] is False

    r = _put_profile(client, auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["profile_complete"] is True

    r = client.get("/api/v1/profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["profile_complete"] is True
    assert r.json()["phone"] == "0114094974"


def test_profile_is_bound_to_authenticated_user_id(client, auth_headers, db_session):
    """profile.user_id must equal the authenticated user's id (not email)."""
    from app.models import MasterProfile, User

    _put_profile(client, auth_headers)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    profile = db_session.query(MasterProfile).filter_by(user_id=me["id"]).one()
    assert profile.user_id == me["id"]
    assert db_session.get(User, profile.user_id).email == me["email"]


def test_each_user_gets_a_separate_profile(client, auth_headers):
    """Two users must never share or see each other's master profile."""
    _put_profile(client, auth_headers, full_name="User One", profession="Teacher")

    r2 = client.post(
        "/api/v1/auth/register",
        json={"email": "second@example.com", "password": "StrongPass123", "full_name": "Second"},
    )
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    p2 = client.get("/api/v1/profile", headers=h2).json()
    assert p2["full_name"] == "Second"
    assert p2["profession"] is None  # not User One's data

    _put_profile(client, h2, full_name="User Two", profession="Engineer")
    assert client.get("/api/v1/profile", headers=auth_headers).json()["full_name"] == "User One"
    assert client.get("/api/v1/profile", headers=h2).json()["full_name"] == "User Two"


def test_repeated_get_does_not_create_duplicate_profiles(client, auth_headers, db_session):
    from app.models import MasterProfile

    for _ in range(3):
        assert client.get("/api/v1/profile", headers=auth_headers).status_code == 200
    assert db_session.query(MasterProfile).count() == 1


def test_inactive_profile_is_recovered_not_hidden(client, auth_headers, db_session):
    """An is_active=False row used to be invisible to GET but writable by PUT."""
    from app.models import MasterProfile

    _put_profile(client, auth_headers)
    profile = db_session.query(MasterProfile).one()
    profile.is_active = False
    db_session.commit()

    r = client.get("/api/v1/profile", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "John Gichaga"
    assert db_session.query(MasterProfile).count() == 1


def test_sub_resources_work_without_explicit_profile_creation(client, auth_headers):
    """Education/skills no longer 404 for a user who never called PUT /profile."""
    r = client.post(
        "/api/v1/profile/education",
        json={"degree": "B.Ed", "institution": "Gretsa University"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/profile/skills", json={"name": "Python"}, headers=auth_headers)
    assert r.status_code == 201, r.text
