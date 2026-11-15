"""Review does not gate membership, ranking or reader access in the live catalog."""
from copy import deepcopy
import json

from app.services.information_catalog import information_flags, load_information, merge_information


def record(key, status="draft", **extra):
    return {"id": key, "title": "Blueberry harvest " + key, "status": status,
            "summary": "A blueberry grower expands harvest.", "source_type": "trade_press",
            "source_url": "https://example.org/" + key, "published_date": "2026-11-12",
            "record_type": "evidence", "evidence_role": "publication_artifact", **extra}


def test_union_keeps_review_and_confidence_independent_and_does_not_mutate():
    reviewed = record("ev-reviewed", "published")
    unreviewed = record("ev-unreviewed", information_confidence="high")
    original = deepcopy([reviewed, unreviewed])
    rows = merge_information([reviewed], [unreviewed])
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {"ev-reviewed", "ev-unreviewed"}
    assert by_id["ev-unreviewed"]["information"]["confidence"] == "high"
    assert by_id["ev-unreviewed"]["information"]["review_status"] == "unreviewed"
    assert by_id["ev-reviewed"]["information"]["confidence"] is None
    assert [reviewed, unreviewed] == original


def test_canonical_identity_and_terminal_decisions_win_over_older_caches():
    rows = merge_information([record("ev-same", "published"), record("ev-rejected", "rejected")],
                             [record("ev-same"), record("ev-rejected")])
    assert [row["id"] for row in rows] == ["ev-same"]
    assert rows[0]["status"] == "published"
    assert rows[0]["_catalog_origin"] == "data"


def test_same_identity_preview_image_survives_without_replacing_canonical_prose():
    cached = record("ev-image", "unreviewed", image_url="https://example.org/preview.jpg", summary="Cached wording")
    canonical = record("ev-image", "published", summary="Canonical wording")
    row = merge_information([canonical], [cached])[0]
    assert row["image_url"] == cached["image_url"]
    assert row["summary"] == "Canonical wording"
    assert row["information"]["review_status"] == "reviewed"
    different_url = {**cached, "source_url": "https://example.org/a-different-source"}
    assert "image_url" not in merge_information([canonical], [different_url])[0]


def test_auto_captured_publication_does_not_imply_review_or_confidence():
    flags = information_flags(record("ev-auto", "published", auto_captured=True,
                                      validated=False, verification_state="disputed",
                                      does_not_prove=["Commercial success"]))
    assert flags["review_status"] == "unreviewed"
    assert flags["confidence_label"] == "Not assessed"
    assert flags["verification_status"] == "disputed"
    assert flags["caveats"] == ["Commercial success"]


def test_retained_web_status_does_not_inherit_supplied_review_flags():
    flags = information_flags(record("ev-cached", "unreviewed", review_state="published",
                                      information={"review_status": "reviewed"}))
    assert flags["review_status"] == "unreviewed"


def test_loader_includes_all_intake_kinds_without_hydrating_bodies(tmp_path):
    folder = tmp_path / "evidence"
    folder.mkdir()
    publication = record("ev-source", article={"paragraphs": [{"text": "PRIVATE FULL ARTICLE"}]},
                         information_confidence="medium")
    atomic = record("ev-claim", evidence_role="atomic_evidence", statement="Source reports a harvest change")
    for row in (publication, atomic, record("ev-rejected", "rejected")):
        (folder / (row["id"] + ".json")).write_text(json.dumps(row), encoding="utf-8")
    before = {path: path.read_bytes() for path in folder.iterdir()}
    rows = load_information([record("ev-existing", "published")], tmp_path)
    assert {row["id"] for row in rows} == {"ev-source", "ev-claim", "ev-existing"}
    assert all("article" not in row for row in rows)
    assert next(row for row in rows if row["id"] == "ev-source")["information"]["confidence"] == "medium"
    assert {path: path.read_bytes() for path in folder.iterdir()} == before
    assert [row["id"] for row in load_information([record("ev-existing", "published")], tmp_path, include_private=False)] == ["ev-existing"]


def test_catalog_request_cache_does_not_hide_new_records_next_request(tmp_path):
    from app.services.request_corpus import RequestCorpus
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    folder = inbox / "evidence"
    folder.mkdir(parents=True)
    first = RequestCorpus(data, tmp_path / "schemas", inbox)
    assert first.information == []
    (folder / "ev-new.json").write_text(json.dumps(record("ev-new")), encoding="utf-8")
    assert first.information == []
    second = RequestCorpus(data, tmp_path / "schemas", inbox)
    assert [row["id"] for row in second.information] == ["ev-new"]


