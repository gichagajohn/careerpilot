"""ScholarshipScout pipeline tests with a mocked adapter."""
from __future__ import annotations

from app.agents.scholarship_scout import run_scholarship_scout
from app.models import Scholarship, ScholarshipSource, SearchRun, SearchSource
from app.services.normalizer import RawListing


class _FakeScholarshipAdapter:
    name = "scholarship_pages"
    kind = "FETCH"

    def fetch(self, db, query=None, limit=20):  # noqa: ARG002
        return [
            RawListing(
                title="Erasmus Mundus Joint Master in Educational Technology",
                url="https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en",
                raw_text=("Erasmus Mundus Joint Master fully funded. "
                          "Full tuition, monthly stipend, accommodation, travel. "
                          "Open to Kenyan graduates. Deadline: 2027-01-15."),
                source_name="scholarship_pages",
                source_type="FETCH",
            )
        ]


def _add_source(db, name="scholarship_pages", cadence="daily", last_run_at=None):
    src = SearchSource(name=name, kind="FETCH", url="https://example.com/page", category="scholarships",
                       cadence=cadence, enabled=True, last_run_at=last_run_at)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def test_scholarshipscout_pipeline(monkeypatch, db_session):
    from app.agents import scholarship_scout as module

    _add_source(db_session)
    monkeypatch.setitem(module.ADAPTERS, "scholarship_pages", _FakeScholarshipAdapter)

    stats = run_scholarship_scout(db_session, force=True)

    assert stats["sources_run"] == 1
    assert stats["listings"] == 1
    assert stats["new_scholarships"] == 1
    assert stats["errors"] == []

    sch = db_session.query(Scholarship).one()
    assert sch.name == "Erasmus Mundus Joint Master in Educational Technology"
    assert sch.funding_level == "FULLY FUNDED"  # official-style evidence in text
    assert sch.open_to_kenyans is True
    assert sch.verification_status == "UNVERIFIED"
    assert db_session.query(SearchRun).count() == 1

    # second forced run → no new rows (same URL already attached)
    stats2 = run_scholarship_scout(db_session, force=True)
    assert stats2["new_scholarships"] == 0
    assert db_session.query(Scholarship).count() == 1
    assert db_session.query(ScholarshipSource).count() == 1


def test_scholarshipscout_cadence(monkeypatch, db_session):
    from datetime import datetime

    from app.agents import scholarship_scout as module

    _add_source(db_session, last_run_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    monkeypatch.setitem(module.ADAPTERS, "scholarship_pages", _FakeScholarshipAdapter)

    assert run_scholarship_scout(db_session, force=False)["sources_run"] == 0
