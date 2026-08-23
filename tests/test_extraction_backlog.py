from __future__ import annotations

from copy import deepcopy

from app.services.extraction_backlog import (
    UNBOUND_QUALIFICATION,
    build_manifest,
    classify_record,
    inventory,
)


def _record(record_id: str, **overrides):
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "published",
        "source_type": "trade_press",
        "title": f"Title {record_id}",
        "source_name": "Trade Press",
        "source_url": f"https://example.com/{record_id}",
        "published_date": "2026-08-01",
        "captured_date": "2026-08-02",
        "summary": f"Thin summary for {record_id}.",
        "submitted_by": "test",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "priority": {},
    }
    record.update(overrides)
    return record


def test_readiness_prefers_full_body_over_summary():
    record = _record(
        "ev-body",
        article={"paragraphs": [{"index": 0, "text": "Full article body. " * 40}]},
    )
    item = classify_record(record)
    assert item["readiness"] == "READY_FULL_ARTICLE"
    assert item["source_chars"] > len(record["summary"])
    assert item["source_sha256"]


def test_transcript_is_ready_and_uses_explicit_language():
    record = _record(
        "ev-transcript",
        source_type="industry_podcast",
        media_format="podcast",
        transcript={"status": "available", "language": "ES", "text": "Transcript source text."},
    )
    item = classify_record(record)
    assert item["readiness"] == "READY_TRANSCRIPT"
    assert item["language"] == "es"


def test_summary_only_is_thin_and_language_is_not_guessed():
    item = classify_record(_record("ev-thin", summary="Este texto no establece metadata de idioma."))
    assert item["readiness"] == "THIN_DESCRIPTION_ONLY"
    assert item["language"] == "undetermined"

    encoded = classify_record(_record("ev-encoded", summary="Owner claim&nbsp;with encoded punctuation."))
    assert encoded["readiness"] == "THIN_DESCRIPTION_ONLY"


def test_registry_summary_is_structured_ready():
    item = classify_record(_record("ev-registry", source_type="patent_record"))
    assert item["readiness"] == "READY_STRUCTURED_REGISTRY"
    assert item["source_class"] == "REGISTRY_STRUCTURED"


def test_exact_duplicate_is_excluded_deterministically():
    first = _record("ev-a", source_url="https://example.com/shared")
    second = _record("ev-b", source_url="https://example.com/shared")
    report = inventory([second, first])
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["ev-b"]["readiness"] == "DUPLICATE_OR_SUPERSEDED"
    assert by_id["ev-b"]["duplicate_of"] == "ev-a"


def test_repeated_thin_boilerplate_is_not_mislabeled_as_duplicate():
    first = _record("ev-a", summary="Repeated publisher boilerplate that is long enough to hash. " * 2)
    second = _record("ev-b", summary=first["summary"])
    report = inventory([first, second])
    assert report["duplicates_skipped"] == 0
    assert report["repeated_thin_source_hash_excess"] == 1


def test_manifest_is_stable_diverse_hash_bound_and_contains_no_source_text():
    records = []
    berries = ("blueberry", "strawberry", "raspberry", "blackberry")
    for index in range(12):
        berry = berries[index % len(berries)]
        records.append(
            _record(
                f"ev-registry-{index:02d}",
                source_type="government_registry",
                berry_ids=[f"berry-{berry}"],
                summary=(f"Registry observation {index}. " * (5 + index)),
            )
        )
    report = inventory(records)
    first = build_manifest(report, 10)
    second = build_manifest(deepcopy(report), 10)
    assert first == second
    assert set(first["mix"]["berry"]) == {"Blueberry", "Strawberry", "Raspberry", "Blackberry"}
    assert all(entry["source_sha256"] for entry in first["sources"])
    assert all("source_text" not in entry for entry in first["sources"])
    assert first["qualification_identity"] == UNBOUND_QUALIFICATION
    assert first["execution_contract"]["auto_publish"] is False


def test_manifest_does_not_mutate_trust_records():
    records = [_record("ev-registry", source_type="government_registry")]
    original = deepcopy(records)
    report = inventory(records)
    build_manifest(report, 10)
    assert records == original
    assert records[0]["status"] == "published"


def test_known_fictional_seed_is_never_ready():
    item = classify_record(_record("ev-sample-patent-published", source_type="patent"))
    assert item["readiness"] == "UNSUPPORTED_ARTIFACT"
    assert item["fidelity_cause"] == "known_fictional_seed"
