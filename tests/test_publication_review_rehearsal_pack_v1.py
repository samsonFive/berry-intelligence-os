"""Publication Review Candidate Inventory and Rehearsal Pack V1.

Validates that the noncanonical rehearsal pack under
data/imports/publication-review-rehearsal-2026-09-16/ is exactly what it
claims to be: a bounded, 10-item, safety-checked set that no repository
loader, record validator, or canonical data path can accidentally ingest.
This module never approves, publishes, or promotes anything -- it only
inspects the pack's own committed content.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR

REPO = Path(__file__).resolve().parents[1]
REHEARSAL_DIR = REPO / "data" / "imports" / "publication-review-rehearsal-2026-09-16"
ITEMS_DIR = REHEARSAL_DIR / "items"

_FORBIDDEN_CONTENT_SIGNALS = (
    "<html", "<body", "<script", "set-cookie", "authorization:", "api_key", "api-key", "password",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rehearsal_items() -> list[dict]:
    paths = sorted(ITEMS_DIR.glob("*.json"))
    assert paths, "rehearsal pack items directory is empty or missing"
    return [_load(p) for p in paths]


def test_rehearsal_pack_has_exactly_ten_items(rehearsal_items):
    assert len(rehearsal_items) == 10


def test_rehearsal_pack_covers_all_ten_required_decision_types(rehearsal_items):
    expected = {
        "clearly_readable_article", "transcript_backed_item", "metadata_only_item",
        "navigation_only_shell", "uncertain_publication_date", "missing_or_weak_entity_match",
        "duplicate_probable_duplicate", "corrected_or_upgraded_acquisition", "rejection_candidate",
        "defer_or_correction_required",
    }
    actual = {item["decision_type"] for item in rehearsal_items}
    assert actual == expected


def test_every_item_declares_synthetic_or_real_provenance(rehearsal_items):
    for item in rehearsal_items:
        meta = item["rehearsal_metadata"]
        assert isinstance(meta["synthetic"], bool)
        if meta["synthetic"]:
            assert meta["grounded_in"], f"{item['record']['id']} is synthetic but cites no real basis"
        else:
            assert meta["real_run_reference"], f"{item['record']['id']} is real but cites no run reference"


def test_every_item_carries_the_full_required_analysis(rehearsal_items):
    required_fields = {
        "source", "discovery_acquisition_path", "content_state", "provenance_completeness",
        "publication_date_confidence", "body_transcript_availability", "entity_association",
        "duplicate_risk", "warnings", "recommended_operator_action", "why_not_automatic",
    }
    for item in rehearsal_items:
        assert required_fields <= set(item["analysis"].keys()), item["record"]["id"]
        assert item["analysis"]["why_not_automatic"].strip()


def test_no_forbidden_content_anywhere_in_the_pack(rehearsal_items):
    for path in ITEMS_DIR.glob("*.json"):
        text = path.read_text(encoding="utf-8").casefold()
        for signal in _FORBIDDEN_CONTENT_SIGNALS:
            assert signal not in text, f"{path.name} contains forbidden signal {signal!r}"


def test_synthetic_source_urls_are_reserved_non_resolving_placeholders(rehearsal_items):
    for item in rehearsal_items:
        if not item["rehearsal_metadata"]["synthetic"]:
            continue
        url = item["record"].get("source_url") or ""
        assert "example.invalid" in url, f"{item['record']['id']} synthetic source_url is not a reserved placeholder: {url}"


def test_synthetic_bodies_are_short_and_never_a_real_scraped_length(rehearsal_items):
    """A short, clearly-invented excerpt is permitted; a full-length scraped
    body (hundreds of words of actual stored text) is not. Checks the
    actual stored paragraph text length, not any fictional `word_count`
    metadata value a fixture may carry to represent a scenario (e.g. item 5
    intentionally omits its body text with a placeholder while still
    recording a representative word_count for the scenario it models)."""
    for item in rehearsal_items:
        if not item["rehearsal_metadata"]["synthetic"]:
            continue
        article = item["record"].get("article")
        if article:
            stored_text = " ".join(p["text"] for p in article.get("paragraphs", []))
            actual_words = len(stored_text.split())
            assert actual_words < 150, (
                f"{item['record']['id']} synthetic article body stores an implausibly long "
                f"actual excerpt ({actual_words} words) for a short fixture"
            )


def test_no_two_items_share_a_url_or_content_hash(rehearsal_items):
    urls = [item["record"].get("source_url") for item in rehearsal_items if item["record"].get("source_url")]
    assert len(urls) == len(set(urls))
    hashes = [
        item["record"]["article"]["content_sha256"]
        for item in rehearsal_items
        if item["record"].get("article", {}).get("content_sha256")
    ]
    assert len(hashes) == len(set(hashes))


def test_rehearsal_index_matches_the_item_files(rehearsal_items):
    index = _load(REHEARSAL_DIR / "rehearsal-pack-index.json")
    assert index["noncanonical"] is True
    assert index["review_required"] is True
    indexed_ids = {row["id"] for row in index["items"]}
    item_ids = {item["record"]["id"] for item in rehearsal_items}
    assert indexed_ids == item_ids


# ---------------------------------------------------------------------------
# The mission's own explicit safety requirement: rehearsal data must never
# be loadable as canonical data by accident.
# ---------------------------------------------------------------------------


def test_rehearsal_items_do_not_validate_as_evidence_records(rehearsal_items):
    """Each rehearsal file's top-level shape ({rehearsal_slot, decision_type,
    rehearsal_metadata, record, analysis}) is deliberately NOT a bare
    Evidence record -- a tool that pointed evidence.schema.json at one of
    these files directly (skipping the real nested "record" field) would
    fail validation immediately, rather than silently accepting rehearsal
    data as if it were real Evidence."""
    schema = json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    for item in rehearsal_items:
        errors = list(validator.iter_errors(item))
        assert errors, f"{item['record']['id']}'s wrapper unexpectedly validated as a bare Evidence record"


def test_no_repository_loader_reads_data_imports(rehearsal_items):
    """The real EvidenceRepository (and by extension every route/service
    built on get_repositories()) only ever reads data/evidence -- confirm
    directly that none of the 10 rehearsal ids appear in a live load
    against this repository's own real data/ directory."""
    repositories = get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR)
    trusted_ids = {row["id"] for row in repositories.evidence.list()}
    rehearsal_ids = {item["record"]["id"] for item in rehearsal_items}
    assert trusted_ids.isdisjoint(rehearsal_ids)


