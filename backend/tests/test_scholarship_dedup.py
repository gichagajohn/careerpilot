"""Scholarship dedup tests."""
from __future__ import annotations

from app.models import Scholarship, ScholarshipSource
from app.services.dedup import attach_scholarship_source, find_duplicate_scholarship, new_cluster_id


def _scholarship(db, name, university):
    sch = Scholarship(name=name, university=university, status="DISCOVERED",
                      verification_status="UNVERIFIED", duplicate_group=new_cluster_id())
    db.add(sch)
    db.flush()
    return sch


def test_exact_duplicate_found(db_session):
    _scholarship(db_session, "DAAD Master's Scholarship", "German universities")
    dup = find_duplicate_scholarship(db_session, "DAAD Master's Scholarship", "German universities")
    assert dup is not None


def test_fuzzy_duplicate_found(db_session):
    _scholarship(db_session, "Erasmus Mundus Joint Master", "European universities")
    dup = find_duplicate_scholarship(db_session, "Erasmus Mundus Joint Master - Education", "European universities")
    assert dup is not None


def test_distinct_scholarship_not_flagged(db_session):
    _scholarship(db_session, "Chevening Scholarship", "UK universities")
    assert find_duplicate_scholarship(db_session, "DAAD Master's Scholarship", "German universities") is None


def test_scholarship_source_attach(db_session):
    sch = _scholarship(db_session, "AIMS Scholarship", "AIMS")
    assert attach_scholarship_source(db_session, sch, "page:aims", "FETCH", "https://nexteinstein.org/") is True
    assert attach_scholarship_source(db_session, sch, "page:aims", "FETCH", "https://nexteinstein.org/") is False
    assert attach_scholarship_source(db_session, sch, "websearch", "SEARCH", "https://portal.example/x") is True
    assert db_session.query(ScholarshipSource).filter(ScholarshipSource.scholarship_id == sch.id).count() == 2
