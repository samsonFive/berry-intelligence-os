"""Offline tests for transcript -> untrusted atomic Evidence proposals."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.transcript_evidence import (
    StructuredCandidateProvider,
    TranscriptArtifact,
    TranscriptContractError,
    TranscriptEvidenceExtractionService,
)


PARENT_ID = "ev-transcript-parent"


def _parent() -> dict:
    return {
        "id": PARENT_ID,
        "record_type": "evidence",
        "status": "published",
        "review_state": "published",
        "source_type": "industry_podcast",
        "title": "Synthetic parent artifact",
        "source_name": "Fixture Publisher",
        "source_url": "https://example.invalid/episode",
        "published_date": "2026-01-01",
        "captured_date": "2026-08-15",
        "summary": "Synthetic fixture only.",
        "submitted_by": "fixture",
        "source_id": "source-transcript-fixture",
        "evidence_role": "publication_artifact",
        "media_format": "podcast",
        "priority": {
            dimension: {"level": "none", "rationale": ""}
            for dimension in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def _transcript() -> TranscriptArtifact:
    return TranscriptArtifact.from_dict(
        {
            "transcript_id": "transcript-fixture-main",
            "parent_evidence_id": PARENT_ID,
            "language": "en",
            "provenance": {
                "method": "auto_generated",
                "created_by": "fixture transcript engine",
                "created_at": "2026-08-15",
            },
            "segments": [
                {"text": "Welcome to the show.", "start_seconds": 0, "end_seconds": 8, "speaker_label": "Host"},
                {
                    "text": "We may expand the trial depending on early results.",
                    "start_seconds": 750,
                    "end_seconds": 770,
                    "speaker_label": "Speaker A",
                },
                {
                    "text": "Approximately 20 hectares could be involved.",
                    "start_seconds": 770,
                    "end_seconds": 790,
                    "speaker_label": "Speaker A",
                },
                {
                    "text": "A separate market statement.",
                    "start_seconds": 900,
                    "end_seconds": 915,
                    "speaker_label": "Speaker B",
                },
            ],
        }
    )


def _setup(tmp_path: Path):
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    repos = main.get_repositories(data_dir, main.SCHEMAS_DIR)
    repos.sources.create({"id": "source-transcript-fixture", "name": "Fixture Publisher"})
    repos.evidence.create(_parent())
    for entity in (
        {"id": "company-transcript-fixture", "record_type": "entity", "entity_type": "company", "name": "Fixture Company", "status": "active"},
        {"id": "geography-transcript-fixture", "record_type": "entity", "entity_type": "geography", "name": "Fixture Geography", "status": "active"},
        {"id": "berry-transcript-fixture", "record_type": "entity", "entity_type": "berry", "name": "Fixture Berry", "status": "active"},
    ):
        repos.entities.create(entity)
    return repos, data_dir, inbox_dir


def _service(repos, inbox_dir: Path, candidates: list[dict], *, method: str = "ai_assisted"):
    validator = main.get_validator("evidence.schema.json")
    return TranscriptEvidenceExtractionService(
        repositories=repos,
        inbox_dir=inbox_dir,
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        provider=StructuredCandidateProvider(candidates, name="fixture extractor", method=method),
        today=lambda: date(2026, 8, 15),
    )


def _candidate(statement: str, indexes: list[int], **links) -> dict:
    return {
        "normalized_statement": statement,
        "segment_indexes": indexes,
        "entity_ids": links.get("entity_ids", []),
        "geography_ids": links.get("geography_ids", []),
        "berry_ids": links.get("berry_ids", []),
    }


def _drafts(inbox_dir: Path) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((inbox_dir / "evidence").glob("*.json"))]


def test_no_meaningful_ci_content_produces_zero_proposals(tmp_path: Path) -> None:
    repos, _, inbox = _setup(tmp_path)
    result = _service(repos, inbox, []).run(_transcript())
    assert result.candidates_found == 0
    assert result.accepted == result.duplicates == result.invalid == []
    assert not (inbox / "evidence").exists()


def test_one_candidate_preserves_qualifiers_timestamp_speaker_links_and_provenance(tmp_path: Path) -> None:
    repos, _, inbox = _setup(tmp_path)
    candidate = _candidate(
        "The company may expand the trial depending on early results.",
        [1, 2],
        entity_ids=["company-transcript-fixture"],
        geography_ids=["geography-transcript-fixture"],
        berry_ids=["berry-transcript-fixture"],
    )
    result = _service(repos, inbox, [candidate]).run(_transcript())
    assert len(result.accepted) == 1
    proposal = _drafts(inbox)[0]
    assert proposal["status"] == "draft"
    assert proposal["review_state"] == "in_review"
    assert proposal["evidence_role"] == "atomic_evidence"
    assert proposal["parent_evidence_id"] == PARENT_ID
    assert proposal["summary"] == candidate["normalized_statement"]
    assert "may" in proposal["summary"] and "depending on" in proposal["summary"]
    assert proposal["artifact_locator"] == {
        "start_seconds": 750.0,
        "end_seconds": 790.0,
        "speaker_label": "Speaker A",
    }
    assert proposal["entity_ids"] == ["company-transcript-fixture", "geography-transcript-fixture"]
    assert proposal["geography_ids"] == ["geography-transcript-fixture"]
    assert proposal["berry_ids"] == ["berry-transcript-fixture"]
    assert proposal["transcript_provenance"]["segment_indexes"] == [1, 2]
    assert proposal["transcript_provenance"]["transcript_id"] == "transcript-fixture-main"
    assert len(proposal["transcript_provenance"]["transcript_sha256"]) == 64
    assert "Speaker A: We may expand" in proposal["transcript_excerpt"]
    assert proposal["extraction_provenance"]["method"] == "ai_assisted"
    assert repos.evidence.get(proposal["id"]) is None
    assert not list((tmp_path / "data" / "facts").glob("*.json"))
    assert not list((tmp_path / "data" / "assessments").glob("*.json"))


def test_multiple_statements_create_multiple_independent_proposals(tmp_path: Path) -> None:
    repos, _, inbox = _setup(tmp_path)
    candidates = [
        _candidate("One qualified statement may occur.", [1]),
        _candidate("Approximately 20 hectares could be involved.", [2]),
        _candidate("A separate market statement.", [3]),
    ]
    result = _service(repos, inbox, candidates).run(_transcript())
    assert len(result.accepted) == 3
    drafts = _drafts(inbox)
    assert len({draft["id"] for draft in drafts}) == 3
    assert {draft["artifact_locator"]["start_seconds"] for draft in drafts} == {750.0, 770.0, 900.0}


def test_malformed_and_unsupported_model_outputs_are_rejected_before_inbox(tmp_path: Path) -> None:
    repos, _, inbox = _setup(tmp_path)
    candidates = [
        _candidate("", [1]),
        _candidate("Bad span.", [2, 1]),
        _candidate("Unknown entity.", [1], entity_ids=["company-does-not-exist"]),
        _candidate("Wrong geography type.", [1], geography_ids=["company-transcript-fixture"]),
        {"normalized_statement": "Missing segment references."},
    ]
    result = _service(repos, inbox, candidates).run(_transcript())
    assert result.candidates_found == 5
    assert len(result.invalid) == 5
    assert result.accepted == []
    assert not (inbox / "evidence").exists()


def test_invalid_transcript_and_parent_are_rejected() -> None:
    try:
        TranscriptArtifact.from_dict(
            {
                "transcript_id": "transcript-invalid-span",
                "parent_evidence_id": PARENT_ID,
                "language": "en",
                "provenance": {"method": "auto_generated", "created_by": "x", "created_at": "2026-08-15"},
                "segments": [{"text": "x", "start_seconds": 20, "end_seconds": 10}],
            }
        )
    except TranscriptContractError as exc:
        assert "end_seconds" in str(exc)
    else:
        raise AssertionError("invalid transcript unexpectedly accepted")
    try:
        TranscriptArtifact.from_dict(
            {
                "transcript_id": "transcript-invalid-date",
                "parent_evidence_id": PARENT_ID,
                "language": "en",
                "provenance": {"method": "auto_generated", "created_by": "x", "created_at": "not-a-date"},
                "segments": [{"text": "x", "start_seconds": 0}],
            }
        )
    except TranscriptContractError as exc:
        assert "ISO date" in str(exc)
    else:
        raise AssertionError("invalid transcript provenance date unexpectedly accepted")


def test_repeated_extraction_is_idempotent_even_after_rejection(tmp_path: Path) -> None:
    repos, _, inbox = _setup(tmp_path)
    candidate = _candidate("The plan may change.", [1])
    service = _service(repos, inbox, [candidate])
    first = service.run(_transcript())
    second = service.run(_transcript())
    assert len(first.accepted) == 1
    assert second.accepted == []
    assert second.duplicates == first.accepted

    path = inbox / "evidence" / f"{first.accepted[0]}.json"
    rejected = json.loads(path.read_text(encoding="utf-8"))
    rejected["status"] = rejected["review_state"] = "rejected"
    path.write_text(json.dumps(rejected), encoding="utf-8")
    third = service.run(_transcript())
    assert third.duplicates == first.accepted
    assert len(_drafts(inbox)) == 1


def test_three_extracted_proposals_use_existing_review_and_downstream_lineage(monkeypatch, tmp_path: Path) -> None:
    repos, data_dir, inbox = _setup(tmp_path)
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    candidates = [
        _candidate("Proposal A.", [1], entity_ids=["company-transcript-fixture"]),
        _candidate("Proposal B may change.", [2], geography_ids=["geography-transcript-fixture"]),
        _candidate("Proposal C.", [3]),
    ]
    result = _service(repos, inbox, candidates).run(_transcript())
    by_summary = {draft["summary"]: draft for draft in _drafts(inbox)}
    proposal_a = by_summary["Proposal A."]
    proposal_b = by_summary["Proposal B may change."]
    proposal_c = by_summary["Proposal C."]
    client = TestClient(app)

    review_a = client.get(f"/review/{proposal_a['id']}")
    review_b = client.get(f"/review/{proposal_b['id']}")
    assert "Fixture Company" in review_a.text
    assert "Fixture Geography" in review_b.text
    approved_a = client.post(
        f"/review/{proposal_a['id']}/publish",
        data={
            "title": proposal_a["title"],
            "source_type": proposal_a["source_type"],
            "source_name": proposal_a["source_name"],
            "source_url": proposal_a["source_url"],
            "published_date": proposal_a["published_date"],
            "captured_date": proposal_a["captured_date"],
            "summary": proposal_a["summary"],
            "companies": "Fixture Company",
            "fact_statement_1": "Synthetic reviewed Fact.",
            "fact_classification_1": "fact",
            "fact_confidence_1": "medium",
            "reviewer": "reviewer-a",
        },
        follow_redirects=False,
    )
    approved_b = client.post(
        f"/review/{proposal_b['id']}/publish",
        data={
            "title": "Human-edited proposal B",
            "source_type": proposal_b["source_type"],
            "source_name": proposal_b["source_name"],
            "source_url": proposal_b["source_url"],
            "published_date": proposal_b["published_date"],
            "captured_date": proposal_b["captured_date"],
            "summary": "Human-edited proposal B remains qualified: may change.",
            "geographies": "Fixture Geography",
            "reviewer": "reviewer-b",
        },
        follow_redirects=False,
    )
    rejected_c = client.post(
        f"/review/{proposal_c['id']}/reject",
        data={"reviewer": "reviewer-c", "rejection_reason": "Insufficient fixture support."},
        follow_redirects=False,
    )

    assert approved_a.status_code == approved_b.status_code == rejected_c.status_code == 303
    trusted_a = repos.evidence.get(proposal_a["id"])
    trusted_b = repos.evidence.get(proposal_b["id"])
    assert trusted_a["evidence_role"] == trusted_b["evidence_role"] == "atomic_evidence"
    assert trusted_a["parent_evidence_id"] == trusted_b["parent_evidence_id"] == PARENT_ID
    assert trusted_b["summary"].startswith("Human-edited")
    assert repos.evidence.get(proposal_c["id"]) is None
    assert main.get_draft(proposal_c["id"])["review_state"] == "rejected"
    assert repos.evidence.get(PARENT_ID)["status"] == "published"
    detail = client.get(f"/evidence/{trusted_a['id']}")
    assert "Transcript provenance" in detail.text
    assert "Extraction provenance" in detail.text
    assert "Supporting transcript excerpt" in detail.text

    fact = repos.facts.get(f"fact-{proposal_a['id'][3:]}-1")
    assessment = repos.assessments.create(
        {
            "id": "assessment-transcript-extraction-fixture",
            "record_type": "assessment",
            "title": "Synthetic lineage fixture",
            "rationale": "Fixture only.",
            "status": "active",
            "confidence": "medium",
            "fact_ids": [fact["id"]],
            "reviewer": "reviewer-a",
            "created_at": "2026-08-15",
        }
    )
    lineage = main.get_query_services(data_dir, main.SCHEMAS_DIR).lineage
    assert lineage.resolve_linked_facts(assessment["fact_ids"])[0]["evidence_ids"] == [trusted_a["id"]]
    assert lineage.resolve_linked_evidence(fact["evidence_ids"])[0]["parent_evidence_id"] == PARENT_ID
    assert len(result.accepted) == 3


def test_real_lucentlands_parent_is_compatible_without_production_proposals(tmp_path: Path) -> None:
    live_repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    parent = live_repos.evidence.get("ev-lucentlands-scaling-blueberry-industry-2025")
    assert parent["evidence_role"] == "publication_artifact"
    transcript = TranscriptArtifact.from_dict(
        {
            "transcript_id": "transcript-lucentlands-compatibility-fixture",
            "parent_evidence_id": parent["id"],
            "language": "en",
            "provenance": {"method": "human_provided", "created_by": "fixture", "created_at": "2026-08-15"},
            "segments": [{"text": "Synthetic compatibility fixture.", "start_seconds": 0, "end_seconds": 1}],
        }
    )
    result = _service(live_repos, tmp_path / "inbox", []).run(transcript)
    assert result.candidates_found == 0
    assert not (tmp_path / "inbox" / "evidence").exists()


def test_cli_reports_acceptance_then_duplicate(monkeypatch, tmp_path: Path, capsys) -> None:
    _, data_dir, inbox = _setup(tmp_path)
    transcript_path = tmp_path / "transcript.json"
    candidates_path = tmp_path / "candidates.json"
    transcript_path.write_text(
        json.dumps(
            {
                "transcript_id": "transcript-cli-fixture",
                "language": "en",
                "provenance": {
                    "method": "human_provided",
                    "created_by": "fixture",
                    "created_at": "2026-08-15",
                },
                "segments": [
                    {"text": "A plan may change.", "start_seconds": 5, "end_seconds": 9, "speaker_label": "Speaker A"}
                ],
            }
        ),
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps([_candidate("The plan may change.", [0])]),
        encoding="utf-8",
    )
    import scripts.extract_transcript_evidence as runner

    argv = [
        "extract_transcript_evidence.py",
        "--transcript",
        str(transcript_path),
        "--parent-evidence",
        PARENT_ID,
        "--candidates",
        str(candidates_path),
        "--data-dir",
        str(data_dir),
        "--inbox-dir",
        str(inbox),
    ]
    monkeypatch.setattr("sys.argv", argv)
    assert runner.main() == 0
    assert "Accepted into inbox: 1" in capsys.readouterr().out
    assert runner.main() == 0
    second_output = capsys.readouterr().out
    assert "Accepted into inbox: 0" in second_output
    assert "Duplicates: 1" in second_output
