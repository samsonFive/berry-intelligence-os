"""Operator orchestration from discovered media to reviewable Evidence.

This module coordinates existing discovery, review, transcript, and extraction
boundaries.  It deliberately does not discover media, acquire/transcribe audio,
publish Evidence, or approve extracted proposals.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Protocol

from app.services import media_transcription
from app.services.article_dedup import find_duplicate_article
from app.services.publication_enrichment import enrich_publication_draft
from app.services.relevance_screening import screen_discovered_item
from app.services.transcript_evidence import (
    PRIORITY_NONE,
    TranscriptArtifact,
    TranscriptContractError,
    TranscriptEvidenceExtractionService,
)


class MediaOrchestrationError(ValueError):
    """A staged record cannot safely progress without operator correction."""


class TranscriptAcquisitionError(MediaOrchestrationError):
    """The configured transcription service could not produce a transcript."""


class StagedTranscriptAdapter(Protocol):
    """Boundary implemented by a normalized transcript producer.

    The returned mapping uses the existing ``TranscriptArtifact`` fields, but
    ``parent_evidence_id`` may be absent until publication review is complete.
    """

    def load(self, discovered_item: dict[str, Any]) -> dict[str, Any] | None: ...


class JsonStagedTranscriptAdapter:
    """Conservative filesystem adapter for normalized transcript handoff.

    It does not read acquisition's raw ``_transcripts`` artifacts.  By default
    it reads ``_normalized_transcripts/<discovered-item-id>.json``; a caller can
    provide an explicit file produced by another implementation.
    """

    def __init__(self, inbox_dir: Path, transcript_path: Path | None = None) -> None:
        self._inbox_dir = inbox_dir
        self._transcript_path = transcript_path

    def load(self, discovered_item: dict[str, Any]) -> dict[str, Any] | None:
        path = self._transcript_path or (
            self._inbox_dir / "discovered_media" / "_normalized_transcripts" / f"{discovered_item['id']}.json"
        )
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MediaOrchestrationError(f"could not read normalized transcript {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise MediaOrchestrationError("normalized transcript must be a JSON object")
        linked_item = payload.get("discovered_item_id") or payload.get("item_id")
        if linked_item is not None and linked_item != discovered_item["id"]:
            raise MediaOrchestrationError(
                f"transcript belongs to discovered item {linked_item!r}, not {discovered_item['id']!r}"
            )
        return payload


class MediaTranscriptionAdapter:
    """Thin adapter around Claude's public media-transcription service.

    A compatible normalized artifact is loaded without touching audio or the
    transcription provider.  When it is absent or its requested cache inputs
    changed, acquisition/cache/transcription decisions remain wholly owned by
    ``media_transcription.transcribe_discovered_item``.
    """

    def __init__(
        self,
        inbox_dir: Path,
        *,
        model: str = media_transcription.DEFAULT_WHISPER_MODEL,
        device: str | None = None,
        language: str | None = None,
        created_by: str | None = None,
        provider_factory: Callable[[], media_transcription.TranscriptionProvider] | None = None,
        force: bool = False,
        transcribe_missing: bool = True,
        max_tier: int = 3,
    ) -> None:
        self._inbox_dir = inbox_dir
        self._model = model
        self._device = device
        self._language = language
        self._created_by = created_by
        self._provider_factory = provider_factory
        self._force = force
        self._transcribe_missing = transcribe_missing
        self._max_tier = max_tier

    def load(self, discovered_item: dict[str, Any]) -> dict[str, Any] | None:
        item_id = discovered_item["id"]
        cached = media_transcription.load_transcript_artifact(self._inbox_dir, item_id)
        if cached is not None and self._cache_matches_request(cached, discovered_item):
            return cached
        if not self._transcribe_missing:
            return None
        outcome = media_transcription.transcribe_discovered_item(
            self._inbox_dir,
            discovered_item,
            model=self._model,
            device=self._device,
            language=self._language,
            parent_evidence_id=None,
            created_by=self._created_by,
            provider_factory=self._provider_factory,
            force=self._force,
            max_tier=self._max_tier,
        )
        if outcome.status != "ok":
            if outcome.tier == "deferred_expensive_transcription":
                return None
            tier = f" via {outcome.tier}" if outcome.tier else ""
            raise TranscriptAcquisitionError(f"transcript acquisition failed{tier}: {outcome.error or 'unknown error'}")
        payload = media_transcription.load_transcript_artifact(self._inbox_dir, item_id)
        if payload is None:
            raise TranscriptAcquisitionError(
                "transcription reported success but no normalized transcript artifact was available"
            )
        return payload

    def _cache_matches_request(self, payload: dict[str, Any], item: dict[str, Any]) -> bool:
        return media_transcription.transcript_cache_matches_request(
            self._inbox_dir,
            payload,
            item,
            model=self._model,
            language=self._language,
            force=self._force,
        )


@dataclass(frozen=True)
class ParentResolution:
    status: str
    evidence_id: str | None = None
    draft_id: str | None = None
    candidate_ids: tuple[str, ...] = ()
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_id": self.evidence_id,
            "draft_id": self.draft_id,
            "candidate_ids": list(self.candidate_ids),
            "message": self.message,
        }


@dataclass
class OrchestrationResult:
    item_id: str
    state: str
    parent_resolution: ParentResolution
    transcript_status: str
    next_action: str
    dry_run: bool = False
    publication_draft_id: str | None = None
    transcript_id: str | None = None
    transcript_sha256: str | None = None
    extraction: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    # "direct" | "adjacent" | None -- only ever set for a web_article result
    # by callers that ran it through relevance_screen.py (see
    # scripts/run_collection.py's orchestrate()); optional/additive so every
    # existing caller/test that never sets it is unaffected. Lets
    # CollectionRunner report direct-vs-adjacent review-ready counts without
    # this module importing anything article-specific itself.
    relevance_tier: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "state": self.state,
            "dry_run": self.dry_run,
            "parent_resolution": self.parent_resolution.as_dict(),
            "publication_draft_id": self.publication_draft_id,
            "transcript_status": self.transcript_status,
            "transcript_id": self.transcript_id,
            "transcript_sha256": self.transcript_sha256,
            "extraction": self.extraction,
            "relevance_tier": self.relevance_tier,
            "next_action": self.next_action,
            "errors": self.errors,
        }


def publication_draft_id(discovered_item: dict[str, Any]) -> str:
    """Return the stable Evidence identity reserved for one staged item."""

    identity = discovered_item.get("id")
    if not isinstance(identity, str) or not identity.strip():
        raise MediaOrchestrationError("discovered item id is required")
    digest = hashlib.sha256(identity.strip().encode("utf-8")).hexdigest()[:20]
    return f"ev-media-{digest}"


class MediaOrchestrationService:
    def __init__(
        self,
        *,
        repositories: Any,
        inbox_dir: Path,
        evidence_errors: Any,
        transcript_adapter: StagedTranscriptAdapter,
        extraction_service: TranscriptEvidenceExtractionService | None = None,
        today: Any = date.today,
        complete_json: Callable[..., Any] | None = None,
    ) -> None:
        self._repos = repositories
        self._inbox_dir = inbox_dir
        self._evidence_errors = evidence_errors
        self._transcript_adapter = transcript_adapter
        self._extraction_service = extraction_service
        self._today = today
        self._complete_json = complete_json

    def load_item(self, item_id: str) -> dict[str, Any]:
        path = self._inbox_dir / "discovered_media" / f"{item_id}.json"
        if not path.exists():
            raise MediaOrchestrationError(f"discovered item not found: {item_id}")
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MediaOrchestrationError(f"could not read discovered item {item_id}: {exc}") from exc
        self._validate_item(item, expected_id=item_id)
        return item

    def resolve_publication_artifact(self, discovered_item: dict[str, Any]) -> ParentResolution:
        """Resolve permanent/pending publication representation without guessing."""

        self._validate_item(discovered_item)
        deterministic_id = publication_draft_id(discovered_item)
        trusted_ids: set[str] = set()

        deterministic = self._repos.evidence.get(deterministic_id)
        if self._is_trusted_publication(deterministic):
            trusted_ids.add(deterministic_id)

        for match in discovered_item.get("possible_evidence_matches", []):
            if not isinstance(match, dict) or not isinstance(match.get("evidence_id"), str):
                continue
            evidence_id = match["evidence_id"]
            if self._is_trusted_publication(self._repos.evidence.get(evidence_id)):
                trusted_ids.add(evidence_id)

        source_id = discovered_item["source_id"]
        canonical_url = discovered_item.get("canonical_url")
        if canonical_url:
            for evidence in self._repos.evidence.list():
                if (
                    self._is_trusted_publication(evidence)
                    and evidence.get("source_id") == source_id
                    and evidence.get("source_url") == canonical_url
                ):
                    trusted_ids.add(evidence["id"])

        drafts = self._publication_drafts_for(discovered_item, deterministic_id)

        # Cross-pipeline duplicate check: the same real-world article
        # already trusted or drafted under a *different* discovered-item
        # id -- a different capture pass, or the publisher's title text
        # drifting between captures (e.g. one capture kept a trailing
        # " - Publisher" suffix, another stripped it). The checks above
        # only ever catch the *same* discovered_item_id or an exact
        # source_url string match; this is deliberately narrower than a
        # general similarity search -- normalized canonical URL, or
        # normalized title + same source + same published date, never
        # mere title resemblance. See app/services/article_dedup.py.
        extra_trusted_ids, extra_drafts = self._cross_pipeline_duplicates(discovered_item)
        trusted_ids |= extra_trusted_ids
        existing_draft_ids = {draft["id"] for draft in drafts}
        drafts = drafts + [draft for draft in extra_drafts if draft["id"] not in existing_draft_ids]
        representation_ids = set(trusted_ids) | {draft["id"] for draft in drafts}
        if len(representation_ids) > 1:
            ids = tuple(sorted(representation_ids))
            return ParentResolution(
                status="ambiguous",
                candidate_ids=ids,
                message="Multiple publication representations require operator review.",
            )
        if trusted_ids:
            evidence_id = next(iter(trusted_ids))
            return ParentResolution(
                status="trusted",
                evidence_id=evidence_id,
                candidate_ids=(evidence_id,),
                message="Existing trusted publication artifact resolved.",
            )
        if drafts:
            draft = drafts[0]
            rejected = draft.get("status") == "rejected" or draft.get("review_state") == "rejected"
            return ParentResolution(
                status="rejected_draft" if rejected else "pending_draft",
                draft_id=draft["id"],
                candidate_ids=(draft["id"],),
                message=(
                    "Publication draft was rejected; operator disposition is required."
                    if rejected
                    else "Publication draft is awaiting human review."
                ),
            )
        return ParentResolution(status="none", message="No publication artifact or draft exists.")

    def prepare_publication_draft(
        self,
        discovered_item: dict[str, Any],
        *,
        dry_run: bool = False,
        enrich: bool = False,
    ) -> dict[str, Any]:
        """Build, validate, and optionally persist one untrusted draft."""

        resolution = self.resolve_publication_artifact(discovered_item)
        if resolution.status != "none":
            raise MediaOrchestrationError(f"publication representation already exists: {resolution.status}")
        source = self._repos.sources.get(discovered_item["source_id"])
        if source is None:
            raise MediaOrchestrationError(f"Source ID does not resolve: {discovered_item['source_id']}")
        draft = self._draft_from_item(discovered_item, source, enrich=enrich)
        errors = self._evidence_errors(draft)
        if errors:
            raise MediaOrchestrationError("publication draft failed Evidence validation: " + "; ".join(errors))
        if not dry_run:
            path = self._inbox_dir / "evidence" / f"{draft['id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return draft

    def bind_transcript(
        self, transcript_payload: dict[str, Any], parent_evidence_id: str
    ) -> TranscriptArtifact:
        """Bind parent metadata without mutating transcript content or input."""

        parent = self._repos.evidence.get(parent_evidence_id)
        if not self._is_trusted_publication(parent):
            raise MediaOrchestrationError("transcript parent must be a trusted publication_artifact")
        payload = deepcopy(transcript_payload)
        embedded_parent = payload.get("parent_evidence_id")
        if embedded_parent and embedded_parent != parent_evidence_id:
            raise MediaOrchestrationError(
                f"transcript parent mismatch: {embedded_parent!r} != {parent_evidence_id!r}"
            )
        payload["parent_evidence_id"] = parent_evidence_id
        payload.pop("discovered_item_id", None)
        payload.pop("item_id", None)
        try:
            return TranscriptArtifact.from_dict(payload)
        except TranscriptContractError as exc:
            raise MediaOrchestrationError(f"malformed transcript: {exc}") from exc

    def process(
        self,
        item_id: str,
        *,
        dry_run: bool = False,
        relevance_gate: bool = False,
        enrich: bool = False,
    ) -> OrchestrationResult:
        item = self.load_item(item_id)
        screening = screen_discovered_item(item)
        item["relevance_screening"] = screening.to_dict()
        if not dry_run:
            self._write_item(item)

        if relevance_gate and screening.decision == "skip":
            return OrchestrationResult(
                item_id=item_id,
                state="skipped_irrelevant",
                parent_resolution=ParentResolution(
                    status="skipped",
                    message="Item is below the relevance threshold; transcription was not attempted.",
                ),
                transcript_status="deferred",
                next_action="No action; item screened as clearly irrelevant before transcription.",
                dry_run=dry_run,
            )

        resolution = self.resolve_publication_artifact(item)
        load_transcript = not (relevance_gate and screening.decision == "borderline")
        if load_transcript:
            transcript_payload, transcript_status, transcript_error = self._load_transcript(item)
        else:
            transcript_payload, transcript_status, transcript_error = None, "deferred", None

        if resolution.status == "ambiguous":
            return OrchestrationResult(
                item_id=item_id,
                state="discovered",
                parent_resolution=resolution,
                transcript_status=transcript_status,
                next_action="Resolve ambiguous publication matches manually.",
                dry_run=dry_run,
                errors=[resolution.message],
            )

        if resolution.status == "none":
            source = self._repos.sources.get(item["source_id"])
            if source is None:
                return OrchestrationResult(
                    item_id=item_id,
                    state="discovered",
                    parent_resolution=resolution,
                    transcript_status=transcript_status,
                    next_action="Register or correct the Source ID.",
                    dry_run=dry_run,
                    errors=[f"Source ID does not resolve: {item['source_id']}"],
                )
            draft = self.prepare_publication_draft(item, dry_run=dry_run, enrich=enrich and not dry_run)
            planned = ParentResolution(
                status="would_create_draft" if dry_run else "pending_draft",
                draft_id=draft["id"],
                candidate_ids=(draft["id"],),
                message=("Publication draft would be created." if dry_run else "Publication draft created for review."),
            )
            return OrchestrationResult(
                item_id=item_id,
                state="discovered" if dry_run else "awaiting_publication_review",
                parent_resolution=planned,
                publication_draft_id=draft["id"],
                transcript_status=transcript_status,
                next_action="Create and review the publication draft." if dry_run else "Review the publication draft.",
                dry_run=dry_run,
                errors=[transcript_error] if transcript_error else [],
            )

        if resolution.status in {"pending_draft", "rejected_draft"}:
            return OrchestrationResult(
                item_id=item_id,
                state=("awaiting_publication_review" if resolution.status == "pending_draft" else "publication_rejected"),
                parent_resolution=resolution,
                publication_draft_id=resolution.draft_id,
                transcript_status=transcript_status,
                next_action=(
                    (
                        "Review the publication draft; then retry transcript acquisition."
                        if transcript_status == "acquisition_failed"
                        else "Review the publication draft."
                    )
                    if resolution.status == "pending_draft"
                    else "Review the rejection before creating another publication draft."
                ),
                dry_run=dry_run,
                errors=[transcript_error] if transcript_error else [],
            )

        if transcript_error:
            acquisition_failed = transcript_status == "acquisition_failed"
            return OrchestrationResult(
                item_id=item_id,
                state="publication_approved",
                parent_resolution=resolution,
                transcript_status=transcript_status,
                next_action=(
                    "Correct the acquisition/transcription failure and retry."
                    if acquisition_failed
                    else "Correct or regenerate the normalized transcript."
                ),
                dry_run=dry_run,
                errors=[transcript_error],
            )
        if transcript_payload is None:
            if transcript_status == "not_applicable":
                return OrchestrationResult(
                    item_id=item_id,
                    state="publication_approved",
                    parent_resolution=resolution,
                    transcript_status="not_applicable",
                    next_action="No transcript applies to a written article; its source text is available for a future qualified extraction step.",
                    dry_run=dry_run,
                )
            return OrchestrationResult(
                item_id=item_id,
                state="publication_approved",
                parent_resolution=resolution,
                transcript_status="missing",
                next_action="Acquire or transcribe and normalize the media.",
                dry_run=dry_run,
            )

        try:
            transcript = self.bind_transcript(transcript_payload, resolution.evidence_id or "")
        except MediaOrchestrationError as exc:
            return OrchestrationResult(
                item_id=item_id,
                state="publication_approved",
                parent_resolution=resolution,
                transcript_status="malformed",
                next_action="Correct the transcript association or normalized transcript.",
                dry_run=dry_run,
                errors=[str(exc)],
            )

        content_hash = transcript.content_sha256()
        if dry_run or self._extraction_service is None:
            return OrchestrationResult(
                item_id=item_id,
                state="ready_for_extraction",
                parent_resolution=resolution,
                transcript_status="ready",
                transcript_id=transcript.transcript_id,
                transcript_sha256=content_hash,
                next_action=(
                    "Run the configured atomic Evidence extractor."
                    if self._extraction_service is None
                    else "Atomic Evidence proposals would be created."
                ),
                dry_run=dry_run,
            )

        try:
            extracted = self._extraction_service.run(transcript)
        except Exception as exc:  # provider/runtime failures become operator-visible state
            return OrchestrationResult(
                item_id=item_id,
                state="ready_for_extraction",
                parent_resolution=resolution,
                transcript_status="ready",
                transcript_id=transcript.transcript_id,
                transcript_sha256=content_hash,
                next_action="Correct the extractor failure and retry.",
                errors=[f"extractor failed: {exc}"],
            )
        summary = {
            "candidates_found": extracted.candidates_found,
            "accepted": len(extracted.accepted),
            "duplicates": len(extracted.duplicates),
            "invalid": len(extracted.invalid),
            "proposal_ids": list(extracted.accepted),
            "provider_metrics": extracted.provider_metrics,
            "provider_errors": extracted.provider_errors,
        }
        if extracted.accepted:
            next_action = "Review the atomic Evidence proposals in inbox/evidence/."
        elif extracted.duplicates:
            next_action = "No new proposals were created; existing proposals remain in the review workflow."
        else:
            next_action = "No atomic Evidence proposals were produced; inspect or configure extractor output."
        return OrchestrationResult(
            item_id=item_id,
            state="extraction_complete",
            parent_resolution=resolution,
            transcript_status="ready",
            transcript_id=transcript.transcript_id,
            transcript_sha256=content_hash,
            extraction=summary,
            next_action=next_action,
        )

    def _load_transcript(
        self, discovered_item: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        if discovered_item.get("media_format") == "web_article":
            # A written article has no audio/video to transcribe -- never
            # attempt Tier 1-3 acquisition for one. Without this guard the
            # transcript adapter would try and fail to acquire a media
            # enclosure that was never going to exist, and collection_runner
            # would classify that failure as retryable, endlessly retrying
            # a fetch that could never succeed for a text item.
            return None, "not_applicable", None
        try:
            payload = self._transcript_adapter.load(discovered_item)
        except TranscriptAcquisitionError as exc:
            return None, "acquisition_failed", str(exc)
        except MediaOrchestrationError as exc:
            return None, "malformed", str(exc)
        if payload is None:
            return None, "missing", None
        probe = deepcopy(payload)
        if not probe.get("parent_evidence_id"):
            probe["parent_evidence_id"] = "ev-unresolved-publication-artifact"
        probe.pop("discovered_item_id", None)
        probe.pop("item_id", None)
        try:
            TranscriptArtifact.from_dict(probe)
        except TranscriptContractError as exc:
            return payload, "malformed", f"malformed transcript: {exc}"
        return payload, "ready", None

    def _validate_item(self, item: Any, expected_id: str | None = None) -> None:
        if not isinstance(item, dict):
            raise MediaOrchestrationError("discovered item must be a JSON object")
        required = {
            "id": str,
            "record_type": str,
            "source_id": str,
            "title": str,
            "dedupe_key": str,
            "media_format": str,
        }
        missing = [name for name, kind in required.items() if not isinstance(item.get(name), kind) or not item.get(name)]
        if missing:
            raise MediaOrchestrationError("malformed discovered item; required fields: " + ", ".join(missing))
        if item["record_type"] != "discovered_media_item":
            raise MediaOrchestrationError("record_type must be discovered_media_item")
        if expected_id is not None and item["id"] != expected_id:
            raise MediaOrchestrationError("discovered item file name and id do not match")

    def _publication_drafts_for(self, item: dict[str, Any], deterministic_id: str) -> list[dict[str, Any]]:
        folder = self._inbox_dir / "evidence"
        if not folder.exists():
            return []
        matches: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                draft = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MediaOrchestrationError(f"could not inspect Evidence draft {path}: {exc}") from exc
            if draft.get("evidence_role") != "publication_artifact":
                continue
            if draft.get("id") == deterministic_id or draft.get("discovered_item_id") == item["id"]:
                matches.append(draft)
        return matches

    def _cross_pipeline_duplicates(self, item: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
        """Trusted Evidence and pending drafts belonging to *other*
        discovered-item ids, searched for a duplicate of `item` per
        app/services/article_dedup.py's normalized-URL / conservative
        title+source+date rules. Returns (trusted_ids, draft_records)
        exactly like the exact-match checks in resolve_publication_
        artifact, so a cross-pipeline match folds into the same
        trusted/pending_draft/ambiguous resolution instead of a third
        outcome the caller has to special-case."""
        candidates: list[dict[str, Any]] = list(self._repos.evidence.list())
        folder = self._inbox_dir / "evidence"
        if folder.exists():
            for path in sorted(folder.glob("*.json")):
                try:
                    draft = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if draft.get("evidence_role") == "publication_artifact":
                    candidates.append(draft)
        publications = [c for c in candidates if c.get("evidence_role") == "publication_artifact"]
        match_id = find_duplicate_article(item, existing_records=publications)
        if match_id is None:
            return set(), []
        for record in publications:
            if record.get("id") != match_id:
                continue
            if self._is_trusted_publication(record):
                return {match_id}, []
            return set(), [record]
        return set(), []

    @staticmethod
    def _is_trusted_publication(record: dict[str, Any] | None) -> bool:
        return bool(
            record
            and record.get("evidence_role") == "publication_artifact"
            and record.get("status") == "published"
            and record.get("review_state", "published") == "published"
        )

    def _write_item(self, item: dict[str, Any]) -> None:
        path = self._inbox_dir / "discovered_media" / f"{item['id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _draft_from_item(self, item: dict[str, Any], source: dict[str, Any], *, enrich: bool = False) -> dict[str, Any]:
        captured_date = self._date_part(item.get("first_seen_at")) or self._today().isoformat()
        published_date = self._date_part(item.get("published_date"))
        source_name = source.get("label") or source.get("name") or source.get("value") or item["source_id"]
        description = item.get("description")
        summary = description.strip() if isinstance(description, str) and description.strip() else (
            f"Discovered {item.get('media_format') or 'media'} item from {source_name}."
        )
        draft = {
            "id": publication_draft_id(item),
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "intake_type": "discovered_media_publication",
            "source_type": "discovered_media",
            "title": item["title"].strip(),
            "source_name": source_name,
            "source_url": item.get("canonical_url") or "",
            "published_date": published_date,
            "captured_date": captured_date,
            "summary": summary,
            "why_it_matters": "",
            "submitted_by": "media-orchestration",
            "berry_ids": [],
            "geography_ids": [],
            "entity_ids": [],
            "fact_ids": [],
            "relationship_ids": [],
            "strategic_question_ids": [],
            "tags": [],
            "attachments": [],
            "auto_captured": False,
            "priority": deepcopy(PRIORITY_NONE),
            "source_id": item["source_id"],
            "media_format": item["media_format"],
            "evidence_role": "publication_artifact",
            "discovered_item_id": item["id"],
            "discovery_provenance": {
                "dedupe_key": item["dedupe_key"],
                "external_id": item.get("external_id"),
                "first_seen_at": item.get("first_seen_at"),
                "last_seen_at": item.get("last_seen_at"),
            },
        }
        berries = [record for record in self._repos.entities.list() if record.get("entity_type") == "berry"]
        geographies = [record for record in self._repos.entities.list() if record.get("entity_type") == "geography"]
        entities = [record for record in self._repos.entities.list() if record.get("entity_type") == "company"]
        return enrich_publication_draft(
            draft,
            item,
            berries=berries,
            geographies=geographies,
            entities=entities,
            complete_json=self._complete_json if enrich else None,
        )
        captured_date = self._date_part(item.get("first_seen_at")) or self._today().isoformat()
        published_date = self._date_part(item.get("published_date"))
        source_name = source.get("label") or source.get("name") or source.get("value") or item["source_id"]
        description = item.get("description")
        summary = description.strip() if isinstance(description, str) and description.strip() else (
            f"Discovered {item.get('media_format') or 'media'} item from {source_name}."
        )
        return {
            "id": publication_draft_id(item),
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "intake_type": "discovered_media_publication",
            "source_type": "discovered_media",
            "title": item["title"].strip(),
            "source_name": source_name,
            "source_url": item.get("canonical_url") or "",
            "published_date": published_date,
            "captured_date": captured_date,
            "summary": summary,
            "why_it_matters": "",
            "submitted_by": "media-orchestration",
            "berry_ids": [],
            "geography_ids": [],
            "entity_ids": [],
            "fact_ids": [],
            "relationship_ids": [],
            "strategic_question_ids": [],
            "tags": [],
            "attachments": [],
            "auto_captured": False,
            "priority": deepcopy(PRIORITY_NONE),
            "source_id": item["source_id"],
            "media_format": item["media_format"],
            "evidence_role": "publication_artifact",
            "discovered_item_id": item["id"],
            "discovery_provenance": {
                "dedupe_key": item["dedupe_key"],
                "external_id": item.get("external_id"),
                "first_seen_at": item.get("first_seen_at"),
                "last_seen_at": item.get("last_seen_at"),
            },
        }

    @staticmethod
    def _date_part(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = value.strip()[:10]
        try:
            date.fromisoformat(candidate)
        except ValueError as exc:
            raise MediaOrchestrationError(f"invalid date value: {value!r}") from exc
        return candidate
