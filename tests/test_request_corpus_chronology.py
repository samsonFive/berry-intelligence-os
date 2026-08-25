"""Focused tests for request-scoped corpus, chronology, and repo cache size."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from app.repositories.json.base import JsonRecordRepository
from app.services.chronology import (
    FORBIDDEN_FRESHNESS,
    date_label,
    development_stamp,
    meaningful_stamp,
)
from app.services.request_corpus import (
    RequestCorpus,
    bind_request_corpus,
    get_request_corpus,
    reset_request_corpus,
    should_skip_corpus,
)


def test_should_skip_corpus_for_light_paths() -> None:
    assert should_skip_corpus("/login")
    assert should_skip_corpus("/healthz")
    assert should_skip_corpus("/static/app.css")
    assert not should_skip_corpus("/work-queue")
    assert not should_skip_corpus("/brief")


def test_request_corpus_lazy_and_indexed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "evidence").mkdir(parents=True)
    (data / "entities").mkdir(parents=True)
    (data / "facts").mkdir(parents=True)
    (data / "signals").mkdir(parents=True)
    (data / "assessments").mkdir(parents=True)
    (data / "relationships").mkdir(parents=True)
    (data / "recommendations").mkdir(parents=True)
    (data / "strategic-questions").mkdir(parents=True)
    (data / "configuration").mkdir(parents=True)
    (data / "configuration" / "sources.json").write_text("[]\n", encoding="utf-8")

    evidence = {
        "id": "ev-1",
        "status": "published",
        "title": "One",
        "published_date": "2026-08-01",
        "entity_ids": ["company-a"],
        "geography_ids": ["geo-chile"],
    }
    (data / "evidence" / "ev-1.json").write_text(json.dumps(evidence), encoding="utf-8")
    (data / "entities" / "company-a.json").write_text(
        json.dumps({"id": "company-a", "name": "A", "entity_type": "company"}),
        encoding="utf-8",
    )
    (data / "entities" / "geo-chile.json").write_text(
        json.dumps({"id": "geo-chile", "name": "Chile", "entity_type": "geography"}),
        encoding="utf-8",
    )
    (data / "facts" / "f-1.json").write_text(
        json.dumps({"id": "f-1", "entity_ids": ["company-a"], "statement": "x"}),
        encoding="utf-8",
    )
    (data / "signals" / "s-1.json").write_text(
        json.dumps({"id": "s-1", "entity_ids": ["company-a"], "title": "sig"}),
        encoding="utf-8",
    )
    (data / "assessments" / "a-1.json").write_text(
        json.dumps({"id": "a-1", "entity_ids": ["company-a"], "title": "as"}),
        encoding="utf-8",
    )
    (data / "relationships" / "r-1.json").write_text(
        json.dumps(
            {
                "id": "r-1",
                "subject_id": "company-a",
                "object_id": "geo-chile",
                "predicate": "operates_in",
            }
        ),
        encoding="utf-8",
    )

    schemas = Path(__file__).resolve().parents[1] / "schemas"
    corpus = RequestCorpus(data_dir=data, schemas_dir=schemas)
    token = bind_request_corpus(corpus)
    try:
        assert get_request_corpus() is corpus
        assert corpus._evidence is None
        rows = corpus.published_evidence
        assert len(rows) == 1
        assert corpus.evidence_for_entity("company-a")[0]["id"] == "ev-1"
        assert corpus.evidence_for_entity("geo-chile")[0]["id"] == "ev-1"
        assert corpus.facts_for_entity("company-a")[0]["id"] == "f-1"
        assert corpus.signals_for_entity("company-a")[0]["id"] == "s-1"
        assert corpus.assessments_for_entity("company-a")[0]["id"] == "a-1"
        assert {r["id"] for r in corpus.relationships_for_entity("company-a")} == {"r-1"}
        assert {r["id"] for r in corpus.relationships_for_entity("geo-chile")} == {"r-1"}
        # Second access reuses the same list object (no second deepcopy).
        assert corpus.published_evidence is rows
    finally:
        reset_request_corpus(token)
    assert get_request_corpus() is None


def test_chronology_ignores_forbidden_freshness_and_labels() -> None:
    assert FORBIDDEN_FRESHNESS == ("reacquired_at", "recovered_at", "reviewed_at", "indexed_at")
    historic = {
        "published_date": "2023-03-01",
        "captured_date": "2026-08-24",
        "reacquired_at": "2026-08-24T12:00:00+00:00",
        "reviewed_at": "2026-08-24",
        "recovered_at": "2026-08-24",
        "indexed_at": "2026-08-24",
    }
    when, origin = meaningful_stamp(historic)
    assert origin == "published"
    assert when is not None and when.year == 2023
    assert date_label(origin) == "Published"

    captured_only = {"captured_date": "2026-08-23"}
    when, origin = development_stamp(captured_only)
    assert origin == "captured"
    assert date_label(origin) == "Captured"

    observed = {
        "commercial_observation": {"observed_at": "2026-07-01"},
        "published_date": "2026-01-01",
        "captured_date": "2026-08-01",
    }
    when, origin = meaningful_stamp(observed, mode="commercial")
    assert origin == "observed"
    assert when is not None and when.month == 7
    assert date_label(origin) == "Observed"

    filed = {"filing_date": "2024-05-01", "source_type": "patent_record"}
    when, origin = meaningful_stamp(filed, mode="patent")
    assert origin == "filed"
    assert date_label(origin) == "Filed"

    # Capture must not masquerade as published when timeline_evidence mode.
    when, origin = meaningful_stamp({"captured_date": "2026-08-23"}, mode="timeline_evidence")
    assert when is None and origin == ""


def test_json_repo_cache_includes_st_size(tmp_path: Path) -> None:
    folder = tmp_path / "records"
    folder.mkdir()
    path = folder / "one.json"
    path.write_text('{"id": "one", "status": "draft"}\n', encoding="utf-8")
    repo = JsonRecordRepository(folder)
    first = repo.list()
    assert first[0]["status"] == "draft"
    path.write_text('{"id": "one", "status": "rejected"}\n', encoding="utf-8")
    original = path.stat()
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert path.stat().st_mtime_ns == original.st_mtime_ns
    second = repo.list()
    assert second[0]["status"] == "rejected"