"""Cutover writers retain one source record through discovery and review."""
from datetime import date
import json
import pytest

from fastapi.testclient import TestClient

from app import main
from app.services import information_storage as storage
from app.services.feed_first_live import save_bundle, load_cached_bundle
from app.services.personal_digest import retained_news
from tests.test_media_orchestration import _setup, _transcript, _item, _write_item
from tests.test_review_publish_portability import _draft, _publish, SOURCE_ID


def activate(data, inbox):
    data, inbox = data.resolve(), inbox.resolve()
    root = data / "information"
    (root / "records").mkdir(parents=True)
    inbox.mkdir(parents=True)
    storage.atomic_json(root / "store.json", {"version": 1, "state": "active", "store_root": str(root),
                        "data_dir": str(data), "inbox_dir": str(inbox)})
    storage.atomic_json(inbox / ".information-store.json", {"version": 1, "store_root": str(root), "inbox_dir": str(inbox)})


def test_daily_cache_retains_references_and_never_downgrades_review(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    activate(data, inbox)
    row = {"id": "live-single-source", "title": "Initial source", "source_url": "https://example.test/source", "summary": "Stored wording",
           "article": {"full_text": "PRIVATE FULL SOURCE BODY"},
           "ai_enrichment": {"concise_summary": "Compact source summary", "why_it_matters": "Compact relevance explanation",
                             "raw_model_response": "PRIVATE MODEL PAYLOAD", "model_provenance": {"status": "ok", "raw": "PRIVATE PROVIDER DETAIL"}}}
    bundle = {"today": "2026-11-15", "records": [row], "rotating_records": [row]}
    path = save_bundle(inbox, bundle)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["records_ids"] == envelope["rotating_records_ids"] == [row["id"]]
    assert "records" not in envelope and "rotating_records" not in envelope
    storage.upsert_record({**storage.get_record(row["id"], inbox_dir=inbox), "title": "Reviewed wording", "status": "published",
                           "information": {"review_status": "reviewed", "confidence": "medium"}}, inbox_dir=inbox, allow_review_update=True)
    save_bundle(inbox, bundle)
    reloaded = load_cached_bundle(inbox, today=date(2026, 11, 15))["records"][0]
    assert reloaded["title"] == "Reviewed wording"
    assert reloaded["information"]["review_status"] == "reviewed"
    assert reloaded["ai_enrichment"]["concise_summary"] == "Compact source summary"
    assert "PRIVATE FULL SOURCE BODY" not in str(reloaded)
    assert "PRIVATE MODEL PAYLOAD" not in str(reloaded) and "PRIVATE PROVIDER DETAIL" not in str(reloaded)
    assert retained_news(inbox)[0]["status"] == "published"
    assert len(list((data / "information" / "records").glob("*.json"))) == 1
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()


def test_captured_unreviewed_source_can_reach_extraction_without_review(tmp_path):
    activate(tmp_path / "data", tmp_path / "inbox")
    service, repos, inbox, adapter = _setup(tmp_path, transcript=_transcript())
    item = _item()
    _write_item(inbox, item)
    result = service.process(item["id"])
    assert result.state == "ready_for_extraction"
    assert adapter.calls == 1
    parent = storage.get_record(result.parent_resolution.evidence_id, inbox_dir=inbox)
    assert parent["status"] == "draft"
    assert parent["information"]["review_status"] == "unreviewed"
    assert parent["publication_scope"] == "private"
    assert repos.evidence.list(status="published", publication_scope="public") == []
    assert not (inbox / "evidence").exists()


@pytest.mark.parametrize("cached_id", [False, True])
def test_optional_review_updates_same_private_record_without_moving_or_deleting(tmp_path, monkeypatch, cached_id):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    activate(data, inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Fixture source"})
    from tests.test_review_publish_portability import _item as review_item
    draft = _draft(review_item())
    if cached_id:
        draft.update(id="live-cached-review-source", status="unreviewed", live=True)
    draft["information_confidence"] = "low"
    draft["custom_source_metadata"] = {"preserve": "original source notes"}
    path = storage.upsert_record(draft, inbox_dir=inbox)
    client = TestClient(main.app)
    response = _publish(client, draft["id"])
    assert response.status_code == 303
    reviewed = storage.get_record(draft["id"], inbox_dir=inbox)
    assert path.is_file()
    assert reviewed["id"] == draft["id"]
    assert reviewed["publication_scope"] == "private"
    assert reviewed["information"]["review_status"] == "reviewed"
    assert reviewed["information_confidence"] == "low"
    assert reviewed["custom_source_metadata"] == draft["custom_source_metadata"]
    assert repos.evidence.list(status="published", publication_scope="public") == []
    assert len(list(path.parent.glob("*.json"))) == 1
    assert not (data / "evidence").exists() and not (inbox / "evidence").exists()
    candidate = reviewed["pending_claim"]["candidate_statement"]
    confirmation = client.post(f"/review/{draft['id']}/claim/approve", data={
        "statement": candidate, "proposed_statement": candidate, "reviewer": "fixture reviewer"}, follow_redirects=False)
    assert confirmation.status_code == 303
    assert repos.facts.list()[0]["publication_scope"] == "private"


def test_injected_extractor_keeps_parent_and_child_unreviewed_in_same_store(tmp_path):
    activate(tmp_path / "data", tmp_path / "inbox")
    service, repos, inbox, _ = _setup(tmp_path, transcript=_transcript(), extraction=True,
        candidates=[{"normalized_statement": "The trial may expand.", "segment_indexes": [1]}])
    item = _item()
    _write_item(inbox, item)
    result = service.process(item["id"])
    assert result.state == "extraction_complete"
    assert result.extraction["accepted"] == 1
    rows = storage.list_records(inbox_dir=inbox)
    assert len(rows) == 2
    child = next(row for row in rows if row.get("evidence_role") == "atomic_evidence")
    parent = next(row for row in rows if row.get("evidence_role") == "publication_artifact")
    assert child["parent_evidence_id"] == parent["id"]
    assert child["transcript_provenance"]["transcript_sha256"] == result.transcript_sha256
    assert all(row["publication_scope"] == "private" and row["information"]["review_status"] == "unreviewed" for row in rows)
    assert service.process(item["id"]).extraction["duplicates"] == 1
    assert repos.facts.list() == []
    assert not (inbox / "evidence").exists() and not (tmp_path / "data" / "evidence").exists()


def test_failed_source_review_restores_the_same_authoritative_record(tmp_path, monkeypatch):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    activate(data, inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    repos = main.get_repositories(data, main.SCHEMAS_DIR)
    repos.sources.create({"id": SOURCE_ID, "name": "Fixture source"})
    from tests.test_review_publish_portability import _item as review_item
    draft = _draft(review_item())
    path = storage.upsert_record(draft, inbox_dir=inbox)
    before = path.read_bytes()
    def unavailable_ledger(*args, **kwargs):
        raise RuntimeError("synthetic ledger failure after the source update")
    monkeypatch.setattr("app.services.review_publish.append_review_event", unavailable_ledger)
    response = _publish(TestClient(main.app, raise_server_exceptions=False), draft["id"])
    assert response.status_code == 500
    assert path.read_bytes() == before
    assert len(list(path.parent.glob("*.json"))) == 1
    assert repos.facts.list() == []


def test_article_capture_keeps_full_body_in_authoritative_source(tmp_path, monkeypatch):
    from app.services import article_acquisition
    from app.services.article_refresh import process_discovered_article
    from tests.test_article_refresh import _FakeArticleResponse, _RELEVANT_HTML
    activate(tmp_path / "data", tmp_path / "inbox")
    service, _, inbox, _ = _setup(tmp_path)
    item = _item(media_format="web_article", title="Blueberry acreage grows in Peru",
                 description="Blueberry acreage update from Peru.")
    _write_item(inbox, item)
    monkeypatch.setattr(article_acquisition.httpx, "get", lambda *args, **kwargs: _FakeArticleResponse(_RELEVANT_HTML))
    result, extra = process_discovered_article(item, orchestrator=service, inbox_dir=inbox)
    assert extra["acquired"] is True
    assert result.publication_draft_id
    record = storage.get_record(result.publication_draft_id, inbox_dir=inbox)
    assert record["article"]["word_count"] > 0
    assert "Peru" in " ".join(row["text"] for row in record["article"]["paragraphs"])
    assert record["information"]["review_status"] == "unreviewed"
    assert record["publication_scope"] == "private"
    assert not (inbox / "evidence").exists()


def test_command_review_preserves_existing_source_assets_and_private_scope(tmp_path):
    from tests.test_publication_review_command import Harness, _readable_draft, domain
    activate(tmp_path / "data", tmp_path / "inbox")
    harness = Harness(tmp_path)
    draft = _readable_draft(status="draft", evidence_role="publication_artifact",
                             attachments=[{"filename": "source.pdf", "path": "information/assets/source.pdf"}])
    storage.upsert_record(draft, inbox_dir=harness.inbox_dir)
    harness.seed(draft)
    result = harness.service.approve_publication(harness.envelope(draft["id"]), approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.publication_id == draft["id"]
    record = storage.get_record(draft["id"], inbox_dir=harness.inbox_dir)
    assert record["attachments"] == draft["attachments"]
    assert record["publication_scope"] == "private"
    assert record["information"]["review_status"] == "reviewed"
    assert len(storage.list_records(inbox_dir=harness.inbox_dir)) == 1
    assert not list((harness.data_dir / "evidence").glob("*.json"))
