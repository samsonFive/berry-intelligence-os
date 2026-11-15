"""Application, export and seed-sync behavior after a real storage cutover."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest

from app import main
from app.repositories.json.evidence import EvidenceRepository
from app.services import information_migration as migration, information_storage as store
from app.services.request_corpus import RequestCorpus, bind_request_corpus, get_request_corpus, reset_request_corpus
from app.services.runtime_backup import create_backup, verify_backup
from scripts.sync_trusted_data import apply_safe_canonical_updates, plan_trusted_data_sync, startup_sync_trusted_data
from tests.test_information_storage_migration import record, write


def evidence(key, **changes):
    fields = {"submitted_by": "Fixture analyst", "priority": {
        axis: {"level": "none", "rationale": "Fixture source"}
        for axis in ("reading", "testing", "commercial_position", "monitoring")},
        "berry_ids": [], "entity_ids": [], "fact_ids": [], "relationship_ids": [],
        "strategic_question_ids": [], "tags": []}
    fields.update(changes)
    return record(key, **fields)


def remove_retired_empty_directories(data, inbox):
    """Make any accidental recreation by a post-cutover writer observable."""
    for root in (data, inbox):
        for name in ("evidence", "attachments"):
            folder = root / name
            if not folder.exists():
                continue
            assert not any(path.is_file() for path in folder.rglob("*"))
            for child in sorted(folder.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                child.rmdir()  # Empty directories only, all within this isolated fixture.
            folder.rmdir()


@pytest.fixture
def application_runtime(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    data, inbox = root / "data", root / "inbox"
    write(data / "evidence/ev-public.json", evidence("ev-public", status="published",
          title="Public blueberry reporting", summary="Public retained source wording.",
          parent_evidence_id="live-private", evidence_links=[{"target_evidence_id": "live-private"}]))
    write(inbox / "evidence/live-private.json", evidence("live-private", title="PRIVATE SOURCE SENTINEL",
          summary="PRIVATE SOURCE SUMMARY", article={"paragraphs": [{"text": "PRIVATE SOURCE FULL BODY"}]}))
    write(inbox / "evidence/live-draft.json", evidence("live-draft", title="PRIVATE DRAFT SENTINEL"))
    entity = {"id": "company-public", "record_type": "entity", "entity_type": "company", "status": "active",
              "name": "Public Berry Company", "aliases": [], "berry_ids": [], "roles": [],
              "evidence_ids": ["ev-public", "live-private"], "fact_ids": ["fact-public", "fact-private", "fact-mixed"],
              "attributes": {"public_note": "Visible company detail", "private_link": "/intelligence/live-private"}}
    write(data / "entities/companies/company-public.json", entity)
    for name, supports in (("public", ["ev-public"]), ("private", ["live-private"]), ("mixed", ["ev-public", "live-private"])):
        write(data / f"facts/fact-{name}.json", {"id": f"fact-{name}", "record_type": "fact", "status": "active",
              "statement": name.upper() + " FACT SENTINEL", "classification": "claim", "confidence": "medium",
              "reviewer": "Fixture analyst", "created_at": "2026-11-13", "entity_ids": [entity["id"]], "evidence_ids": supports})
    write(data / "configuration/sources.json", [])
    for parent, key, filename, body in ((data, "ev-public", "public.txt", b"public attachment"),
                                        (inbox, "live-private", "private.txt", b"PRIVATE ATTACHMENT")):
        path = parent / "attachments" / key / filename
        path.parent.mkdir(parents=True)
        path.write_bytes(body)
    migration.apply_migration(data, inbox, tmp_path / "migration-backups", quiesced=True)
    private = store.get_record("live-private", data_dir=data)
    store.write_record({**private, "status": "published", "review_state": "published", "reviewed_by": "Human reviewer",
                        "information": {"review_status": "reviewed", "confidence": "high"}}, data_dir=data)
    remove_retired_empty_directories(data, inbox)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    main._JSON_FOLDER_CACHE.clear()
    main._SEARCH_DOC_CACHE.update(key=None, docs=None)
    return SimpleNamespace(root=root, data=data, inbox=inbox, backups=tmp_path / "backups")


def test_cached_evidence_repository_follows_cutover_and_existing_record_edits(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    canonical = evidence("ev-existing", status="published")
    write(data / "evidence/ev-existing.json", canonical)
    write(inbox / "evidence/live-new.json", evidence("live-new"))
    repository = EvidenceRepository(data, main.SCHEMAS_DIR)
    assert [row["id"] for row in repository.list()] == ["ev-existing"]  # Prime the legacy folder cache.
    migration.apply_migration(data, inbox, tmp_path / "backups", quiesced=True)
    remove_retired_empty_directories(data, inbox)
    assert {row["id"] for row in repository.list()} == {"ev-existing", "live-new"}
    current = repository.get("ev-existing")
    repository.update("ev-existing", {**current, "summary": "Analyst edit after cutover"})
    assert store.get_record("ev-existing", inbox_dir=inbox)["summary"] == "Analyst edit after cutover"
    assert next(row for row in repository.list() if row["id"] == "ev-existing")["summary"] == "Analyst edit after cutover"
    assert store.record_path("ev-existing", data_dir=data) == store.record_path("ev-existing", inbox_dir=inbox)
    assert not (data / "evidence").exists() and not (inbox / "evidence").exists()


def test_intake_attachment_and_reader_share_one_physical_record(application_runtime, monkeypatch):
    runtime = application_runtime
    monkeypatch.setattr(main, "new_draft_id", lambda title: "ev-new-intake")
    client = TestClient(main.app)
    response = client.post("/intake", data={"intake_type": "article_or_url", "title": "New blueberry source",
        "source_url": "https://example.com/new-intake", "summary": "One retained source statement", "submitted_by": "Human"},
        files={"attachment": ("proof.txt", b"new attachment bytes", "text/plain")}, follow_redirects=False)
    assert response.status_code == 303
    key = parse_qs(urlsplit(response.headers["location"]).query)["created"][0]
    saved = store.get_record(key, data_dir=runtime.data)
    assert saved["publication_scope"] == "private" and saved["status"] == "draft"
    assert main.get_draft(key) == saved
    assert main._load_intelligence_record(key)["summary"] == saved["summary"]
    assert main.get_repositories(runtime.data, main.SCHEMAS_DIR).evidence.get(key) == saved
    assert client.get(f"/intake/{key}").status_code == 200
    assert client.get(f"/api/intelligence/{key}/reader").status_code == 200
    attachment = client.get(f"/intake/{key}/attachments/proof.txt")
    assert attachment.status_code == 200 and attachment.content == b"new attachment bytes"
    assert (store.assets_dir(data_dir=runtime.data) / key / "proof.txt").read_bytes() == attachment.content
    for parent in (runtime.data, runtime.inbox):
        assert not (parent / "evidence").exists() and not (parent / "attachments").exists()


def test_readonly_routes_hide_private_reviewed_source_and_dependent_facts(application_runtime, monkeypatch):
    runtime = application_runtime
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    client = TestClient(main.app)
    protected = ("/evidence/live-private", "/intelligence/live-private", "/api/intelligence/live-private/reader",
                 "/intake/live-draft", "/evidence/live-private/attachments/private.txt",
                 "/intake/live-private/attachments/private.txt", "/facts/fact-private", "/facts/fact-mixed")
    assert {path: client.get(path).status_code for path in protected} == {path: 404 for path in protected}
    for path in ("/api/feed", "/api/search?q=PRIVATE", "/api/search/global?q=PRIVATE&include_private=1"):
        response = client.get(path)
        assert response.status_code == 200
        assert "live-private" not in response.text and "live-draft" not in response.text
        assert "PRIVATE SOURCE" not in response.text and "PRIVATE FACT" not in response.text
    public = client.get("/evidence/ev-public")
    assert public.status_code == 200 and "Public retained source wording" in public.text
    assert "live-private" not in public.text and "PRIVATE SOURCE" not in public.text
    attachment = client.get("/evidence/ev-public/attachments/public.txt")
    assert attachment.status_code == 200 and attachment.content == b"public attachment"
    assert store.get_record("live-private", data_dir=runtime.data)["reviewed_by"] == "Human reviewer"


def test_public_entity_backlinks_are_projected_without_editing_private_graph(application_runtime, monkeypatch):
    runtime = application_runtime
    path = runtime.data / "entities/companies/company-public.json"
    before = path.read_bytes()
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    response = TestClient(main.app).get("/api/entities/company/company-public")
    assert response.status_code == 200
    public = response.json()
    assert public["evidence_ids"] == ["ev-public"] and public["fact_ids"] == ["fact-public"]
    assert public["attributes"]["public_note"] == "Visible company detail"
    assert "live-private" not in response.text and "fact-private" not in response.text and "fact-mixed" not in response.text
    assert path.read_bytes() == before


def test_authoring_still_reads_reviewed_private_record_and_its_graph(application_runtime):
    client = TestClient(main.app)
    feed = client.get("/api/feed")
    private = next(row for row in feed.json() if row["id"] == "live-private")
    assert private["status"] == "published" and private["publication_scope"] == "private"
    assert private["information"]["review_status"] == "reviewed"
    assert client.get("/api/intelligence/live-private/reader").status_code == 200
    assert client.get("/evidence/live-private/attachments/private.txt").content == b"PRIVATE ATTACHMENT"
    entity = client.get("/api/entities/company/company-public").json()
    assert "live-private" in entity["evidence_ids"] and "fact-private" in entity["fact_ids"]


def test_static_build_context_filters_sources_and_transitive_facts_even_when_authoring(application_runtime, monkeypatch):
    from scripts import build_static
    runtime = application_runtime
    previous = RequestCorpus(runtime.data, main.SCHEMAS_DIR, runtime.inbox)
    token = bind_request_corpus(previous)
    def collect_public_context():
        repositories = main.get_repositories(runtime.data, main.SCHEMAS_DIR)
        return {"sources": main.all_evidence(), "facts": main.all_facts(), "entities": main.all_entities(),
                "selected_private": repositories.evidence.get("live-private")}
    monkeypatch.setattr(build_static, "_build_public_snapshot", collect_public_context)
    try:
        assert {row["id"] for row in main.all_facts()} == {"fact-public", "fact-private", "fact-mixed"}
        exported = build_static.build()
        assert {row["id"] for row in exported["sources"]} == {"ev-public"}
        assert [row["id"] for row in exported["facts"]] == ["fact-public"]
        assert exported["selected_private"] is None
        assert "live-private" not in json.dumps(exported) and "PRIVATE SOURCE" not in json.dumps(exported)
        assert get_request_corpus() is previous
        assert {row["id"] for row in main.all_facts()} == {"fact-public", "fact-private", "fact-mixed"}
    finally:
        reset_request_corpus(token)


def synced_migrated_runtime(tmp_path):
    seed, root = tmp_path / "seed", tmp_path / "runtime"
    data, inbox = root / "data", root / "inbox"
    inbox.mkdir(parents=True)
    source = evidence("ev-seeded", status="published", summary="Canonical first version")
    write(seed / "evidence/ev-seeded.json", source)
    write(data / "evidence/ev-seeded.json", source)
    migration.apply_migration(data, inbox, tmp_path / "migration-backups", quiesced=True)
    remove_retired_empty_directories(data, inbox)
    startup = startup_sync_trusted_data(seed, data, canonical_sha="first-canonical")
    assert "evidence/ev-seeded.json" in startup["baseline_initialized"]
    return SimpleNamespace(seed=seed, root=root, data=data, inbox=inbox, source=source)


def test_startup_and_backup_gated_promotion_use_migrated_paths(tmp_path):
    runtime = synced_migrated_runtime(tmp_path)
    migration_proof = deepcopy(store.get_record("ev-seeded", data_dir=runtime.data)["information_migration"])
    write(runtime.seed / "evidence/ev-new-seed.json", evidence("ev-new-seed", status="published"))
    asset = runtime.seed / "attachments/ev-new-seed/new.txt"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"new canonical attachment")
    write(runtime.seed / "evidence/ev-seeded.json", {**runtime.source, "summary": "Canonical second version"})
    startup = startup_sync_trusted_data(runtime.seed, runtime.data, canonical_sha="second-canonical")
    assert "evidence/ev-new-seed.json" in startup["files_added"]
    assert "attachments/ev-new-seed/new.txt" in startup["files_added"]
    assert store.get_record("ev-new-seed", inbox_dir=runtime.inbox)["publication_scope"] == "public"
    assert store.get_record("ev-seeded", data_dir=runtime.data)["summary"] == "Canonical first version"
    plan = plan_trusted_data_sync(runtime.seed, runtime.data, canonical_sha="second-canonical")
    row = next(row for row in plan["records"] if row["record_id"] == "ev-seeded")
    assert row["state"] == "SAFE_CANONICAL_UPDATE"
    assert row["runtime_path"] == "information/records/ev-seeded.json"
    archive = create_backup(runtime.root, tmp_path / "verified-backups")
    files = {row["path"] for row in verify_backup(archive)["files"]}
    assert "data/information/records/ev-seeded.json" in files
    assert "data/information/assets/ev-new-seed/new.txt" in files
    assert not any(name.startswith(("data/evidence/", "data/attachments/")) for name in files)
    applied = apply_safe_canonical_updates(runtime.seed, runtime.data, verified_backup=archive,
                                           canonical_sha="second-canonical")
    assert applied["files_updated"] == ["evidence/ev-seeded.json"]
    assert applied["backup"]["verified_targets"] == 1
    assert store.get_record("ev-seeded", inbox_dir=runtime.inbox)["summary"] == "Canonical second version"
    assert store.get_record("ev-seeded", data_dir=runtime.data)["information_migration"] == migration_proof
    assert (store.assets_dir(data_dir=runtime.data) / "ev-new-seed/new.txt").read_bytes() == b"new canonical attachment"
    assert next(row for row in plan_trusted_data_sync(runtime.seed, runtime.data)["records"]
                if row["record_id"] == "ev-seeded")["state"] == "UNCHANGED"
    for parent in (runtime.data, runtime.inbox):
        assert not (parent / "evidence").exists() and not (parent / "attachments").exists()


def test_promotion_backup_gate_checks_physical_record_bytes_after_cutover(tmp_path):
    runtime = synced_migrated_runtime(tmp_path)
    archive = create_backup(runtime.root, tmp_path / "verified-backups")
    source_path = store.record_path("ev-seeded", data_dir=runtime.data)
    current = deepcopy(store.get_record("ev-seeded", data_dir=runtime.data))
    write(source_path, current)  # Semantic identity, different bytes from the verified backup.
    write(runtime.seed / "evidence/ev-seeded.json", {**runtime.source, "summary": "Canonical second version"})
    with pytest.raises(ValueError, match="does not match current runtime bytes: data/information/records/ev-seeded.json"):
        apply_safe_canonical_updates(runtime.seed, runtime.data, verified_backup=archive, canonical_sha="next-canonical")
    assert store.get_record("ev-seeded", data_dir=runtime.data) == current
    assert not (runtime.data / "evidence").exists()


def test_relative_seed_sync_paths_follow_the_active_store(tmp_path, monkeypatch):
    runtime = synced_migrated_runtime(tmp_path)
    write(runtime.seed / "evidence/ev-seeded.json", {**runtime.source, "summary": "Relative-path canonical update"})
    monkeypatch.chdir(tmp_path)
    seed, data = Path("seed"), Path("runtime/data")
    planned = plan_trusted_data_sync(seed, data, canonical_sha="relative-canonical")
    row = next(row for row in planned["records"] if row["record_id"] == "ev-seeded")
    assert row["state"] == "SAFE_CANONICAL_UPDATE"
    assert row["runtime_path"] == "information/records/ev-seeded.json"
    startup = startup_sync_trusted_data(seed, data, canonical_sha="relative-canonical")
    assert startup["files_updated"] == []  # Startup preserves the existing source.
    archive = create_backup(runtime.root, tmp_path / "verified-backups")
    applied = apply_safe_canonical_updates(seed, data, verified_backup=archive.relative_to(tmp_path),
                                           canonical_sha="relative-canonical")
    assert applied["files_updated"] == ["evidence/ev-seeded.json"]
    assert store.get_record("ev-seeded", inbox_dir=runtime.inbox)["summary"] == "Relative-path canonical update"
    assert not (data / "evidence").exists() and not (data / "attachments").exists()
