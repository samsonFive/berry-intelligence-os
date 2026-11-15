"""Import integrity, no trust side effects, and replay/edited-draft safety."""
from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.strawberry_research_import import (
    build_packet, digest, import_packet, load_import_batches,
)
from app.services import information_storage


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def sample(tmp_path):
    root = tmp_path / "research"
    root.mkdir()
    capture = root / "original.txt"
    capture.write_text("Retained original source content.", encoding="utf-8")
    source = {"id": "S1", "title": "Grower source", "url": "https://example.org/document",
              "date": "2026-10", "publication_date": "2026-10", "type": "primary grower",
              "locator": "page 2", "local_capture": str(capture)}
    row = {"id": "ROW-1", "region": "Florida", "subregion": "", "cultivar": "Example",
           "platform_entity_ids": ["variety-example"], "platform_candidate_ids": ["variety-example"],
           "record_kind": "cultivar", "claim": "Reported planted area", "evidence_type": "Reported planted area",
           "value": 12, "unit": "acres", "denominator": "Company planted area", "data_period": "2025/26",
           "source_ids": ["S1"], "limitations": "Company scope"}
    ledger = {"rows": [row], "sources": [source]}
    path = root / "combined-research.json"
    write(path, ledger)
    write(root / "acquisition-backlog.json", [{"region": "Florida", "gap": "Current survey"}])
    data = tmp_path / "data"
    write(data / "entities/varieties/example.json", {"id": "variety-example", "entity_type": "variety",
          "name": "Example", "berry_ids": ["berry-strawberry"]})
    write(data / "entities/berries/strawberry.json", {"id": "berry-strawberry", "entity_type": "berry"})
    return root, path, ledger, data, tmp_path / "inbox", tmp_path / "packet"


def build(sample, **kwargs):
    root, path, _, _, _, packet_dir = sample
    return build_packet(path, packet_dir, capture_root=root, batch_id="test-batch",
                        captured_at="2026-11-15T00:00:00Z", berry_id="berry-strawberry", **kwargs)


def activate_store(data, inbox):
    """Exact non-sibling capable marker/binding contract; no legacy folders."""
    data, inbox = data.resolve(), inbox.resolve()
    root = data / "information"
    (root / "records").mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    information_storage.atomic_json(root / "store.json", {
        "version": 1, "state": "active", "store_root": str(root),
        "data_dir": str(data), "inbox_dir": str(inbox)})
    information_storage.atomic_json(inbox / ".information-store.json", {
        "version": 1, "store_root": str(root), "inbox_dir": str(inbox)})
    return root


def test_dry_run_no_writes_and_explicit_source_allowlist(sample):
    packet = build(sample)
    assert packet["counts"]["publication_eligible_documents"] == 0
    _, _, _, data, inbox, folder = sample
    plan = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox)
    assert not inbox.exists()
    assert plan["counts"]["new_publication_drafts"] == 0
    assert plan["source_bindings"][0]["evidence_id"] is None
    assert plan["source_bindings"][0]["access_status"] == "acquisition_backlog"


def test_apply_replay_preserves_draft_edits_and_canonical_bytes(sample):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    canonical = {p: p.read_bytes() for p in data.rglob("*.json")}
    first = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert first["counts"]["measurement_outcomes"] == {"created": 1}
    draft_path = next((inbox / "evidence").glob("*.json"))
    draft = json.loads(draft_path.read_text())
    assert draft["status"] == "draft" and draft["evidence_role"] == "publication_artifact"
    assert all(value["level"] == "none" for value in draft["priority"].values())
    assert draft["published_date"] is None  # month-only publication date is not an invented day
    draft["summary"] = "Human edit retained"
    write(draft_path, draft)
    second = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert second["counts"]["measurement_outcomes"] == {"already_present_identical": 1}
    assert second["source_bindings"] == first["source_bindings"]
    assert json.loads(draft_path.read_text())["summary"] == "Human edit retained"
    assert {p: p.read_bytes() for p in data.rglob("*.json")} == canonical
    assert not (data / "facts").exists()
    assert len(list((inbox / "cultivar_measurements").glob("*.json"))) == 1
    batches = load_import_batches(inbox)
    assert len(batches) == 1 and batches[0]["acquisition_backlog"][0]["region"] == "Florida"


