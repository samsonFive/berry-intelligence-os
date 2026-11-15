"""New cultivar intake stays in the active source store and private graph."""
from copy import deepcopy
from contextlib import contextmanager
from hashlib import sha256
import json

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services import information_migration as migration, information_storage as storage
from app.services.cultivar_measurements import load_evidence_dependencies, stage_measurement
from app.services.cultivar_measurement_workspace import CultivarMeasurementError, present_measurement, source_artifact, source_dependency_ids
from app.services.publication_scope import public_repositories
from app.services.request_corpus import RequestCorpus
from app.services.strawberry_research_import import digest, import_packet
from tests.test_cultivar_measurements import world, _normalize, _project, _review
from tests.test_strawberry_research_import import sample, build, write
from tests.test_review_publish_portability import _publish


def activate(data, inbox, backups):
    inbox.mkdir(parents=True, exist_ok=True)
    migration.apply_migration(data, inbox, backups, quiesced=True)
    for root in (data, inbox):
        for name in ("evidence", "attachments"):
            folder = root / name
            if folder.exists():
                assert not any(folder.iterdir())
                folder.rmdir()  # Known empty fixture directories only.


def test_active_import_review_replay_and_reader_share_one_private_source_and_original(sample, tmp_path, monkeypatch):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    first = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    key = first["source_bindings"][0]["evidence_id"]
    record_path = storage.record_path(key, data_dir=data)
    record = storage.get_record(key, data_dir=data)
    assert record["publication_scope"] == "private" and record["information"]["review_status"] == "unreviewed"
    assert len(list(record_path.parent.glob("*.json"))) == 1
    attachment = record["attachments"][0]
    asset = storage.assets_dir(data_dir=data) / key / attachment["filename"]
    assert asset.read_bytes() == (packet_dir / packet["artifacts"][0]["path"]).read_bytes()
    assert not (inbox / "cultivar_measurement_imports/test-batch" / packet["artifacts"][0]["path"]).exists()
    resolved, _name = source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])
    assert resolved == asset
    inventory = RequestCorpus(data, main.SCHEMAS_DIR, inbox).information
    assert inventory[0]["id"] == key and inventory[0]["information"]["review_status"] == "unreviewed"
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    response = _publish(TestClient(main.app), key, title=record["title"], summary="Human source edit",
        source_type=record["source_type"], source_name=record["source_name"], source_url=record["source_url"],
        published_date="", captured_date=record["captured_date"])
    assert response.status_code == 303
    reviewed = storage.get_record(key, data_dir=data)
    assert reviewed["id"] == key and reviewed["summary"] == "Human source edit"
    assert reviewed["publication_scope"] == "private" and reviewed["information"]["review_status"] == "reviewed"
    assert reviewed["attachments"][0]["sha256"] == attachment["sha256"]
    again = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert again["source_bindings"] == first["source_bindings"]
    assert storage.get_record(key, data_dir=data) == reviewed
    assert asset.read_bytes() == resolved.read_bytes()
    # A later explicit source publication must not rewrite the immutable
    # import index or introduce a second physical original during replay.
    storage.write_record({**reviewed, "publication_scope": "public"}, data_dir=data)
    published_replay = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert published_replay["source_bindings"] == first["source_bindings"]
    assert not (inbox / "cultivar_measurement_imports/test-batch" / packet["artifacts"][0]["path"]).exists()
    assert not (data / "evidence").exists() and not (inbox / "evidence").exists()
    assert not (data / "attachments").exists() and not (inbox / "attachments").exists()


def test_legacy_research_import_replays_after_cutover_without_copying_its_original_again(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    first = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    original = inbox / "cultivar_measurement_imports/test-batch" / packet["artifacts"][0]["path"]
    before = original.read_bytes()
    activate(data, inbox, tmp_path / "backups")
    again = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert again["source_bindings"] == first["source_bindings"]
    assert source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])[0] == original
    assert original.read_bytes() == before
    key = first["source_bindings"][0]["evidence_id"]
    assert not (storage.assets_dir(data_dir=data) / key).exists()
    assert not (inbox / "evidence").exists() and not (data / "evidence").exists()


