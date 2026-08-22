"""Provider-neutral transcript -> atomic Evidence proposal service.

This module starts at an already-available structured transcript. It does
not discover media, download audio, transcribe speech, or publish Evidence.
Providers only propose structured candidates; this service owns deterministic
validation, provenance, identity, dedupe, and inbox persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Protocol
import unicodedata


EXTRACTION_INSTRUCTIONS = """Extract only discrete, decision-relevant statements supported by the transcript.
Return no candidate for non-CI discussion. Preserve qualifiers and attribution. Split independent claims.
Reference the exact supporting transcript segment indexes. Do not invent entity, geography, or berry IDs.
Do not create Facts, Relationships, Assessments, Recommendations, or trusted Evidence."""

PRIORITY_NONE = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


class TranscriptContractError(ValueError):
    pass


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_seconds: float
    end_seconds: float | None = None
    speaker_label: str | None = None


@dataclass(frozen=True)
class TranscriptProvenance:
    method: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class TranscriptArtifact:
    transcript_id: str
    parent_evidence_id: str
    language: str
    provenance: TranscriptProvenance
    segments: tuple[TranscriptSegment, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TranscriptArtifact":
        if not isinstance(payload, dict):
            raise TranscriptContractError("transcript must be an object")
        errors: list[str] = []
        transcript_id = payload.get("transcript_id")
        parent_id = payload.get("parent_evidence_id")
        language = payload.get("language")
        provenance = payload.get("provenance")
        raw_segments = payload.get("segments")
        if not isinstance(transcript_id, str) or not transcript_id.strip():
            errors.append("transcript_id is required")
        if not isinstance(parent_id, str) or not re.fullmatch(r"ev-[a-z0-9-]+", parent_id):
            errors.append("parent_evidence_id must be an Evidence id")
        if not isinstance(language, str) or not language.strip():
            errors.append("language is required")
        if not isinstance(provenance, dict):
            errors.append("provenance is required")
            provenance = {}
        method = provenance.get("method")
        if method not in {"publisher_provided", "human_provided", "auto_generated"}:
            errors.append("provenance.method is invalid")
        if not isinstance(provenance.get("created_by"), str) or not provenance.get("created_by", "").strip():
            errors.append("provenance.created_by is required")
        if not isinstance(provenance.get("created_at"), str) or not provenance.get("created_at", "").strip():
            errors.append("provenance.created_at is required")
        else:
            try:
                date.fromisoformat(provenance["created_at"])
            except ValueError:
                errors.append("provenance.created_at must be an ISO date")
        if not isinstance(raw_segments, list) or not raw_segments:
            errors.append("segments must be a non-empty list")
            raw_segments = []

        segments: list[TranscriptSegment] = []
        previous_start = -1.0
        for index, raw in enumerate(raw_segments):
            if not isinstance(raw, dict):
                errors.append(f"segments[{index}] must be an object")
                continue
            text = raw.get("text")
            start = raw.get("start_seconds")
            end = raw.get("end_seconds")
            speaker = raw.get("speaker_label")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"segments[{index}].text is required")
            if not isinstance(start, (int, float)) or isinstance(start, bool) or start < 0:
                errors.append(f"segments[{index}].start_seconds is invalid")
                continue
            if start < previous_start:
                errors.append("segments must be ordered by start_seconds")
            previous_start = float(start)
            if end is not None and (
                not isinstance(end, (int, float)) or isinstance(end, bool) or end < start
            ):
                errors.append(f"segments[{index}].end_seconds must be >= start_seconds")
            if speaker is not None and not isinstance(speaker, str):
                errors.append(f"segments[{index}].speaker_label must be a string or null")
            segments.append(
                TranscriptSegment(
                    text=text.strip() if isinstance(text, str) else "",
                    start_seconds=float(start),
                    end_seconds=float(end) if isinstance(end, (int, float)) else None,
                    speaker_label=speaker.strip() if isinstance(speaker, str) and speaker.strip() else None,
                )
            )
        if errors:
            raise TranscriptContractError("; ".join(errors))
        return cls(
            transcript_id=transcript_id.strip(),
            parent_evidence_id=parent_id,
            language=language.strip(),
            provenance=TranscriptProvenance(
                method=method,
                created_by=provenance["created_by"].strip(),
                created_at=provenance["created_at"].strip(),
            ),
            segments=tuple(segments),
        )

    def content_sha256(self) -> str:
        payload = [
            {
                "text": segment.text,
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "speaker_label": segment.speaker_label,
            }
            for segment in self.segments
        ]
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractionRequest:
    transcript: TranscriptArtifact
    parent_evidence: dict[str, Any]
    instructions: str = EXTRACTION_INSTRUCTIONS


class ExtractionProvider(Protocol):
    name: str
    method: str

    def extract(self, request: ExtractionRequest) -> list[dict[str, Any]]: ...


@dataclass
class ExtractionRunResult:
    candidates_found: int = 0
    accepted: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    provider_metrics: dict[str, Any] = field(default_factory=dict)
    provider_errors: list[str] = field(default_factory=list)


class StructuredCandidateProvider:
    """Offline adapter for structured provider output or deterministic tests.

    It is intentionally not an extractor heuristic. A future hosted/local
    model adapter implements the same Protocol and receives the same request.
    """

    def __init__(self, candidates: list[dict[str, Any]], *, name: str, method: str = "ai_assisted") -> None:
        self._candidates = candidates
        self.name = name
        self.method = method

    def extract(self, request: ExtractionRequest) -> list[dict[str, Any]]:
        return list(self._candidates)


def _normalized_statement(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split())


def _proposal_id(parent_id: str, locator: dict[str, Any], statement: str) -> str:
    identity = json.dumps(
        [parent_id, locator["start_seconds"], locator.get("end_seconds"), statement.casefold()],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"ev-proposal-atomic-{digest}"


class TranscriptEvidenceExtractionService:
    def __init__(
        self,
        *,
        repositories: Any,
        inbox_dir: Path,
        evidence_errors: Callable[[dict[str, Any]], list[str]],
        provider: ExtractionProvider,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repos = repositories
        self._inbox_dir = inbox_dir
        self._evidence_errors = evidence_errors
        self._provider = provider
        self._today = today

    def run(self, transcript: TranscriptArtifact) -> ExtractionRunResult:
        parent = self._repos.evidence.get(transcript.parent_evidence_id)
        if parent is None:
            raise TranscriptContractError(f"parent Evidence not found: {transcript.parent_evidence_id}")
        if parent.get("evidence_role") != "publication_artifact":
            raise TranscriptContractError("parent Evidence must have evidence_role=publication_artifact")
        source_id = parent.get("source_id")
        if source_id and self._repos.sources.get(source_id) is None:
            raise TranscriptContractError(f"parent Source does not resolve: {source_id}")

        raw_candidates = self._provider.extract(ExtractionRequest(transcript=transcript, parent_evidence=parent))
        if not isinstance(raw_candidates, list):
            raise TranscriptContractError("extractor output must be a list")
        provider_report = getattr(self._provider, "last_run_report", None)
        provider_metrics: dict[str, Any] = {}
        provider_errors: list[str] = []
        if provider_report is not None:
            if hasattr(provider_report, "as_dict"):
                provider_metrics = provider_report.as_dict()
            elif isinstance(provider_report, dict):
                provider_metrics = dict(provider_report)
            raw_errors = getattr(provider_report, "errors", None)
            if isinstance(raw_errors, (list, tuple)):
                provider_errors = [str(error) for error in raw_errors]
        result = ExtractionRunResult(
            candidates_found=len(raw_candidates),
            provider_metrics=provider_metrics,
            provider_errors=provider_errors,
        )
        result.invalid.extend(f"provider: {error}" for error in provider_errors)
        for index, raw in enumerate(raw_candidates):
            try:
                proposal = self._proposal(transcript, parent, raw)
            except (KeyError, TypeError, ValueError, TranscriptContractError) as exc:
                result.invalid.append(f"candidate {index}: {exc}")
                continue
            proposal_id = proposal["id"]
            draft_path = self._inbox_dir / "evidence" / f"{proposal_id}.json"
            if self._repos.evidence.get(proposal_id) is not None or draft_path.exists():
                result.duplicates.append(proposal_id)
                continue
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            result.accepted.append(proposal_id)
        return result

    def _proposal(
        self,
        transcript: TranscriptArtifact,
        parent: dict[str, Any],
        raw: Any,
    ) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise TranscriptContractError("candidate must be an object")
        statement = raw.get("normalized_statement")
        if not isinstance(statement, str) or not statement.strip():
            raise TranscriptContractError("normalized_statement is required")
        statement = _normalized_statement(statement)
        indexes = raw.get("segment_indexes")
        if not isinstance(indexes, list) or not indexes or any(
            not isinstance(value, int) or isinstance(value, bool) for value in indexes
        ):
            raise TranscriptContractError("segment_indexes must be a non-empty integer list")
        if indexes != sorted(set(indexes)) or indexes != list(range(indexes[0], indexes[-1] + 1)):
            raise TranscriptContractError("segment_indexes must be unique, ordered, and contiguous")
        if indexes[0] < 0 or indexes[-1] >= len(transcript.segments):
            raise TranscriptContractError("segment index is outside the transcript")
        selected = [transcript.segments[value] for value in indexes]
        start = selected[0].start_seconds
        end = selected[-1].end_seconds
        if end is not None and end < start:
            raise TranscriptContractError("locator end must be >= start")
        speakers = {segment.speaker_label for segment in selected if segment.speaker_label}
        locator: dict[str, Any] = {"start_seconds": start, "end_seconds": end}
        if len(speakers) == 1:
            locator["speaker_label"] = next(iter(speakers))
        excerpt = "\n".join(
            f"{segment.speaker_label}: {segment.text}" if segment.speaker_label else segment.text
            for segment in selected
        )

        entity_ids = self._id_list(raw, "entity_ids")
        geography_ids = self._id_list(raw, "geography_ids")
        berry_ids = self._id_list(raw, "berry_ids")
        entities: dict[str, dict[str, Any]] = {}
        for entity_id in [*entity_ids, *geography_ids, *berry_ids]:
            entity = self._repos.entities.get(entity_id)
            if entity is None:
                raise TranscriptContractError(f"linked id does not resolve: {entity_id}")
            entities[entity_id] = entity
        if any(entities[value].get("entity_type") == "geography" for value in entity_ids):
            raise TranscriptContractError("geography ids belong in geography_ids")
        if any(entities[value].get("entity_type") != "geography" for value in geography_ids):
            raise TranscriptContractError("geography_ids must resolve to geography entities")
        if any(entities[value].get("entity_type") != "berry" for value in berry_ids):
            raise TranscriptContractError("berry_ids must resolve to berry entities")

        proposal_id = _proposal_id(transcript.parent_evidence_id, locator, statement)
        extraction_provenance = {
            "method": self._provider.method,
            "extracted_by": self._provider.name,
            "extracted_at": self._today().isoformat(),
        }
        provider_provenance = getattr(self._provider, "provenance", None)
        if isinstance(provider_provenance, dict):
            for field_name in ("provider", "model", "prompt_version"):
                value = provider_provenance.get(field_name)
                if isinstance(value, str) and value:
                    extraction_provenance[field_name] = value
        proposal = {
            "id": proposal_id,
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "intake_type": "transcript_extraction",
            "source_type": parent.get("source_type", ""),
            "title": statement[:160],
            "source_name": parent.get("source_name", ""),
            "source_url": parent.get("source_url", ""),
            "published_date": parent.get("published_date"),
            "captured_date": self._today().isoformat(),
            "summary": statement,
            "transcript_excerpt": excerpt,
            "why_it_matters": "",
            "submitted_by": f"extractor:{self._provider.name}",
            "berry_ids": berry_ids,
            "geography_ids": geography_ids,
            "entity_ids": list(dict.fromkeys([*entity_ids, *geography_ids])),
            "fact_ids": [],
            "relationship_ids": [],
            "strategic_question_ids": [],
            "tags": [],
            "auto_captured": False,
            "priority": PRIORITY_NONE,
            "source_id": parent.get("source_id"),
            "evidence_role": "atomic_evidence",
            "parent_evidence_id": transcript.parent_evidence_id,
            "artifact_locator": locator,
            "extraction_provenance": extraction_provenance,
            "transcript_provenance": {
                "transcript_id": transcript.transcript_id,
                "transcript_sha256": transcript.content_sha256(),
                "language": transcript.language,
                "method": transcript.provenance.method,
                "created_by": transcript.provenance.created_by,
                "created_at": transcript.provenance.created_at,
                "segment_indexes": indexes,
            },
            "suggested_competitors": [
                entities[value]["name"] for value in entity_ids if entities[value].get("entity_type") == "company"
            ],
            "suggested_varieties": [
                entities[value]["name"] for value in entity_ids if entities[value].get("entity_type") == "variety"
            ],
            "suggested_retailers": [
                entities[value]["name"] for value in entity_ids if entities[value].get("entity_type") == "retailer"
            ],
            "suggested_geographies": [entities[value]["name"] for value in geography_ids],
            "attachments": [],
        }
        errors = self._evidence_errors(proposal)
        if errors:
            raise TranscriptContractError("Evidence validation failed: " + "; ".join(errors))
        return proposal

    @staticmethod
    def _id_list(raw: dict[str, Any], field_name: str) -> list[str]:
        value = raw.get(field_name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise TranscriptContractError(f"{field_name} must be a string list")
        if len(value) != len(set(value)):
            raise TranscriptContractError(f"{field_name} contains duplicates")
        return value