def test_capture_tamper_rejected_before_any_inbox_write(sample):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    (folder / packet["artifacts"][0]["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="capture hash mismatch"):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert not inbox.exists()


def test_source_aliases_share_document_and_preserve_all_rows(sample):
    root, path, ledger, data, inbox, folder = sample
    alias = deepcopy(ledger["sources"][0])
    alias["id"] = "S2"
    alias.pop("local_capture")
    alias["url"] += "#page=2"
    ledger["sources"].append(alias)
    row = deepcopy(ledger["rows"][0])
    row.update(id="ROW-2", source_ids=["S2"], value=13)
    ledger["rows"].append(row)
    write(path, ledger)
    packet = build(sample, publication_source_ids=["S1", "S2"])
    assert packet["counts"]["source_entries"] == 2
    assert packet["counts"]["documents"] == 1
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["counts"]["new_publication_drafts"] == 1
    assert len(list((inbox / "cultivar_measurements").glob("*.json"))) == 2


def test_outside_capture_and_canonical_target_rejected(sample, tmp_path):
    root, path, ledger, data, _, folder = sample
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    ledger["sources"][0]["local_capture"] = str(outside)
    write(path, ledger)
    with pytest.raises(ValueError, match="leaves the declared capture root"):
        build(sample)
    ledger["sources"][0]["local_capture"] = str(root / "original.txt")
    write(path, ledger)
    build(sample)
    with pytest.raises(ValueError, match="must be disjoint"):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=data, apply=True)


def test_access_form_cannot_be_allowlisted(sample):
    _, path, ledger, _, _, _ = sample
    ledger["sources"][0]["type"] = "primary_blank_administrative_form"
    write(path, ledger)
    with pytest.raises(ValueError, match="Access-only"):
        build(sample, publication_source_ids=["S1"])


def test_changed_mutable_document_never_reuses_old_version(sample):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    write(data / "evidence/ev-old-version.json", {"id": "ev-old-version", "status": "published",
          "source_url": "https://example.org/document", "workspace_capture": {"binary_sha256": "f" * 64}})
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["source_bindings"][0]["evidence_id"] != "ev-old-version"
    assert result["source_bindings"][0]["captured_sha256"] == packet["artifacts"][0]["sha256"]
    assert json.loads((data / "evidence/ev-old-version.json").read_text())["workspace_capture"]["binary_sha256"] == "f" * 64


def test_manifest_path_escape_is_rejected_even_when_hash_recomputed(sample):
    build(sample)
    _, _, _, data, inbox, folder = sample
    path = folder / "packet.json"
    packet = json.loads(path.read_text())
    packet["batch_id"] = "../../data"
    packet.pop("packet_sha256")
    packet["packet_sha256"] = digest(packet)
    write(path, packet)
    with pytest.raises(ValueError, match="batch ID"):
        import_packet(path, data_dir=data, inbox_dir=inbox, apply=True)
    assert not inbox.exists()


def test_catalog_dependency_change_does_not_duplicate_or_rebind_proposal(sample):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    before = {p.name: p.read_bytes() for p in (inbox / "cultivar_measurements").glob("*.json")}
    (data / "entities/varieties/example.json").unlink()
    replay = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert replay["counts"]["measurement_outcomes"] == {"already_present_identical": 1}
    assert {p.name: p.read_bytes() for p in (inbox / "cultivar_measurements").glob("*.json")} == before


def test_identity_resolution_history_survives_exact_import_replay(sample):
    from app.services.cultivar_measurements import resolve_measurement_identity
    _, path, ledger, data, inbox, folder = sample
    ledger["rows"][0]["platform_candidate_ids"].append("variety-other")
    write(path, ledger)
    write(data / "entities/varieties/other.json", {"id": "variety-other", "entity_type": "variety",
          "name": "Other", "berry_ids": ["berry-strawberry"]})
    build(sample, publication_source_ids=["S1"])
    import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    record_path = next((inbox / "cultivar_measurements").glob("*.json"))
    record = json.loads(record_path.read_text())
    entity = json.loads((data / "entities/varieties/example.json").read_text())
    decision = resolve_measurement_identity(inbox, record["id"], selected_entity_id="variety-example",
        reviewer="human-reviewer", expected_content_sha256=record["content_sha256"],
        notes="Verified cultivar code in original source page 2",
        repos=SimpleNamespace(entities=SimpleNamespace(get=lambda key: entity if key == entity["id"] else None)))
    assert decision["ok"]
    proposal_bytes = {p.name: p.read_bytes() for p in (inbox / "cultivar_measurements").glob("*.json")}
    event_bytes = {str(p.relative_to(inbox)): p.read_bytes() for p in inbox.rglob("*.json")
                   if "review_event" in str(p)}
    assert len(proposal_bytes) == 2 and event_bytes
    replay = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert replay["counts"]["measurement_outcomes"] == {"already_present_identical": 1}
    assert {p.name: p.read_bytes() for p in (inbox / "cultivar_measurements").glob("*.json")} == proposal_bytes
    assert {str(p.relative_to(inbox)): p.read_bytes() for p in inbox.rglob("*.json")
            if "review_event" in str(p)} == event_bytes
    assert not (data / "facts").exists()


def test_active_store_import_is_private_and_replay_preserves_review_metadata(sample):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    before = {path: path.read_bytes() for path in data.rglob("*.json")}
    dry = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox)
    assert {path: path.read_bytes() for path in data.rglob("*.json")} == before
    assert not (data / ".information-store.lock").exists()
    first = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert first["counts"]["new_publication_drafts"] == dry["counts"]["new_publication_drafts"] == 1
    source = information_storage.list_records(data_dir=data, inbox_dir=inbox)[0]
    assert source["status"] == "draft" and source["publication_scope"] == "private"
    assert source["information"]["review_status"] == "unreviewed"
    assert source["information"]["confidence"] is None
    assert not information_storage.is_public_record(source)
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()
    assert all(path.read_bytes() == value for path, value in before.items())
    assert not (data / "facts").exists()
    reviewed = {**source, "summary": "Human edited wording", "reviewed_by": "Analyst", "reviewed_at": "2026-11-15",
                "information_confidence": "high", "information": {"review_status": "reviewed", "confidence": "high"}}
    information_storage.upsert_record(reviewed, data_dir=data, inbox_dir=inbox, allow_review_update=True)
    source_before = {path: path.read_bytes() for path in root.rglob("*.json")}
    second = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert second["counts"]["new_publication_drafts"] == 0
    assert second["counts"]["measurement_outcomes"] == {"already_present_identical": 1}
    assert {path: path.read_bytes() for path in root.rglob("*.json")} == source_before
    preserved = information_storage.get_record(source["id"], inbox_dir=inbox)
    assert preserved["summary"] == "Human edited wording" and preserved["publication_scope"] == "private"
    assert preserved["information"]["review_status"] == "reviewed" and preserved["information_confidence"] == "high"