def test_active_import_reuses_retained_id_and_dependency_reader_is_body_free(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    storage.upsert_record({"id": "live-retained-cultivar", "status": "unreviewed", "live": True,
        "source_url": "https://example.org/document", "title": "Retained source", "summary": "Source statement",
        "article": {"paragraphs": [{"text": "FULL SOURCE BODY CANARY"}]}}, inbox_dir=inbox, origin="retained")
    result = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["counts"]["new_publication_drafts"] == 0
    assert result["source_bindings"][0]["evidence_id"] == "live-retained-cultivar"
    dependencies = load_evidence_dependencies(data, evidence_ids=["live-retained-cultivar", "../../outside"])
    assert set(dependencies) == {"live-retained-cultivar"}
    assert "CANARY" not in json.dumps(dependencies) and dependencies["live-retained-cultivar"]["publication_scope"] == "private"
    assert len(storage.list_records(data_dir=data)) == 1
    packet_meta = [{"_batch_id": "test-batch"}]
    assert source_dependency_ids(inbox, packet_meta) == {"live-retained-cultivar"}
    assert source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])[0].is_file()


def test_reused_public_source_does_not_publish_new_research_capture(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    write(data / "evidence/ev-existing.json", {"id": "ev-existing", "record_type": "evidence", "status": "published",
        "source_url": "https://example.org/document", "title": "Published source"})
    activate(data, inbox, tmp_path / "backups")
    before = storage.record_path("ev-existing", data_dir=data).read_bytes()
    result = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["source_bindings"][0]["evidence_id"] == "ev-existing"
    assert storage.record_path("ev-existing", data_dir=data).read_bytes() == before
    assert not (storage.assets_dir(data_dir=data) / "ev-existing").exists()
    path, _name = source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])
    assert path.is_relative_to(inbox / "cultivar_measurement_imports")


def test_conflicting_same_id_cannot_install_private_bytes_under_a_public_source(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    key = "ev-strawberry-source-" + packet["documents"][0]["id"][4:]
    write(data / "evidence" / (key + ".json"), {"id": key, "status": "published", "source_url": "https://different.example/source"})
    activate(data, inbox, tmp_path / "backups")
    before = storage.record_path(key, data_dir=data).read_bytes()
    with pytest.raises(ValueError, match="source ID conflicts"):
        import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert storage.record_path(key, data_dir=data).read_bytes() == before
    assert not (storage.assets_dir(data_dir=data) / key).exists()
    assert not (inbox / "cultivar_measurement_imports").exists()


def test_shared_original_reference_cannot_escape_its_registered_asset(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    index_path = inbox / "cultivar_measurement_imports/test-batch/import-index.json"
    index = json.loads(index_path.read_text())
    index["information_assets"][packet["artifacts"][0]["sha256"]]["filename"] = "../../outside"
    write(index_path, index)
    with pytest.raises(CultivarMeasurementError, match="shared source capture binding"):
        source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])


def test_dry_run_resolves_exact_shared_asset_and_prepared_source_payload(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    preview = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox)
    key = preview["source_bindings"][0]["evidence_id"]
    capture = packet["artifacts"][0]
    assert preview["information_assets"] == {capture["sha256"]: {
        "evidence_id": key, "filename": capture["path"].split("/")[-1],
        "sha256": capture["sha256"], "bytes": capture["bytes"]}}
    prepared = preview["new_sources"][key]
    assert prepared["publication_scope"] == "private" and prepared["review_status"] == "unreviewed"
    assert prepared["attachments"][0]["sha256"] == capture["sha256"]
    assert not (inbox / "cultivar_measurement_imports").exists()
    assert not list(storage.information_directory(data_dir=data).glob("*.json"))
    first = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    source_bytes = storage.record_path(key, data_dir=data).read_bytes()
    assert first["information_assets"] == preview["information_assets"]
    assert first["new_sources"] == preview["new_sources"]
    assert sha256(source_bytes).hexdigest() == prepared["record_sha256"]
    assert len(source_bytes) == prepared["record_bytes"]
    replay = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert replay["new_sources"] == {} and replay["information_assets"] == preview["information_assets"]


