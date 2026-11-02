"""Handoff integrity tests only; these do not demonstrate Stage 2 research."""
import importlib
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "competitive-landscape-2026-10-30-v1"
REL = Path("data/imports") / VERSION


@pytest.fixture
def packet(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    validator = importlib.import_module("validate_competitive_landscape_handoff")
    shutil.copytree(ROOT / REL, tmp_path / REL)
    shutil.copytree(ROOT / "docs/research" / VERSION, tmp_path / "docs/research" / VERSION)
    return tmp_path, validator


def update(path, transform):
    row = json.loads(path.read_text(encoding="utf-8"))
    transform(row)
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_full_canonical_ecosystem_covered_once(packet):
    root, validator = packet
    assert validator.validate(root, root / REL, check_inputs=False) == []
    inventory = json.loads((root / REL / "commercial-entity-inventory.json").read_text(encoding="utf-8"))
    rows = {e["entity_id"]: e for e in inventory["entities"]}
    assert {p.stem for p in (ROOT / "data/entities/companies").glob("*.json")} <= rows.keys()
    assert rows["company-example-genetics"]["inclusion_status"] == "out_of_scope"
    assert rows["company-genetics-uruguay"]["official_domain"] is None
    assert rows["company-genetics-uruguay"]["inclusion_status"] == "unresolved_identity"


def test_missing_batch_is_visible(packet):
    root, validator = packet
    update(root / REL / "research-coverage-checklist.json", lambda d: d["batches"].pop())
    assert any("Batch coverage mismatch" in e for e in validator.validate(root, root / REL, check_inputs=False))


def test_inventory_drift_is_not_silently_accepted(packet):
    root, validator = packet
    update(root / REL / "commercial-entity-inventory.json", lambda d: d.update(snapshot_date="2099-01-01"))
    assert any("Inventory differs" in e for e in validator.validate(root, root / REL, check_inputs=False))


def test_prompt_corruption_is_visible(packet):
    root, validator = packet
    manifest = json.loads((root / REL / "research-coverage-checklist.json").read_text(encoding="utf-8"))
    prompt = root / manifest["batches"][0]["prompt_file"]
    prompt.write_text(prompt.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8")
    assert any("Prompt hash mismatch" in e for e in validator.validate(root, root / REL, check_inputs=False))


def test_rehashed_private_field_still_fails_public_contract(packet):
    root, validator = packet
    manifest_path = root / REL / "research-coverage-checklist.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt = root / manifest["batches"][0]["prompt_file"]
    text = prompt.read_text(encoding="utf-8").replace('"legal_name": null,', '"private_notes": "private", "legal_name": null,', 1)
    prompt.write_text(text, encoding="utf-8")
    manifest["batches"][0]["prompt_sha256"] = validator.text_sha256(prompt)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert any("Public inventory mismatch" in e for e in validator.validate(root, root / REL, check_inputs=False))


def test_geography_context_is_not_promoted_to_production_or_sales(packet):
    root, _ = packet
    inventory = json.loads((root / REL / "commercial-entity-inventory.json").read_text(encoding="utf-8"))
    driscolls = next(e for e in inventory["entities"] if e["entity_id"] == "company-driscolls")
    assert driscolls["geographic_context_relationships"]
    assert driscolls["production_origins"] == driscolls["destination_markets"] == []
    assert driscolls["origin_status"] == driscolls["destination_status"] == "unknown"
    assert {"breeder", "marketer"} <= set(driscolls["peer_roles"])


def test_import_only_sources_are_not_marked_as_missing_or_trusted(packet):
    root, _ = packet
    inventory = json.loads((root / REL / "commercial-entity-inventory.json").read_text(encoding="utf-8"))
    ohalo = next(e for e in inventory["entities"] if e["entity_id"] == "company-ohalo")
    assert ohalo["import_only_evidence_ids"]
    assert not ohalo["missing_evidence_ids"]
    assert all(e["status"] != "published" for e in ohalo["import_evidence_dates"])


def test_fingerprints_survive_windows_unix_line_endings(packet):
    root, validator = packet
    path = root / "newline-check.txt"
    path.write_bytes(b"one\r\ntwo\r\n")
    before = validator.text_sha256(path)
    path.write_bytes(b"one\ntwo\n")
    assert validator.text_sha256(path) == before