def test_validate_records_never_scans_data_imports():
    """scripts/validate_records.py's own folder list is fixed and does not
    include data/imports -- read directly from the script's source rather
    than re-deriving the list, so this test fails loudly if a future edit
    ever adds an imports scan without updating this guard."""
    source = (REPO / "scripts" / "validate_records.py").read_text(encoding="utf-8")
    folders = re.findall(r'ROOT / "data" / "([a-z-]+)"', source)
    assert "imports" not in folders
    assert set(folders) == {
        "evidence", "entities", "facts", "relationships", "strategic-questions",
        "signals", "assessments", "recommendations",
    }


def test_validate_records_passes_with_the_rehearsal_pack_present():
    """A direct, end-to-end proof rather than an inference: run the real
    validator with the rehearsal pack committed and confirm it still
    reports success -- the rehearsal pack's non-schema-shaped JSON under
    data/imports/ must never trip record validation."""
    result = subprocess.run(
        [sys.executable, "scripts/validate_records.py"], cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All validated records passed." in result.stdout


def test_no_canonical_data_directory_changed_by_this_mission():
    for path in (
        "data/entities", "data/relationships", "data/evidence", "data/facts", "data/signals",
        "data/assessments", "data/recommendations", "data/strategic-questions", "data/configuration",
    ):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={REPO}", "status", "--porcelain", "--", path],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        assert result.stdout.strip() == "", f"unexpected changes under {path}: {result.stdout}"
