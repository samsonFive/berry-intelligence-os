"""Entity Intelligence Timeline & Change History V1.

Company/Variety already shipped Source/Entity Intelligence Timeline V1.
This mission closes Geography parity on the same `entity_intelligence_timeline`
builder, keeps published_date vs captured_date discipline, and fills Assessment
timeline lineage from explicit evidence_ids (PR #181 reuse pattern).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.queries.timeline import entity_intelligence_timeline
from app.services.geography_workspace import geography_detail
from app.services.watchlist import is_watched, load_watches
from app.services import watchlist as watchlist_mod

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]

GEO_RICH = "geography-peru"
GEO_SPARSE = "geography-zambia"
COMPANY_WITH_EVIDENCE = "company-planasa"
VARIETY_WITH_EVIDENCE = "variety-sekoya-pop"


def _entity(**overrides):
    row = {
        "record_type": "entity",
        "status": "active",
        "aliases": [],
        "berry_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(id="company-x", entity_type="company", name="Company X"),
        _entity(id="variety-y", entity_type="variety", name="Variety Y", berry_ids=["berry-blueberry"]),
        _entity(id="geography-us", entity_type="geography", name="United States"),
    ]
    return {row["id"]: row for row in rows}


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "record_type": "evidence",
        "status": "published",
        "source_type": "trade_press",
        "title": "Some article",
        "summary": "A summary.",
        "captured_date": "2026-01-01",
        "entity_ids": ["company-x"],
        "geography_ids": [],
    }
    row.update(overrides)
    return row


# --- Date discipline -------------------------------------------------------


def test_newest_first_ordering_on_dated_timeline():
    entities = _entities()
    evidence = [
        _evidence(id="ev-old", published_date="2024-01-01", title="Old"),
        _evidence(id="ev-new", published_date="2026-06-01", title="New"),
        _evidence(id="ev-mid", published_date="2025-06-01", title="Mid"),
    ]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert [r["date"] for r in result["dated"]] == ["2026-06-01", "2025-06-01", "2024-01-01"]


def test_published_date_not_captured_date_for_evidence_chronology():
    entities = _entities()
    evidence = [
        _evidence(id="ev-only-captured", published_date=None, captured_date="2026-08-01"),
        _evidence(id="ev-published", published_date="2025-01-15", captured_date="2026-08-01"),
    ]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert result["dated_count"] == 1
    assert result["dated"][0]["id"] == "ev-published"
    assert result["dated"][0]["date"] == "2025-01-15"
    assert result["undated"][0]["id"] == "ev-only-captured"


def test_commercial_does_not_use_captured_date_as_chronology():
    entities = _entities()
    commercial = _evidence(
        id="ev-commercial-captured-only",
        intake_type="commercial_observation",
        commercial_observation={"retailer_name": "Tesco"},
        published_date=None,
        captured_date="2026-07-01",
    )
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[commercial],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={commercial["id"]: commercial},
    )
    assert result["dated"] == []
    assert result["undated"][0]["kind"] == "commercial"
    assert result["undated"][0]["date_basis"] == "published_date"


def test_assessment_created_at_chronology_and_evidence_lineage():
    entities = _entities()
    evidence = [_evidence(id="ev-a", published_date="2024-01-01", title="Source article")]
    assessment = {
        "id": "assessment-a",
        "title": "An analyst interpretation.",
        "rationale": "Because of X and Y.",
        "why_it_matters": "Ownership timing matters.",
        "status": "active",
        "confidence": "medium",
        "ai_proposed": True,
        "evidence_ids": ["ev-a", "ev-missing"],
        "reviewer": "analyst",
        "created_at": "2026-04-15",
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[assessment],
        evidence_idx={r["id"]: r for r in evidence},
    )
    row = result["dated"][0]
    assert row["date"] == "2026-04-15"
    assert row["date_basis"] == "created_at"
    assert row["ai_proposed"] is True
    assert row["excerpt"] == "Ownership timing matters."
    assert [item["id"] for item in row["lineage"]] == ["ev-a"]
    assert "ev-missing" not in [item["id"] for item in row["lineage"]]


def test_signal_without_reliable_own_date_uses_labeled_evidence_fallback_or_undated():
    entities = _entities()
    with_fallback = {
        "id": "signal-a",
        "title": "Pattern with evidence date only.",
        "status": "proposed",
        "evidence_ids": ["ev-3"],
        "first_seen": None,
        "last_updated": None,
        "entity_ids": ["company-x"],
    }
    undated = {
        "id": "signal-b",
        "title": "Nothing dateable.",
        "status": "proposed",
        "evidence_ids": ["ev-gone"],
        "entity_ids": ["company-x"],
    }
    evidence_idx = {"ev-3": _evidence(id="ev-3", published_date="2023-05-05")}
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[with_fallback, undated],
        entity_assessments=[],
        evidence_idx=evidence_idx,
    )
    by_id = {r["id"]: r for r in result["dated"] + result["undated"]}
    assert by_id["signal-a"]["is_fallback_date"] is True
    assert by_id["signal-a"]["date_basis"] == "evidence_published_date"
    assert by_id["signal-b"]["date"] == ""


def test_sparse_entity_zero_events():
    entities = _entities()
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={},
    )
    assert result["has_any"] is False
    assert result["dated_count"] == 0
    assert result["undated_count"] == 0


# --- Geography parity ------------------------------------------------------


def test_geography_detail_includes_intelligence_timeline_peru():
    entities = main.entity_index()
    evidence = main.published_evidence()
    geo = geography_detail(
        GEO_RICH,
        entities=entities,
        relationships=main.all_relationships(),
        published_evidence=evidence,
        signals=main.all_signals(),
        assessments=main.all_assessments(),
        berry_labels=main.BERRIES,
        entity_facts=main.facts_for_entity(GEO_RICH),
        entity_relationships=main.relationships_for_entity(GEO_RICH, main.all_relationships()),
        evidence_idx={r["id"]: r for r in evidence if r.get("id")},
    )
    assert geo is not None
    timeline = geo["intelligence_timeline"]
    assert timeline["has_any"] is True
    assert timeline["dated_count"] >= 1
    dates = [row["date"] for row in timeline["dated"]]
    assert dates == sorted(dates, reverse=True)
    assert all(row.get("date_basis") != "captured_date" for row in timeline["dated"] + timeline["undated"])


def test_geography_route_renders_timeline_section():
    page = client.get(f"/geographies/{GEO_RICH}")
    assert page.status_code == 200
    assert 'id="intelligence-timeline"' in page.text
    assert "Intelligence timeline" in page.text


def test_geography_sparse_timeline_honest_empty():
    page = client.get(f"/geographies/{GEO_SPARSE}")
    assert page.status_code == 200
    assert 'id="intelligence-timeline"' in page.text
    # Zambia has no published-date chronology; undated trusted items (if any)
    # stay in the undated bucket rather than being fabricated into history.
    assert "0 dated item" in page.text
    assert "(recorded date)" not in page.text or "Undated" in page.text


def test_company_and_variety_profiles_still_render_timeline():
    company = client.get(f"/entities/company/{COMPANY_WITH_EVIDENCE}")
    assert company.status_code == 200
    assert 'id="intelligence-timeline"' in company.text
    variety = client.get(f"/entities/variety/{VARIETY_WITH_EVIDENCE}")
    assert variety.status_code == 200
    assert 'id="intelligence-timeline"' in variety.text


# --- Trust / watch / body fidelity -----------------------------------------


def test_geography_get_does_not_mark_watch_seen(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    watchlist_mod.add_watch(tmp_path, "geography", GEO_RICH)
    watches = load_watches(tmp_path)
    watches[0]["last_seen_at"] = "2026-01-01T00:00:00Z"
    watchlist_mod._write(tmp_path, watches)
    before = load_watches(tmp_path)[0]["last_seen_at"]
    assert client.get(f"/geographies/{GEO_RICH}").status_code == 200
    after = load_watches(tmp_path)[0]["last_seen_at"]
    assert after == before
    assert is_watched(tmp_path, "geography", GEO_RICH) is True


def test_timeline_get_does_not_mutate_trusted_evidence_bytes():
    # Pick one Peru-linked evidence file and ensure GET leaves it untouched.
    sample = None
    for path in (ROOT / "data" / "evidence").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if GEO_RICH in (data.get("geography_ids") or []) and data.get("status") == "published":
            sample = path
            break
    assert sample is not None
    before = sample.read_bytes()
    mtime = sample.stat().st_mtime_ns
    assert client.get(f"/geographies/{GEO_RICH}").status_code == 200
    assert sample.read_bytes() == before
    assert sample.stat().st_mtime_ns == mtime


def test_timeline_does_not_duplicate_transcript_or_article_bodies():
    page = client.get(f"/geographies/{GEO_RICH}")
    assert "transcript_body" not in page.text
    assert "full_text" not in page.text


def test_geography_live_page_has_no_private_watch_newness_badge_copy():
    page = client.get(f"/geographies/{GEO_RICH}")
    # Watchlist newness is /watches only; profile must not invent new-since badges.
    assert "new since last check" not in page.text.lower()
    assert "mark seen" not in page.text.lower()