def test_existing_private_source_keeps_scope_in_lookup_and_owns_one_original(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    storage.upsert_record({"id": "Existing.Private", "status": "draft", "source_url": "https://example.org/document",
                          "summary": "Existing human prose"}, data_dir=data, inbox_dir=inbox)
    before = storage.record_path("Existing.Private", data_dir=data).read_bytes()
    result = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    reference = result["information_assets"][packet["artifacts"][0]["sha256"]]
    assert reference["evidence_id"] == "Existing.Private"
    assert result["new_sources"] == {}
    assert storage.record_path("Existing.Private", data_dir=data).read_bytes() == before
    asset, _ = source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])
    assert asset.is_relative_to(storage.assets_dir(data_dir=data))
    assert not (inbox / "cultivar_measurement_imports/test-batch" / packet["artifacts"][0]["path"]).exists()


@pytest.mark.parametrize("mutation", ["public_scope", "different_identity", "missing_binding"])
def test_fresh_owner_and_marker_changes_hold_before_any_private_binary(sample, tmp_path, monkeypatch, mutation):
    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    storage.upsert_record({"id": "Existing.Private", "status": "draft", "source_url": "https://example.org/document",
                          "summary": "Human source retained"}, data_dir=data, inbox_dir=inbox)
    source_path = storage.record_path("Existing.Private", data_dir=data)
    source = storage.get_record("Existing.Private", data_dir=data)
    original_lock = storage.storage_lock
    written = []

    @contextmanager
    def prior_writer_before_lease(**kwargs):
        with original_lock(**kwargs):
            if mutation == "missing_binding":
                (inbox / ".information-store.json").unlink()
            else:
                revised = {**source, "publication_scope": "public"} if mutation == "public_scope" else {
                    **source, "source_url": "https://different.example/document"}
                storage.atomic_json(source_path, revised)
            written.append(source_path.read_bytes())
            yield

    monkeypatch.setattr(storage, "storage_lock", prior_writer_before_lease)
    with pytest.raises((ValueError, storage.InformationStorageError)):
        import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert source_path.read_bytes() == written[0]
    assert not list(storage.assets_dir(data_dir=data).rglob("*.*"))
    assert not (inbox / "cultivar_measurement_imports").exists()
    assert not (inbox / "cultivar_measurements").exists()


def test_one_source_lease_covers_every_asset_and_new_source_install(sample, tmp_path, monkeypatch):
    from app.services import strawberry_research_import as importer

    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    held, acquisitions, observed = False, [], []
    original_lock, original_install = storage.storage_lock, importer._install

    @contextmanager
    def observed_lock(**kwargs):
        nonlocal held
        assert not held, "Source lease must not be reacquired recursively"
        with original_lock(**kwargs):
            held = True
            acquisitions.append(True)
            try:
                yield
            finally:
                held = False

    def observed_install(path, raw):
        assert held, "Private artifact/source installation happened outside source lease"
        observed.append(str(path))
        return original_install(path, raw)

    monkeypatch.setattr(storage, "storage_lock", observed_lock)
    monkeypatch.setattr(importer, "_install", observed_install)
    import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert len(acquisitions) == 1 and not held
    assert any("assets" in path for path in observed) and any("records" in path for path in observed)


def test_asset_collision_is_detected_before_new_source_or_batch_writes(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    key = "ev-strawberry-source-" + packet["documents"][0]["id"][4:]
    asset = storage.assets_dir(data_dir=data) / key / packet["artifacts"][0]["path"].split("/")[-1]
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"Pre-existing conflicting content")
    before = asset.read_bytes()
    with pytest.raises(ValueError, match="Conflicting existing research asset"):
        import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert asset.read_bytes() == before
    assert storage.get_record(key, data_dir=data) is None
    assert not (inbox / "cultivar_measurement_imports").exists()


