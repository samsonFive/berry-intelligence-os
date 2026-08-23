"""Atomic Evidence workbench tests use only synthetic temporary records."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.review_workbench import build_review_workbench, format_locator, timestamp_source_url


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _setup(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-workbench", "name": "Synthetic Podcast"})
    parent = {
        "id": "ev-workbench-parent", "record_type": "evidence", "status": "published",
        "review_state": "published", "source_type": "industry_podcast",
        "title": "Synthetic Episode 12", "source_name": "Synthetic Podcast",
        "source_url": "https://www.youtube.com/watch?v=fixture", "source_id": "source-workbench",
        "published_date": "2026-08-01", "captured_date": "2026-08-02",
        "summary": "Synthetic parent fixture.", "submitted_by": "fixture",
        "evidence_role": "publication_artifact", "media_format": "podcast",
        "priority": deepcopy(PRIORITY),
    }
    repos.evidence.create(parent)
    entities = [
        {"id": "company-workbench", "record_type": "entity", "entity_type": "company", "name": "Synthetic Company", "status": "active"},
        {"id": "geography-workbench", "record_type": "entity", "entity_type": "geography", "name": "Synthetic Region", "status": "active"},
        {"id": "berry-blueberry", "record_type": "entity", "entity_type": "berry", "name": "Blueberry", "status": "active"},
    ]
    for entity in entities:
        repos.entities.create(entity)
    statements = ["A duplicated synthetic claim.", "A duplicated synthetic claim."] + [
        f"Synthetic atomic claim {index}." for index in range(3, 11)
    ]
    for index, statement in enumerate(statements, start=1):
        start = [300, 295][index - 1] if index <= 2 else index * 60
        draft = {
            "id": f"ev-workbench-{index}", "record_type": "evidence", "status": "draft",
            "review_state": "in_review", "intake_type": "article_or_url",
            "source_type": "industry_podcast", "source_name": "Synthetic Podcast",
            "source_url": parent["source_url"], "published_date": "2026-08-01",
            "captured_date": "2026-08-02", "title": statement, "summary": statement,
            "why_it_matters": "", "submitted_by": "synthetic extractor",
            "source_id": "source-workbench", "evidence_role": "atomic_evidence",
            "parent_evidence_id": parent["id"],
            "artifact_locator": {
                "start_seconds": start, "end_seconds": start + 20,
                **({"speaker_label": "Speaker A"} if index == 3 else {}),
            },
            "transcript_excerpt": f"Exact synthetic transcript support {index}.",
            "entity_ids": ["company-workbench", "geography-workbench"] if index == 3 else [],
            "geography_ids": ["geography-workbench"] if index == 3 else [],
            "berry_ids": ["berry-blueberry"] if index == 3 else [],
            "extraction_provenance": {
                "method": "ai_assisted", "extracted_by": "synthetic-provider",
                "extracted_at": "2026-08-02", "provider": "openai-compatible",
                "model": "synthetic-model", "prompt_version": "atomic-ci-v1",
            },
            "transcript_provenance": {
                "transcript_id": "transcript-workbench", "transcript_sha256": "a" * 64,
                "language": "en", "method": "auto_generated", "created_by": "synthetic-transcriber",
                "created_at": "2026-08-02", "segment_indexes": [index],
            },
            "suggested_competitors": [], "suggested_varieties": [], "attachments": [],
        }
        main.save_draft(draft)
    generic = {
        "id": "ev-generic-draft", "record_type": "evidence", "status": "draft",
        "intake_type": "article_or_url", "source_type": "article", "source_name": "Synthetic Journal",
        "source_url": "https://example.invalid/article", "captured_date": "2026-08-02",
        "title": "Synthetic article draft", "summary": "Ordinary Evidence fixture.",
        "why_it_matters": "", "submitted_by": "fixture", "suggested_competitors": [],
        "suggested_varieties": [], "attachments": [],
    }
    main.save_draft(generic)
    return repos, parent


def _workbench(repos, **filters):
    return build_review_workbench(
        drafts=main.list_drafts(), evidence=repos.evidence.list(), sources=repos.sources.list(),
        entities=repos.entities.list(), berry_labels=main.BERRIES, filters=filters,
    )


def test_batch_composition_resolves_parent_sorts_and_flags_duplicates(monkeypatch, tmp_path: Path) -> None:
    repos, _ = _setup(monkeypatch, tmp_path)
    view = _workbench(repos)
    assert len(view["groups"]) == 1
    group = view["groups"][0]
    assert group["parent"]["title"] == "Synthetic Episode 12"
    assert group["source_label"] == "Synthetic Podcast"
    assert group["progress"] == {"total": 10, "approved": 0, "rejected": 0, "remaining": 10, "reviewed": 0}
    ordered_ids = [card["record"]["id"] for card in group["cards"]]
    assert ordered_ids == ["ev-workbench-3", "ev-workbench-4", "ev-workbench-2", "ev-workbench-1", "ev-workbench-5", "ev-workbench-6", "ev-workbench-7", "ev-workbench-8", "ev-workbench-9", "ev-workbench-10"]
    duplicate_card = next(card for card in group["cards"] if card["record"]["id"] == "ev-workbench-1")
    assert duplicate_card["duplicate_warnings"][0]["reason"] == "same normalized statement and overlapping transcript span"
    assert format_locator({"start_seconds": 750, "end_seconds": 790}) == "12:30–13:10"
    assert timestamp_source_url("https://youtu.be/fixture", 750).endswith("?t=750")
    assert timestamp_source_url("https://example.invalid/podcast", 750) is None


def test_context_links_provenance_filters_and_generic_regression(monkeypatch, tmp_path: Path) -> None:
    repos, _ = _setup(monkeypatch, tmp_path)
    view = _workbench(repos, berry="berry-blueberry", geography="geography-workbench", model="synthetic-model", version="atomic-ci-v1")
    cards = view["groups"][0]["cards"]
    assert [card["record"]["id"] for card in cards] == ["ev-workbench-3"]
    card = cards[0]
    assert card["speaker_label"] == "Speaker A"
    assert [item["name"] for item in card["entities"]] == ["Synthetic Company"]
    assert [item["name"] for item in card["geographies"]] == ["Synthetic Region"]
    assert card["extraction"]["prompt_version"] == "atomic-ci-v1"
    assert _workbench(repos, kind="atomic")["generic_drafts"] == []
    assert [item["id"] for item in _workbench(repos, kind="all")["generic_drafts"]] == ["ev-generic-draft"]
    generic = main.get_draft("ev-generic-draft")
    generic["status"] = generic["review_state"] = "rejected"
    main.save_draft(generic)
    assert _workbench(repos)["generic_drafts"] == []
    assert [item["id"] for item in _workbench(repos, state="rejected")["generic_drafts"]] == ["ev-generic-draft"]


def test_workbench_renders_grounding_actions_and_safe_keyboard_handlers(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    response = TestClient(app).get("/review?kind=atomic")
    assert response.status_code == 200
    text = response.text
    assert "Claim review" in text
    assert "Exact synthetic transcript support 3." in text and 'class="transcript-support"' in text
    assert "5:00–5:20" in text and "Speaker A" in text
    assert "Synthetic Company" in text and "Synthetic Region" in text
    assert "synthetic-model" in text and "atomic-ci-v1" in text
    assert "Surrounding context is not persisted" in text
    assert "confirm_individual_review" in text
    assert 'input, textarea, select, button, [contenteditable="true"]' in text
    assert "Synthetic article draft" not in text


def test_individual_approve_reject_progress_and_position(monkeypatch, tmp_path: Path) -> None:
    repos, parent_before = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    approved = client.post(
        "/review/ev-workbench-1/approve-atomic",
        data={"reviewer": "human-a", "confirm_individual_review": "true", "return_to": "/review?parent=ev-workbench-parent&current=ev-workbench-2"},
        follow_redirects=False,
    )
    rejected = client.post(
        "/review/ev-workbench-2/reject",
        data={"reviewer": "human-b", "rejection_category": "duplicate", "rejection_reason": "Duplicate synthetic claim.", "return_to": "/review?parent=ev-workbench-parent&current=ev-workbench-3"},
        follow_redirects=False,
    )
    assert approved.status_code == rejected.status_code == 303
    assert approved.headers["location"].endswith("current=ev-workbench-2")
    assert rejected.headers["location"].endswith("current=ev-workbench-3")
    assert repos.evidence.get("ev-workbench-1")["reviewed_by"] == "human-a"
    assert main.get_draft("ev-workbench-2")["rejection_category"] == "duplicate"
    assert main.get_draft("ev-workbench-3")["review_state"] == "in_review"
    assert repos.evidence.get(parent_before["id"]) == parent_before
    assert repos.facts.list() == [] and repos.relationships.list() == []
    view = _workbench(repos)
    assert view["groups"][0]["progress"] == {"total": 10, "approved": 1, "rejected": 1, "remaining": 8, "reviewed": 2}
    pending_ids = {card["record"]["id"] for card in view["groups"][0]["cards"]}
    assert "ev-workbench-1" not in pending_ids and "ev-workbench-2" not in pending_ids


def test_edit_approve_preserves_lineage_excerpt_and_original_statement(monkeypatch, tmp_path: Path) -> None:
    repos, parent_before = _setup(monkeypatch, tmp_path)
    response = TestClient(app).post(
        "/review/ev-workbench-3/publish",
        data={
            "title": "Ignored atomic title", "source_type": "industry_podcast",
            "source_name": "Synthetic Podcast", "source_url": "https://www.youtube.com/watch?v=fixture",
            "published_date": "2026-08-01", "captured_date": "2026-08-02",
            "summary": "Human-corrected synthetic atomic claim.", "companies": "Synthetic Company",
            "geographies": "Synthetic Region", "berries": ["berry-blueberry"], "reviewer": "human-editor",
            "return_to": "/review?parent=ev-workbench-parent&current=ev-workbench-4",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303 and response.headers["location"].endswith("current=ev-workbench-4")
    record = repos.evidence.get("ev-workbench-3")
    assert record["summary"] == "Human-corrected synthetic atomic claim."
    assert record["transcript_excerpt"] == "Exact synthetic transcript support 3."
    assert record["artifact_locator"]["start_seconds"] == 180
    assert record["review_outcome"] == {
        "decision": "approved", "edited_before_approval": True,
        "original_normalized_statement": "Synthetic atomic claim 3.",
    }
    assert set(record["entity_ids"]) == {"company-workbench", "geography-workbench"}
    assert repos.evidence.get(parent_before["id"]) == parent_before
    assert repos.facts.list() == [] and repos.relationships.list() == []


def test_external_return_url_is_rejected_and_missing_confirmation_cannot_approve(monkeypatch, tmp_path: Path) -> None:
    repos, _ = _setup(monkeypatch, tmp_path)
    client = TestClient(app)
    missing_confirmation = client.post(
        "/review/ev-workbench-4/approve-atomic", data={"reviewer": "human"}, follow_redirects=False
    )
    assert missing_confirmation.status_code == 400
    rejected = client.post(
        "/review/ev-workbench-4/reject",
        data={"reviewer": "human", "rejection_category": "other", "rejection_reason": "Synthetic rejection.", "return_to": "https://evil.invalid/"},
        follow_redirects=False,
    )
    assert rejected.status_code == 303 and rejected.headers["location"] == "/review"
    assert repos.evidence.get("ev-workbench-4") is None
    assert main.get_draft("ev-workbench-4")["review_state"] == "rejected"


def test_source_says_and_system_proposes_stay_distinct(monkeypatch, tmp_path: Path) -> None:
    repos, parent = _setup(monkeypatch, tmp_path)
    evidence = repos.evidence.list()
    for record in evidence:
        if record["id"] == parent["id"]:
            record["article"] = {"body": "HUGE_PARENT_BODY " * 50}
    view = build_review_workbench(
        drafts=main.list_drafts(),
        evidence=evidence,
        sources=repos.sources.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        filters={"kind": "atomic"},
    )
    group = view["groups"][0]
    assert "HUGE_PARENT_BODY" not in str(group["parent"])
    assert group["parent"].get("has_article_body") is True
    card = next(item for item in group["cards"] if item["record"]["id"] == "ev-workbench-3")
    assert card["source_says"] == card["excerpt"] == "Exact synthetic transcript support 3."
    assert card["statement"] == "Synthetic atomic claim 3."
    assert card["source_says"] != card["statement"]
    assert card["speaker_label"] == "Speaker A"
    assert card["locator_kind"] == "timestamp"
    assert "Does not auto-create Facts or Relationships" in card["if_approved"]


def test_rich_source_batch_registry_transcript_and_deep_links(monkeypatch, tmp_path: Path) -> None:
    repos, parent = _setup(monkeypatch, tmp_path)
    for variety_id, name in (
        ("variety-redsayra", "RedSayra"),
        ("variety-bluemaldiva", "Blue Maldiva"),
        ("variety-pinkhudson", "Pink Hudson"),
    ):
        repos.entities.create(
            {"id": variety_id, "record_type": "entity", "entity_type": "variety", "name": name, "status": "active"}
        )
    traits = [
        ("variety-redsayra", "precocity"),
        ("variety-redsayra", "firmness"),
        ("variety-bluemaldiva", "size"),
        ("variety-pinkhudson", "flavor"),
        ("variety-pinkhudson", "shelf life"),
    ]
    seed = main.get_draft("ev-workbench-3")
    for index, (variety_id, trait) in enumerate(traits, start=11):
        main.save_draft(
            {
                **seed,
                "id": f"ev-workbench-{index}",
                "title": f"{trait} proposal",
                "summary": f"System proposes {trait}.",
                "transcript_excerpt": f"Retailers mentioned {trait}.",
                "entity_ids": [variety_id],
                "artifact_locator": {"start_seconds": 800 + index, "end_seconds": 820 + index, "speaker_label": "Host"},
                "does_not_prove": ["universal variety property"],
            }
        )
    main.save_draft(
        {
            **seed,
            "id": "ev-registry-1",
            "source_type": "cpvo_filing",
            "title": "CPVO application for denomination",
            "summary": "Filing names an applicant and a proposed denomination.",
            "transcript_excerpt": "Application received; grant not issued.",
            "artifact_locator": {"paragraph_index": 0},
            "attribution": {"kind": "registry_government", "publisher": "CPVO"},
            "does_not_prove": ["commercialization", "granted rights", "acreage"],
            "entity_ids": ["variety-redsayra"],
        }
    )
    view = _workbench(repos, kind="atomic", parent=parent["id"])
    group = view["groups"][0]
    assert group["progress"]["total"] >= 16
    assert group["progress"]["remaining"] >= 16
    registry_card = next(card for card in group["cards"] if card["record"]["id"] == "ev-registry-1")
    assert registry_card["locator_kind"] == "paragraph"
    assert registry_card["locator_label"] == "Paragraph 1"
    assert "commercialization" in registry_card["does_not_prove"]
    assert registry_card["attribution_kind"] == "registry_government"
    client = TestClient(app)
    batch = client.get(f"/review/batch/{parent['id']}", follow_redirects=False)
    assert batch.status_code == 302
    assert "kind=atomic" in batch.headers["location"] and parent["id"] in batch.headers["location"]
    page = client.get(f"/review?kind=atomic&parent={parent['id']}")
    assert page.status_code == 200
    assert "Source says" in page.text and "System proposes" in page.text
    assert "Does not prove" in page.text
    assert "Approve all" not in page.text
    saved = client.post(
        "/review/ev-workbench-5/save",
        data={"title": "Corrected title", "summary": "Corrected statement", "return_to": "/review?kind=atomic"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert repos.evidence.get("ev-workbench-5") is None
    assert main.get_draft("ev-workbench-5")["summary"] == "Corrected statement"


def test_queue_composition_stays_bounded_at_5000_proposals(monkeypatch, tmp_path: Path) -> None:
    repos, parent = _setup(monkeypatch, tmp_path)
    drafts = []
    for index in range(5000):
        drafts.append(
            {
                "id": f"ev-scale-{index}",
                "evidence_role": "atomic_evidence",
                "status": "draft",
                "parent_evidence_id": parent["id"],
                "title": f"scale {index}",
                "summary": f"scale {index}",
                "transcript_excerpt": f"excerpt {index}",
                "artifact_locator": {"start_seconds": index},
                "extraction_provenance": {"model": "synthetic-model", "prompt_version": "atomic-ci-v1"},
            }
        )
    parent_record = {**parent, "article": {"body": "PARENT_ARTICLE_BODY"}}
    import time

    started = time.perf_counter()
    view = build_review_workbench(
        drafts=drafts,
        evidence=[parent_record],
        sources=repos.sources.list(),
        entities=repos.entities.list(),
        berry_labels=main.BERRIES,
        filters={"kind": "atomic"},
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 8
    group = view["groups"][0]
    assert group["progress"]["total"] == 5000
    assert "PARENT_ARTICLE_BODY" not in str(group["parent"])
    assert group["cards"][0]["source_says"].startswith("excerpt")
    assert "article" not in group["parent"]