@pytest.mark.parametrize("scope", ["private", "public"])
def test_active_store_reuses_safe_non_ev_id_without_changing_scope_or_confidence(sample, scope):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    source = {"id": "Live.Source_01", "status": "published", "source_url": "https://example.org/document",
              "title": "Existing source", "summary": "Analyst wording", "publication_scope": scope,
              "information_confidence": {"level": "medium", "basis": "Existing human metadata"},
              "information": {"review_status": "reviewed"}, "reviewed_by": "Original reviewer"}
    information_storage.write_record(source, data_dir=data, inbox_dir=inbox, origin="canonical")
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    first = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert first["counts"]["new_publication_drafts"] == 0
    assert first["source_bindings"][0]["evidence_id"] == "Live.Source_01"
    assert {path: path.read_bytes() for path in root.rglob("*.json")} == before
    stored = information_storage.get_record("Live.Source_01", inbox_dir=inbox)
    assert stored["publication_scope"] == scope and stored["reviewed_by"] == "Original reviewer"
    assert stored["information_confidence"] == source["information_confidence"]
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()
    assert not (data / "facts").exists()


@pytest.mark.parametrize("broken", ["missing_marker", "missing_binding", "mismatched_binding", "transition"])
def test_incomplete_active_store_blocks_import_without_legacy_fallback(sample, broken):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    if broken == "missing_marker":
        (root / "store.json").unlink()
    elif broken == "missing_binding":
        (inbox / ".information-store.json").unlink()
    elif broken == "mismatched_binding":
        binding = json.loads((inbox / ".information-store.json").read_text())
        binding["store_root"] = str(data.parent / "other/information")
        write(inbox / ".information-store.json", binding)
    else:
        write(data / ".information-store-transition.json", {"state": "in_progress"})
    before = {path: path.read_bytes() for parent in (data, inbox) for path in parent.rglob("*") if path.is_file()}
    with pytest.raises(information_storage.InformationStorageError):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert {path: path.read_bytes() for parent in (data, inbox) for path in parent.rglob("*") if path.is_file()} == before
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()


