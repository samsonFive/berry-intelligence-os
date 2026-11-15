"""Import integrity, no trust side effects, and replay/edited-draft safety."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.strawberry_research_import import (
    build_packet, digest, import_packet, load_import_batches,
)


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
    write(data / "evidence/old.json", {"id": "ev-old-version", "status": "published",
          "source_url": "https://example.org/document", "workspace_capture": {"binary_sha256": "f" * 64}})
    result = import_packet(folder / "packet.json", data_dir=data, inbox_dir=inbox, apply=True)
    assert result["source_bindings"][0]["evidence_id"] != "ev-old-version"
    assert result["source_bindings"][0]["captured_sha256"] == packet["artifacts"][0]["sha256"]
    assert json.loads((data / "evidence/old.json").read_text())["workspace_capture"]["binary_sha256"] == "f" * 64


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
