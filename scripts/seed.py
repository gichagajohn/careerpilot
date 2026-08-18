"""Seed the master profile (John's verified data from the spec) and,
optionally, demo opportunities for development.

Usage (from the backend/ directory):
    python ../scripts/seed.py --email johngichaga8@gmail.com
    python ../scripts/seed.py --email johngichaga8@gmail.com --demo

The master profile contains ONLY facts supplied by the user. It is the
single source of truth for every generated document (anti-fabrication).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.crypto import encrypt_text  # noqa: E402
from app.core.db import SessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Certification,
    Education,
    Experience,
    Job,
    MasterProfile,
    NotificationPreference,
    Scholarship,
    SearchSource,
    Setting,
    Skill,
    User,
)
from app.schemas.opportunities import JobIn, ScholarshipIn  # noqa: E402

MASTER_PROFILE = {
    "full_name": "John Gichaga",
    "nationality": "Kenyan",
    "location": "Nairobi, Kenya",
    "phone": "0114094974",
    "email": "johngichaga8@gmail.com",
    "profession": "Mathematics and Computer Studies Teacher",
    "professional_registration": "Teacher Service Commission (TSC) registered teacher",
    "summary": (
        "Mathematics and Computer Studies teacher with a First Class Honours B.Ed "
        "(Gretsa University), TSC-registered, currently teaching at Huruma Girls "
        "Senior School. Experienced in CBC/CBE pedagogy, ICT integration and "
        "learner-centred teaching."
    ),
}

EDUCATION = [
    {
        "degree": "Bachelor of Education (Arts)",
        "institution": "Gretsa University",
        "field": "Mathematics and Computer Studies",
        "classification": "First Class Honours",
        "start_date": "2022",
        "end_date": "2025",
        "is_current": False,
        "notes": None,
    }
]

EXPERIENCE = [
    {
        "organization": "Huruma Girls Senior School",
        "role": "Mathematics and Computer Studies Teacher",
        "location": "Kenya",
        "start_date": "2026-01",
        "end_date": None,
        "is_current": True,
        "subjects": ["Mathematics", "Computer Studies"],
        "grades": [],
        "description": None,
    },
    {
        "organization": "Happyland Greenspan Spring",
        "role": "Teacher",
        "location": "Kenya",
        "start_date": "2025-09",
        "end_date": "2025-12",
        "is_current": False,
        "subjects": ["Mathematics", "Integrated Science", "ICT"],
        "grades": ["Grade 7", "Grade 8", "Grade 9"],
        "description": None,
    },
    {
        "organization": "Huruma Girls High School",
        "role": "Teaching Practice",
        "location": "Kenya",
        "start_date": "2025-01",
        "end_date": "2025-04",
        "is_current": False,
        "subjects": ["Mathematics", "Computer Studies"],
        "grades": ["Form 3", "Form 4"],
        "description": None,
    },
]

SKILLS = [
    # Teaching & pedagogy
    ("Mathematics teaching", "teaching"),
    ("Computer Studies teaching", "teaching"),
    ("ICT integration", "teaching"),
    ("CBC/CBE pedagogy", "pedagogy"),
    ("Learner-centred teaching", "pedagogy"),
    ("Competency-based assessment", "pedagogy"),
    ("Curriculum implementation", "pedagogy"),
    ("Project-based learning", "pedagogy"),
    ("Problem solving", "pedagogy"),
    ("Critical thinking", "pedagogy"),
    ("Creativity and innovation", "pedagogy"),
    # Technical
    ("Microsoft Excel", "technical"),
    ("Data analysis", "technical"),
    ("HTML", "technical"),
    ("CSS", "technical"),
    ("JavaScript", "technical"),
    ("Front-end web development", "technical"),
    ("Python", "technical"),
    ("Basic programming", "technical"),
    ("Educational technology", "technical"),
    ("AI tools", "technical"),
    ("AI-assisted workflows", "technical"),
    ("Digital literacy", "technical"),
]

CERTIFICATIONS = [
    {
        "name": "TSC Registration",
        "issuer": "Teachers Service Commission (TSC), Kenya",
        "date_earned": None,
        "reference_number": None,
    }
]

# Demo opportunities — clearly marked as examples for development only.
DEMO_JOBS = [
    JobIn(
        title="Mathematics Teacher (Demo example)",
        organization_name="Nova Pioneer (example)",
        location="Nairobi, Kenya",
        country="Kenya",
        employment_type="Full-time",
        description="Teach Mathematics using inquiry-based, learner-centred methods. "
                    "This is a DEMO record for development.",
        requirements=["Bachelor of Education (Mathematics)", "TSC registration"],
        preferred_requirements=["CBC/CBE experience", "ICT integration"],
        deadline="2026-08-28",
        application_url="https://example.com/apply/math-teacher",
        source_url="https://example.com",
        curriculum="CBC",
        is_international=False,
        remote=False,
        is_ai_training=False,
    ),
    JobIn(
        title="AI Mathematics Evaluator (Demo example)",
        organization_name="AI Training Platform (example)",
        location="Remote",
        country=None,
        employment_type="Contract",
        description="Review and grade AI model responses to Mathematics and logic "
                    "tasks. DEMO record for development.",
        requirements=["Strong mathematics background", "English proficiency"],
        preferred_requirements=["Programming basics", "Data annotation experience"],
        deadline="2026-09-15",
        application_url="https://example.com/apply/ai-evaluator",
        source_url="https://example.com",
        remote=True,
        is_ai_training=True,
    ),
    JobIn(
        title="Computer Science & ICT Teacher (Demo example)",
        organization_name="International School (example)",
        location="Abuja, Nigeria",
        country="Nigeria",
        employment_type="Full-time",
        description="Teach Computer Science and ICT. DEMO record for development.",
        requirements=["Computer Studies/CS teaching", "Bachelor's degree in CS or related"],
        preferred_requirements=["JavaScript", "Python", "International curriculum"],
        deadline="2026-09-30",
        application_url="https://example.com/apply/cs-teacher",
        source_url="https://example.com",
        curriculum="IGCSE",
        is_international=True,
        remote=False,
    ),
]

DEMO_SCHOLARSHIPS = [
    ScholarshipIn(
        name="Erasmus Mundus Joint Master (Demo example)",
        university="European universities (example)",
        country="Europe",
        programme="Educational Technology / Learning Design",
        degree_level="Master's",
        funding_level="FULLY FUNDED",
        tuition_coverage="Full tuition",
        accommodation="Partial",
        living_allowance="Monthly stipend",
        travel_allowance="Travel allowance",
        insurance="Yes",
        application_fee="None",
        eligibility="Open to Kenyan graduates; first degree in Education, STEM or related",
        required_classification="Upper second or equivalent",
        required_field="Education / STEM",
        deadline="2027-01-15",
        application_url="https://example.com/scholarship/erasmus",
        official_url="https://example.com/scholarship/erasmus",
        open_to_kenyans=True,
        open_to_africans=True,
    ),
    ScholarshipIn(
        name="Mastercard Foundation Scholars (Demo example)",
        university="Partner universities (example)",
        country="Africa / Global",
        programme="Various Master's (Education, CS, AI)",
        degree_level="Master's",
        funding_level="FULLY FUNDED",
        tuition_coverage="Full tuition",
        accommodation="Yes",
        living_allowance="Yes",
        travel_allowance="Yes",
        insurance="Yes",
        application_fee="None",
        eligibility="African nationals with strong academic record and leadership potential",
        deadline="2027-03-01",
        application_url="https://example.com/scholarship/mastercard",
        official_url="https://example.com/scholarship/mastercard",
        open_to_kenyans=True,
        open_to_africans=True,
    ),
]

# Default discovery sources (Phase 2: JobScout). Cadence is per-source:
#   3x  = every scheduled run (3×/day default)
#   2x  = twice a day
#   daily = once a day (used for quota-limited APIs like Adzuna)
DEFAULT_SOURCES = [
    {"name": "adzuna", "kind": "API", "url": "https://api.adzuna.com/v1/api/jobs", "category": "jobs", "cadence": "daily",
     "notes": "Official Adzuna API (free tier). Needs ADZUNA_APP_ID/KEY. Core queries only."},
    {"name": "remotive", "kind": "API", "url": "https://remotive.com/api/remote-jobs", "category": "jobs", "cadence": "3x",
     "notes": "Remote jobs API (free, no key)."},
    {"name": "remoteok", "kind": "API", "url": "https://remoteok.com/api", "category": "jobs", "cadence": "3x",
     "notes": "Remote tech jobs API (free, no key)."},
    {"name": "arbeitnow", "kind": "API", "url": "https://www.arbeitnow.com/api/job-board-api", "category": "jobs", "cadence": "3x",
     "notes": "Europe-leaning job feed (free, no key)."},
    {"name": "websearch", "kind": "SEARCH", "url": None, "category": "jobs", "cadence": "2x",
     "notes": "Web search (Google CSE / Serper / Tavily) — discovery only, no scraping of banned sites."},
    {"name": "rss", "kind": "RSS", "url": "https://reliefweb.int/jobs/rss.xml?search%5Bvalue%5D%5B0%5D=education", "category": "jobs", "cadence": "2x",
     "notes": "ReliefWeb education jobs feed. Add more feeds (UN, schools) in the UI/DB."},
]

# Default scholarship sources (Phase 3: ScholarshipScout)
DEFAULT_SCHOLARSHIP_SOURCES = [
    {"name": "websearch", "kind": "SEARCH", "url": None, "category": "scholarships", "cadence": "daily",
     "notes": "Web search for Master's scholarships (fully funded / Kenya / Africa variants)."},
    {"name": "rss", "kind": "RSS", "url": "https://opportunitiesforyouth.org/feed/", "category": "scholarships", "cadence": "daily",
     "notes": "Opportunities for Youth feed (scholarships + opportunities for Africans)."},
    {"name": "scholarship_pages", "kind": "FETCH", "url": None, "category": "scholarships", "cadence": "daily",
     "notes": "Official programme pages (DAAD, Erasmus+, Chevening, Commonwealth, Mastercard, AIMS...). "
              "FULLY FUNDED is only accepted with explicit official evidence (spec §4)."},
    {"name": "scholarship_daad", "kind": "FETCH", "url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "DAAD official scholarships page."},
    {"name": "scholarship_erasmus_mundus", "kind": "FETCH", "url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en", "category": "scholarships", "cadence": "daily",
     "notes": "Erasmus Mundus catalogue (fully funded joint Master's)."},
    {"name": "scholarship_chevening", "kind": "FETCH", "url": "https://www.chevening.org/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Chevening Scholarships (UK government)."},
    {"name": "scholarship_commonwealth", "kind": "FETCH", "url": "https://cscuk.fcdo.gov.uk/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Commonwealth Scholarship Commission (UK)."},
    {"name": "scholarship_mastercard", "kind": "FETCH", "url": "https://mastercardfdn.org/all/scholarships/", "category": "scholarships", "cadence": "daily",
     "notes": "Mastercard Foundation Scholars Program."},
    {"name": "scholarship_aims", "kind": "FETCH", "url": "https://nexteinstein.org/", "category": "scholarships", "cadence": "daily",
     "notes": "AIMS Next Einstein (African math sciences MSc)."},
    {"name": "scholarship_mandela_rhodes", "kind": "FETCH", "url": "https://mandelarhodes.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Mandela Rhodes Scholarships."},
    {"name": "scholarship_fulbright", "kind": "FETCH", "url": "https://foreign.fulbrightonline.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Fulbright Foreign Student Program."},
    {"name": "scholarship_gates_cambridge", "kind": "FETCH", "url": "https://www.gatescambridge.org/", "category": "scholarships", "cadence": "daily",
     "notes": "Gates Cambridge Scholarships."},
]


DEFAULT_SETTINGS = {
    "priority_weights": '{"eligibility": 0.30, "relevance": 0.25, "growth": 0.15, '
                        '"compensation": 0.10, "deadline": 0.10, "org_quality": 0.10}',
    "high_match_threshold": "80",
    "open_to_international": "false",
}


def ensure_default_settings(db, user_id: int) -> int:
    added = 0
    for key, value in DEFAULT_SETTINGS.items():
        exists = db.query(Setting).filter(Setting.user_id == user_id, Setting.key == key).first()
        if exists is None:
            db.add(Setting(user_id=user_id, key=key, value=value))
            added += 1
    return added


def ensure_notification_prefs(db, user_id: int) -> bool:
    exists = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if exists is None:
        db.add(NotificationPreference(user_id=user_id))
        return True
    return False


def ensure_default_sources(db) -> int:
    added = 0
    for row in DEFAULT_SOURCES + DEFAULT_SCHOLARSHIP_SOURCES:
        exists = db.query(SearchSource).filter(
            SearchSource.name == row["name"], SearchSource.category == row["category"]
        ).first()
        if exists is None:
            db.add(SearchSource(**row))
            added += 1
    db.commit()
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed CareerPilot database")
    parser.add_argument("--email", required=True, help="Login email for the seeded account")
    parser.add_argument("--password", default="ChangeMe123!", help="Initial password (change after first login)")
    parser.add_argument("--demo", action="store_true", help="Also insert demo opportunities")
    args = parser.parse_args()

    init_db()
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == args.email.lower()).first()
        if user is None:
            user = User(
                email=args.email.lower(),
                password_hash=hash_password(args.password),
                full_name=MASTER_PROFILE["full_name"],
            )
            db.add(user)
            db.flush()
            print(f"👤 Created user: {args.email}")

        profile = db.query(MasterProfile).filter(MasterProfile.user_id == user.id).first()
        if profile is None:
            profile = MasterProfile(user_id=user.id, full_name=MASTER_PROFILE["full_name"])
            db.add(profile)
            db.flush()

        data = dict(MASTER_PROFILE)
        data["phone_encrypted"] = encrypt_text(data.pop("phone"))
        for field, value in data.items():
            setattr(profile, field, value)

        if not profile.education:
            for row in EDUCATION:
                db.add(Education(profile_id=profile.id, **row))
        if not profile.experience:
            for row in EXPERIENCE:
                db.add(Experience(profile_id=profile.id, **row))
        if not profile.skills:
            for name, category in SKILLS:
                db.add(
                    Skill(
                        profile_id=profile.id,
                        name=name,
                        category=category,
                        level="proficient",
                        approved=True,
                        source="USER APPROVED",
                    )
                )
        if not profile.certifications:
            for row in CERTIFICATIONS:
                db.add(Certification(profile_id=profile.id, **row))

        if args.demo:
            if not db.query(Job).filter(Job.title.ilike("%Demo example%")).first():
                for job_in in DEMO_JOBS:
                    db.add(Job(**job_in.model_dump()))
                print("💼 Added 3 demo jobs (marked 'Demo example')")
            if not db.query(Scholarship).filter(Scholarship.name.ilike("%Demo example%")).first():
                for sch_in in DEMO_SCHOLARSHIPS:
                    db.add(Scholarship(**sch_in.model_dump()))
                print("🎓 Added 2 demo scholarships (marked 'Demo example')")

        added_sources = ensure_default_sources(db)
        if added_sources:
            print(f"🕸️  Added {added_sources} default discovery sources (JobScout, Phase 2)")

        ensure_default_settings(db, user.id)
        ensure_notification_prefs(db, user.id)

        db.commit()

    print("✅ Seed complete.")
    print(f"   Login: {args.email}")
    print(f"   Password: {args.password}  (change it after first login)")
    print("   Master profile: John Gichaga — Mathematics & Computer Studies Teacher")


if __name__ == "__main__":
    main()