def test_active_authoring_inventory_uses_body_free_previews_and_preserves_selected_source(tmp_path, monkeypatch):
    from app.repositories.json.evidence import EvidenceRepository
    from app.repositories.paths import SCHEMAS_DIR
    from app.services import association_corrections, information_migration, information_storage
    from app.services.request_corpus import RequestCorpus
    from tests.test_information_storage_migration import write

    data, inbox = tmp_path / "data", tmp_path / "inbox"
    private = record("ev-private", article={"paragraphs": [{"text": "FULL ARTICLE CANARY"}]},
        transcript={"status": "captured", "text": "FULL TRANSCRIPT CANARY"},
        provider_response={"body": "PRIVATE PROVIDER CANARY"}, entity_ids=["company-old"],
        ai_enrichment={"concise_summary": "Compact source preview", "raw_response": "RAW MODEL CANARY",
                       "model_provenance": {"provider": "fixture", "request_body": "PRIVATE REQUEST CANARY"}})
    write(data / "evidence/ev-public.json", record("ev-public", "published"))
    write(inbox / "evidence/ev-private.json", private)
    write(inbox / "evidence/ev-claim.json", record("ev-claim", evidence_role="atomic_evidence",
                                                    statement="A source claim remains available."))
    write(inbox / "evidence/ev-rejected.json", record("ev-rejected", "rejected"))
    information_migration.apply_migration(data, inbox, tmp_path / "backups", quiesced=True)
    stored = information_storage.get_record("ev-private", data_dir=data)
    information_storage.write_record({**stored, "status": "published", "information": {
        "review_status": "reviewed", "confidence": "medium"}}, data_dir=data)
    corrections = [{"id": "correction-fixture", "record_id": "ev-private", "field": "entity_ids",
                    "entity_id": "company-old", "action": "exclude"},
                   {"id": "correction-fixture-add", "record_id": "ev-private", "field": "entity_ids",
                    "entity_id": "company-correct", "action": "include"}]
    monkeypatch.setattr(association_corrections, "load", lambda _inbox: corrections)

    def prohibit_full_inventory(*_args, **_kwargs):
        raise AssertionError("authoring inventory must not load full Evidence records")

    monkeypatch.setattr(EvidenceRepository, "list", prohibit_full_inventory)
    before = {path: path.read_bytes() for path in (data / "information/records").glob("*.json")}
    corpus = RequestCorpus(data, SCHEMAS_DIR, inbox, include_workspace_corrections=True)
    rows = corpus.information
    assert rows is corpus.information
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {"ev-public", "ev-private", "ev-claim"}
    preview = by_id["ev-private"]
    assert preview["publication_scope"] == "private"
    assert preview["information"]["review_status"] == "reviewed"
    assert preview["information"]["confidence"] == "medium"
    assert preview["entity_ids"] == ["company-correct"]
    assert preview["ai_enrichment"]["concise_summary"] == "Compact source preview"
    assert preview["transcript_status"] == "captured"
    assert "CANARY" not in json.dumps(rows)
    assert all("article" not in row and "transcript" not in row and "provider_response" not in row for row in rows)
    assert corpus._evidence is None
    selected = corpus.repos().evidence.get("ev-private")
    assert selected["article"] == private["article"]
    assert selected["transcript"] == private["transcript"]
    assert selected["provider_response"] == private["provider_response"]
    assert selected["entity_ids"] == ["company-old"]
    assert {path: path.read_bytes() for path in before} == before


def test_feed_ranking_uses_content_and_date_without_review_gate():
    from app.services.intelligence_feed import build_intelligence_feed
    reviewed = record("ev-reviewed", "published", published_date="2026-11-11")
    unreviewed = record("ev-unreviewed", published_date="2026-11-12")
    feed = build_intelligence_feed(drafts=[], published=[], records=merge_information([reviewed], [unreviewed]),
                                   entities={}, berry_labels={})
    assert [row["id"] for row in feed["entries"]] == ["ev-unreviewed", "ev-reviewed"]


def test_api_feed_and_reader_share_unreviewed_record(tmp_path, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    folder = inbox / "evidence"
    folder.mkdir(parents=True)
    row = record("ev-available", information_confidence="low")
    (folder / (row["id"] + ".json")).write_text(json.dumps(row), encoding="utf-8")
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    with TestClient(main.app) as client:
        assert [r["id"] for r in client.get("/api/feed").json()] == [row["id"]]
        search = client.get("/api/search", params={"q": "harvest"}).json()
        assert [r["id"] for r in search["evidence"]] == [row["id"]]
    loaded = main._load_intelligence_record(row["id"])
    assert loaded["information"]["review_status"] == "unreviewed"
    assert loaded["information"]["confidence"] == "low"


def test_readonly_api_keeps_export_scope_separate_from_review_flags(tmp_path, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    for folder in (data / "evidence", inbox / "evidence"):
        folder.mkdir(parents=True)
    public = record("ev-public", "published", information={"review_status": "unreviewed"})
    for row, folder in ((public, data / "evidence"),
                        (record("ev-private-data", "in_review"), data / "evidence"),
                        (record("ev-private-inbox"), inbox / "evidence")):
        (folder / (row["id"] + ".json")).write_text(json.dumps(row), encoding="utf-8")
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    with TestClient(main.app) as client:
        assert [row["id"] for row in client.get("/api/feed").json()] == ["ev-public"]
        assert [row["id"] for row in client.get("/api/search?q=harvest").json()["evidence"]] == ["ev-public"]
    assert main._load_intelligence_record("ev-private-data") is None
    assert main._load_intelligence_record("ev-private-inbox") is None
