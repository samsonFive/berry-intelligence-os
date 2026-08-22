"""Tests for app.main.recent_intelligence_for_entity() -- the Company/Entity
"Recent Intelligence" feed added for cross-object freshness/recall.

The one hard invariant under test: include_pending=False (what
scripts/build_static.py always passes) must never surface a pending draft,
since pending drafts live in gitignored inbox/ and must never appear on the
public GitHub Pages build alongside trusted intelligence.
"""

from __future__ import annotations

from app.main import recent_intelligence_for_entity


def _trusted(id_: str, *, published_date: str | None, captured_date: str | None) -> dict:
    return {"id": id_, "title": f"Trusted {id_}", "published_date": published_date, "captured_date": captured_date}


def test_trusted_items_sort_by_published_date_descending():
    linked = [
        _trusted("ev-a", published_date="2026-08-01", captured_date="2026-08-01"),
        _trusted("ev-b", published_date="2026-08-10", captured_date="2026-08-10"),
        _trusted("ev-c", published_date="2026-08-05", captured_date="2026-08-05"),
    ]
    items = recent_intelligence_for_entity("company-x", linked_evidence=linked, include_pending=False)
    assert [item["record"]["id"] for item in items] == ["ev-b", "ev-c", "ev-a"]
    assert all(item["kind"] == "trusted" for item in items)


def test_missing_published_date_falls_back_to_captured_date_and_is_flagged():
    linked = [_trusted("ev-a", published_date=None, captured_date="2026-08-15")]
    items = recent_intelligence_for_entity("company-x", linked_evidence=linked, include_pending=False)
    assert items[0]["date"] == "2026-08-15"
    assert items[0]["date_is_published"] is False


def test_include_pending_false_never_surfaces_a_pending_draft():
    """The exact invariant scripts/build_static.py depends on."""
    linked = [_trusted("ev-a", published_date="2026-08-01", captured_date="2026-08-01")]
    items = recent_intelligence_for_entity("company-x", linked_evidence=linked, include_pending=False)
    assert all(item["kind"] != "pending" for item in items)
    assert len(items) == 1


def test_pending_and_trusted_interleave_by_recency_when_included(monkeypatch):
    import app.main as main_module

    pending_draft = {
        "id": "ev-pending-a", "title": "Pending draft",
        "published_date": "2026-08-17", "captured_date": "2026-08-18",
        "entity_ids": ["company-x"],
    }
    monkeypatch.setattr(main_module, "pending_publication_drafts", lambda: [pending_draft])

    linked = [_trusted("ev-old", published_date="2026-08-01", captured_date="2026-08-01")]
    items = recent_intelligence_for_entity("company-x", linked_evidence=linked, include_pending=True)
    assert items[0]["kind"] == "pending"
    assert items[0]["record"]["id"] == "ev-pending-a"
    assert items[1]["kind"] == "trusted"


def test_pending_about_entity_is_not_crowded_out_by_older_trusted_limit(monkeypatch):
    import app.main as main_module

    pending_draft = {
        "id": "ev-pending-hf",
        "title": "Hortifrut expands berry genetics platform",
        "published_date": "2026-07-30",
        "captured_date": "2026-08-19",
        "entity_ids": ["company-hortifrut"],
        "source_id": "source-20260819-hortifrut-newsroom",
    }
    monkeypatch.setattr(main_module, "pending_publication_drafts", lambda: [pending_draft])
    linked = [
        _trusted(f"ev-trusted-{i}", published_date="2026-08-04", captured_date="2026-08-04")
        for i in range(8)
    ]
    items = recent_intelligence_for_entity("company-hortifrut", linked_evidence=linked, include_pending=True)
    assert items[0]["kind"] == "pending"
    assert items[0]["record"]["id"] == "ev-pending-hf"
    assert sum(1 for item in items if item["kind"] == "pending") == 1


def test_pending_body_comention_is_not_treated_as_about_the_company(monkeypatch):
    import app.main as main_module

    draft = {
        "id": "ev-pending-index",
        "title": "Plant Breeders' Rights - blueberry variety index",
        "published_date": "2026-08-17",
        "summary": "The index lists Planasa among many applicants.",
        "entity_ids": [],
    }
    monkeypatch.setattr(main_module, "pending_publication_drafts", lambda: [draft])
    items = recent_intelligence_for_entity("company-planasa", linked_evidence=[], include_pending=True)
    assert items == []


def test_pending_draft_naming_a_different_entity_is_excluded(monkeypatch):
    import app.main as main_module

    other_entity_draft = {
        "id": "ev-pending-other", "title": "Not about this entity",
        "published_date": "2026-08-17", "captured_date": "2026-08-17",
        "entity_ids": ["company-someone-else"],
    }
    monkeypatch.setattr(main_module, "pending_publication_drafts", lambda: [other_entity_draft])

    items = recent_intelligence_for_entity("company-x", linked_evidence=[], include_pending=True)
    assert items == []


def test_live_entity_page_opens_recent_intelligence_in_the_reader(monkeypatch, tmp_path) -> None:
    from copy import deepcopy

    from fastapi.testclient import TestClient

    from app import main
    from app.main import app

    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.entities.create(
        {
            "id": "company-x",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Synthetic Company",
            "status": "active",
        }
    )
    priority = {
        dimension: {"level": "none", "rationale": ""}
        for dimension in ("reading", "testing", "commercial_position", "monitoring")
    }
    repos.evidence.create(
        {
            "id": "ev-trusted-x",
            "record_type": "evidence",
            "status": "published",
            "source_type": "article",
            "title": "Trusted company brief",
            "captured_date": "2026-08-01",
            "published_date": "2026-08-01",
            "summary": "Synthetic trusted fixture.",
            "submitted_by": "fixture",
            "priority": deepcopy(priority),
            "entity_ids": ["company-x"],
        }
    )
    main.save_draft(
        {
            "id": "ev-pending-x",
            "record_type": "evidence",
            "status": "draft",
            "evidence_role": "publication_artifact",
            "title": "Pending company discovery",
            "captured_date": "2026-08-18",
            "published_date": "2026-08-18",
            "entity_ids": ["company-x"],
        }
    )
    page = TestClient(app).get("/entities/company/company-x")
    assert page.status_code == 200
    assert "Recent intelligence" in page.text
    assert 'href="/intelligence/ev-trusted-x"' in page.text
    assert 'href="/intelligence/ev-pending-x"' in page.text
    assert 'href="/review/ev-pending-x"' not in page.text
    recent = page.text.split("Recent intelligence", 1)[1].split("Varieties / genetics", 1)[0]
    assert 'href="/intelligence/ev-trusted-x"' in recent
    assert 'href="/evidence/ev-trusted-x"' not in recent
