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
    assert client.get("/api/v1/profile", headers=other_headers).status_code == 404
    assert (
        client.put(f"/api/v1/profile/education/{edu_id}", json={}, headers=other_headers).status_code
        == 404
    )