def test_public_registered_original_cannot_be_recreated_after_removal(sample, tmp_path):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    first = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    key = first["source_bindings"][0]["evidence_id"]
    source = storage.get_record(key, data_dir=data)
    asset, _ = source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])
    storage.write_record({**source, "publication_scope": "public"}, data_dir=data)
    before = storage.record_path(key, data_dir=data).read_bytes()
    index = inbox / "cultivar_measurement_imports/test-batch/import-index.json"
    index_bytes = index.read_bytes()
    asset.unlink()
    with pytest.raises(ValueError, match="public source asset is missing"):
        import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert not asset.exists()
    assert storage.record_path(key, data_dir=data).read_bytes() == before
    assert index.read_bytes() == index_bytes
    assert not (inbox / "cultivar_measurement_imports/test-batch" / packet["artifacts"][0]["path"]).exists()


@pytest.mark.parametrize("kind", ["visual_verification", "unbound"])
def test_visual_and_unbound_artifacts_keep_one_batch_original(sample, tmp_path, kind):
    packet = build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    if kind == "visual_verification":
        packet["artifacts"][0]["role"] = kind
    else:
        packet["artifacts"][0]["source_ids"] = []
    packet.pop("packet_sha256")
    packet["packet_sha256"] = digest(packet)
    write(packet_dir / "packet.json", packet)
    result = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["information_assets"] == {}
    assert all(not row["attachments"] for row in result["new_sources"].values())
    asset, _ = source_artifact(inbox, "test-batch", packet["artifacts"][0]["sha256"])
    assert asset.is_relative_to(inbox / "cultivar_measurement_imports/test-batch")
    assert not list(storage.assets_dir(data_dir=data).rglob("*.*"))
    replay = import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert replay["information_assets"] == {} and replay["new_sources"] == {}


def test_source_lease_releases_after_asset_install_failure(sample, tmp_path, monkeypatch):
    from app.services import strawberry_research_import as importer

    build(sample, publication_source_ids=["S1"])
    _, _, _, data, inbox, packet_dir = sample
    activate(data, inbox, tmp_path / "backups")
    original_install = importer._install

    def fail_asset_install(path, raw):
        if path.is_relative_to(storage.assets_dir(data_dir=data)):
            raise OSError("Simulated private asset disk failure")
        return original_install(path, raw)

    monkeypatch.setattr(importer, "_install", fail_asset_install)
    with pytest.raises(OSError, match="Simulated private asset disk failure"):
        import_packet(packet_dir / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    # Reacquisition uses the actual OS-owned information store lease.
    with storage.storage_lock(data_dir=data, inbox_dir=inbox, timeout=0.1):
        assert not list(storage.information_directory(data_dir=data).glob("*.json"))
    assert not (inbox / "cultivar_measurements").exists()


def test_reviewed_private_measurement_citing_public_source_requires_explicit_public_authorization(world, tmp_path):
    activate(world.data, world.inbox, tmp_path / "backups")
    record = _normalize()
    stage_measurement(world.inbox, record)
    result = _review(world, record)
    assert result["ok"]
    fact = world.repos.facts.get(result["fact_id"])
    assert fact["publication_scope"] == "private"
    assert storage.get_record("ev-source", data_dir=world.data)["publication_scope"] == "public"
    assert _project(world)[0]["review_state"] == "reviewed" and _project(world, False) == []
    assert public_repositories(world.repos).facts.list() == []
    world.repos.facts.update(fact["id"], {**fact, "publication_scope": "public"})
    assert len(_project(world, False)) == 1
    source = storage.get_record("ev-source", data_dir=world.data)
    storage.write_record({**source, "publication_scope": "private"}, data_dir=world.data)
    assert _project(world, False) == [] and public_repositories(world.repos).facts.list() == []


def test_source_cards_link_unreviewed_sources_to_reader_without_claiming_review():
    binding = {"source_id": "S1", "evidence_id": "live-source", "source_url": "https://example.org", "source_title": "Source"}
    record = {"id": "cm-fixture-" + "a" * 16, "source_bindings": [binding], "source_native": {}}
    source = {"id": "live-source", "status": "published", "information": {"review_status": "unreviewed"}, "validated": False}
    card = present_measurement(record, entities={}, evidence={"live-source": source}, packets=[])["source_cards"][0]
    assert not card["published"] and card["information"]["review_status"] == "unreviewed"
    assert card["source_href"] == "/intelligence/live-source" and card["review_href"].startswith("/review/live-source?")