def test_active_store_deterministic_id_collision_never_upserts_existing_source(sample):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    source_id = "ev-strawberry-source-" + packet["documents"][0]["id"][4:]
    information_storage.upsert_record({"id": source_id, "status": "draft", "title": "Other source",
                                      "source_url": "https://example.org/different"}, inbox_dir=inbox)
    before = {path: path.read_bytes() for path in root.rglob("*.json")}
    with pytest.raises(ValueError, match="source ID conflicts"):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert {path: path.read_bytes() for path in root.rglob("*.json")} == before
    assert not (inbox / "cultivar_measurements").exists()
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()


def test_existing_private_proposals_replay_after_real_information_migration(sample):
    from app.services import information_migration
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    first = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    proposals = {path.name: path.read_bytes() for path in (inbox / "cultivar_measurements").glob("*.json")}
    information_migration.apply_migration(data, inbox, inbox.parent / "migration-backups", quiesced=True)
    source_root = data / "information"
    before = {path: path.read_bytes() for path in source_root.rglob("*.json")}
    second = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert second["source_bindings"] == first["source_bindings"]
    assert second["counts"]["measurement_outcomes"] == {"already_present_identical": 1}
    assert {path: path.read_bytes() for path in source_root.rglob("*.json")} == before
    assert {path.name: path.read_bytes() for path in (inbox / "cultivar_measurements").glob("*.json")} == proposals
    assert not list((inbox / "evidence").glob("*.json"))
    assert not (data / "facts").exists()


def test_inventory_lookup_streams_unrelated_bodies_and_keeps_only_matches(sample, monkeypatch):
    from app.services.strawberry_research_import import _source_records

    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    unrelated_paths = set()
    for number in range(4):
        path = root / "records" / f"Cached.Source_{number}.json"
        write(path, {"id": path.stem, "status": "published", "source_url": f"https://other.org/{number}",
                     "article": {"paragraphs": [{"text": "x" * 3_000_000}]},
                     "workspace_capture": {"binary_sha256": "a" * 64}})
        unrelated_paths.add(path)
    matching = {"id": "Live.Source_01", "status": "published", "source_url": "https://example.org/document",
                "discovery_provenance": {"retained_binary_sha256": packet["artifacts"][0]["sha256"]}}
    write(root / "records" / "Live.Source_01.json", matching)
    read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        assert path not in unrelated_paths, "Unrelated source body was fully hydrated"
        return read_text(path, *args, **kwargs)

    def no_eager_inventory(*args, **kwargs):
        pytest.fail("Full source inventory must not be hydrated")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(information_storage, "list_records", no_eager_inventory)
    records = _source_records(data, inbox, packet["documents"])
    assert list(records) == ["Live.Source_01"]
    assert len(json.dumps(records)) < 1000
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox)
    assert result["source_bindings"][0]["evidence_id"] == matching["id"]
    assert result["counts"]["new_publication_drafts"] == 0
    assert not (inbox / "cultivar_measurements").exists()


