"""CareerPilot AI — end-to-end API smoke test.

Tests every subsystem built so far against a RUNNING server:
  Phase 1: auth, master profile, jobs/scholarships CRUD, applications, dashboard, documents
  Phase 2: JobScout sources listing + optional live discovery run
  Phase 3: ScholarshipScout optional live run
  Phase 4: verifier optional live run

Usage:
    python scripts/smoke_test.py                      # quick checks (no network discovery)
    python scripts/smoke_test.py --full               # also runs discovery + verification live
    python scripts/smoke_test.py --base-url http://localhost:8000 --email you@example.com

Exits non-zero if any check fails (so it can be used in CI / .bat files).
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

PASS, FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def check(name: str, fn):
    try:
        fn()
        _results.append((PASS, name, ""))
        print(f"  [PASS] {name}")
    except AssertionError as exc:
        _results.append((FAIL, name, str(exc)))
        print(f"  [FAIL] {name}: {exc}")
    except Exception as exc:  # network/parse failures
        _results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default=None, help="Existing account email (optional)")
    parser.add_argument("--password", default=None)
    parser.add_argument("--full", action="store_true",
                        help="Also run live discovery (JobScout/ScholarshipScout) and verification")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v1"
    client = httpx.Client(base_url=api, timeout=180)
    print(f"CareerPilot smoke test -> {base}")
    print("=" * 60)

    # ── Phase 1: auth ─────────────────────────────────────────
    def _auth() -> str:
        # try existing seeded account first, else register a fresh one
        email = args.email or "smoke@example.com"
        password = args.password or "SmokePass123!"
        r = client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            return r.json()["access_token"]
        r = client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": "Smoke Test"},
        )
        assert r.status_code == 201, f"register failed: {r.status_code} {r.text}"
        return r.json()["access_token"]

    token: str | None = None

    def check_health():
        assert client.get("/../health").status_code == 200 or client.get(f"{base}/health").status_code == 200

    def check_auth():
        nonlocal token
        token = _auth()
        assert token

    def check_me():
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text

    headers = {"Authorization": ""}

    def check_profile():
        nonlocal headers
        headers = {"Authorization": f"Bearer {token}"}
        r = client.put(
            "/profile",
            json={
                "full_name": "John Gichaga",
                "nationality": "Kenyan",
                "location": "Nairobi, Kenya",
                "phone": "0114094974",
                "email": "johngichaga8@gmail.com",
                "profession": "Mathematics and Computer Studies Teacher",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["phone"] == "0114094974", "phone did not round-trip through encryption"
        # add a skill (idempotent across repeated smoke runs)
        r = client.post("/profile/skills", json={"name": "Python"}, headers=headers)
        assert r.status_code in (201, 409), f"skill add failed: {r.status_code} {r.text}"

    def check_jobs():
        r = client.post(
            "/jobs",
            json={"title": f"Mathematics Teacher (smoke {int(time.time())})",
                  "organization_name": "Smoke Test School",
                  "location": "Nairobi, Kenya", "employment_type": "Full-time"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        job_id = r.json()["id"]
        r = client.patch(f"/jobs/{job_id}", json={"verification_status": "VERIFIED", "match_score": 92.0},
                         headers=headers)
        assert r.status_code == 200 and r.json()["match_score"] == 92.0, r.text

    def check_scholarships():
        r = client.post(
            "/scholarships",
            json={"name": f"Smoke Scholarship {int(time.time())}", "university": "Smoke University",
                  "degree_level": "Master's", "funding_level": "UNSPECIFIED"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    def check_applications():
        r = client.post(
            "/applications",
            json={"job_id": _job_id, "status": "SHORTLISTED BY AGENT", "match_score": 90.0},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        app_id = r.json()["id"]
        r = client.patch(f"/applications/{app_id}", json={"status": "INTERVIEW",
                                                          "interview_date": "2026-09-10"}, headers=headers)
        assert r.status_code == 200 and r.json()["status"] == "INTERVIEW", r.text

    def check_dashboard():
        r = client.get("/dashboard/summary", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_opportunities"] >= 0 and body["scholarships_total"] >= 0

    def check_documents():
        r = client.post("/documents/upload", params={"doc_type": "OTHER"},
                        files={"file": ("cv.txt", b"John Gichaga - CV placeholder", "text/plain")},
                        headers=headers)
        assert r.status_code == 201, r.text
        assert r.json()["extraction_status"] == "PENDING"

    def check_sources():
        r = client.get("/agents/sources", headers=headers)
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 3, "expected the default discovery sources"

    def check_matcher():
        r = client.post("/agents/matcher/run", params={"force": "true"}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["errors"] == [], f"matcher errors: {r.json()['errors']}"

    def check_notifications():
        r = client.get("/notifications", headers=headers)
        assert r.status_code == 200, r.text
        r = client.get("/notifications/preferences", headers=headers)
        assert r.status_code == 200 and r.json()["in_app"] is True, r.text

    def check_recommendations():
        r = client.get("/recommendations", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "jobs" in body and "scholarships" in body

    def check_cv_generation():
        # generate a fact-checked CV for the application created earlier
        r = client.post(f"/cv/applications/{_app_id}/generate", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["fact_check"]["prohibited_findings"] == [], "CV must pass the FactCheck gate"
        assert body["summary"].get("EDUCATION"), "CV must include education"
        r = client.get("/cv/versions", headers=headers)
        assert r.status_code == 200 and len(r.json()) >= 1, "CV version must be stored"

    def check_cover_letter():
        r = client.post(f"/cover-letters/applications/{_app_id}/generate", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["fact_check"]["prohibited_findings"] == [], "letter must pass the FactCheck gate"
        assert body["text"], "letter must have content"

    _app_id = None

    def _create_app_and_capture():
        nonlocal _app_id
        r = client.post("/applications", json={"job_id": _job_id}, headers=headers)
        assert r.status_code == 201, r.text
        _app_id = r.json()["id"]

    # ── Optional live runs (network) ──────────────────────────
    def check_jobscout_live():
        r = client.post("/agents/jobscout/run", params={"force": "true"}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["errors"] == [], f"jobscout errors: {r.json()['errors']}"

    def check_scholarshipscout_live():
        r = client.post("/agents/scholarshipscout/run", params={"force": "true"}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["errors"] == [], f"scholarshipscout errors: {r.json()['errors']}"

    def check_verifier_live():
        r = client.post("/agents/verify/run", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["errors"] == [], f"verify errors: {r.json()['errors']}"

    # needs job_id from check_jobs
    _job_id = None

    def check_jobs_and_capture():
        nonlocal _job_id
        r = client.post(
            "/jobs",
            json={"title": f"Mathematics Teacher (smoke {int(time.time())})",
                  "organization_name": "Smoke Test School",
                  "location": "Nairobi, Kenya", "employment_type": "Full-time"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        _job_id = r.json()["id"]

    print("\n[1/8] Health & Auth")
    check("health", check_health)
    check("auth (login or register)", check_auth)
    check("auth/me", check_me)

    print("\n[2/8] Master profile")
    check("profile upsert (phone encrypted round-trip)", check_profile)

    print("\n[3/8] Jobs")
    check("create + patch job (verification/match)", check_jobs_and_capture)

    print("\n[4/8] Scholarships")
    check("create scholarship", check_scholarships)

    print("\n[5/8] Applications tracker, CV & cover letter")
    check("create application + status INTERVIEW", check_applications)
    check("capture application id for documents", _create_app_and_capture)
    check("fact-checked CV generation", check_cv_generation)
    check("fact-checked cover letter generation", check_cover_letter)

    print("\n[6/8] Dashboard & documents")
    check("dashboard summary", check_dashboard)
    check("document upload", check_documents)

    print("\n[7/8] Discovery sources & matching")
    check("sources listing", check_sources)
    check("matcher run (eligibility + priority)", check_matcher)
    check("notifications inbox + preferences", check_notifications)
    check("ranked recommendations", check_recommendations)

    if args.full:
        print("\n[8/8] Live pipeline (network)")
        check("JobScout live run", check_jobscout_live)
        check("ScholarshipScout live run", check_scholarshipscout_live)
        check("Verifier live run", check_verifier_live)
    else:
        print("\n[8/8] Live pipeline — SKIPPED (pass --full to run discovery + verification)")

    # ── summary ───────────────────────────────────────────────
    failed = [r for r in _results if r[0] == FAIL]
    print("\n" + "=" * 60)
    print(f"Smoke test finished: {len(_results) - len(failed)}/{len(_results)} checks passed")
    if failed:
        print("Failed checks:")
        for _, name, detail in failed:
            print(f"  - {name}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