@pytest.mark.parametrize("version", ["matching", "changed"])
def test_matching_workspace_capture_hydrates_only_its_exact_version(sample, monkeypatch, version):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    checksum = packet["artifacts"][0]["sha256"] if version == "matching" else "f" * 64
    source = {"id": "Live.Source_01", "status": "published", "source_url": "https://example.org/document",
              "workspace_capture": {"binary_sha256": checksum},
              "article": {"paragraphs": [{"text": "retained original text " * 100_000}]}}
    source_path = root / "records" / "Live.Source_01.json"
    write(source_path, source)
    get_record = information_storage.get_record
    hydrated = []

    def observed_get_record(record_id, **kwargs):
        hydrated.append(record_id)
        return get_record(record_id, **kwargs)

    monkeypatch.setattr(information_storage, "get_record", observed_get_record)
    before = source_path.read_bytes()
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox)
    assert hydrated == [source["id"]]
    assert (result["source_bindings"][0]["evidence_id"] == source["id"]) == (version == "matching")
    assert result["counts"]["new_publication_drafts"] == (0 if version == "matching" else 1)
    assert source_path.read_bytes() == before
    assert not (inbox / "cultivar_measurements").exists()


def test_oversized_inventory_record_holds_import_before_any_writes(sample, monkeypatch):
    from app.services import publication_sources

    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    write(root / "records" / "Large.Source.json", {"id": "Large.Source", "source_url": "https://other.org",
                                                 "article": {"text": "x" * 2000}})
    monkeypatch.setattr(publication_sources, "MAX_DRAFT_BYTES", 1024)
    before = {path: path.read_bytes() for parent in (data, inbox) for path in parent.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="source-size-limit"):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert {path: path.read_bytes() for parent in (data, inbox) for path in parent.rglob("*") if path.is_file()} == before
    assert not (inbox / "cultivar_measurements").exists()
    assert not (inbox / "evidence").exists()


def test_legacy_canonical_id_suppresses_stale_matching_intake_copy(sample):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    write(data / "evidence" / "Existing.Source.json", {
        "id": "Existing.Source", "status": "published", "source_url": "https://example.org/new-url"})
    write(inbox / "evidence" / "Existing.Source.json", {
        "id": "Existing.Source", "status": "draft", "source_url": "https://example.org/document"})
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox)
    assert result["source_bindings"][0]["evidence_id"] != "Existing.Source"
    assert result["counts"]["new_publication_drafts"] == 1


def test_source_appearing_at_storage_lock_is_never_merged_or_overwritten(sample, monkeypatch):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, folder = sample
    root = activate_store(data, inbox)
    source_id = "ev-strawberry-source-" + packet["documents"][0]["id"][4:]
    source_path = root / "records" / (source_id + ".json")
    concurrent_source = {"id": source_id, "source_url": "https://example.org/document", "status": "draft",
                         "summary": "Human wording written concurrently", "publication_scope": "private",
                         "information": {"review_status": "unreviewed", "confidence": "medium"},
                         "reviewed_by": "Concurrent analyst"}
    original_lock = information_storage.storage_lock
    retained = []

    @contextmanager
    def concurrent_writer_before_lease(**kwargs):
        with original_lock(**kwargs):
            information_storage.atomic_json(source_path, concurrent_source)
            retained.append(source_path.read_bytes())
            yield

    monkeypatch.setattr(information_storage, "storage_lock", concurrent_writer_before_lease)
    with pytest.raises(ValueError, match="Source record appeared after planning"):
        import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert source_path.read_bytes() == retained[0]
    assert not (root / "history").exists()
    assert not (inbox / "cultivar_measurements").exists()
    assert not (inbox / "evidence").exists()
    assert not (data / "facts").exists()
