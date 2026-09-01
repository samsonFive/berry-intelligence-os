"""Pulse -> Publication intake bridge.

Turns a QUALIFIED, NOT-ALREADY-REPRESENTED Industry Pulse DiscoveryHit into
a real Publication draft in the exact place the existing collection
pipeline already writes drafts (`inbox/evidence/*.json`,
`evidence_role: "publication_artifact"`, `status: "draft"`) so it enters
the ordinary Publication Review queue and becomes visible on the Front
Page's Emerging/Unreviewed section -- without ever writing trusted
Evidence, promoting trust, or bypassing review.

This module does not fork media_orchestration.py's official
`prepare_publication_draft()` path -- it cannot reuse it unchanged. That
function pulls `source_name`/`source_url` from the REGISTERED Source
record, which is correct for a Source's own RSS/keyword feed (the
publisher IS the Source) but wrong here: the discovering PROVIDER
(Google News RSS, Perplexity) is never the publisher, and a pulse hit's
real publisher domain frequently has no registered Source at all. This
module builds an equivalent draft by hand, reusing every real primitive
underneath that official path instead of duplicating it:
`article_dedup.find_duplicate_article` (novelty before acquisition),
`article_acquisition.fetch_article` (the same body-fetch/extract used by
`article_refresh.process_discovered_article`), `publication_enrichment.
enrich_publication_draft` (deterministic berry/geography/entity tagging),
`source_completeness.with_source_completeness`, and the shared
`evidence.schema.json` validator.

UNKNOWN SOURCES: a pulse hit's real publisher domain is looked up against
already-registered Sources by hostname; if none matches, the draft is
attributed to `PULSE_CATCHNET_SOURCE_ID` -- one shared, clearly-labeled,
non-collection-eligible placeholder Source (see
`data/configuration/sources.json`) that exists ONLY to satisfy the
schema's Source-linkage requirement. The draft's own `source_name`/
`source_url`/`pulse_provenance.publisher_domain` always carry the real
discovered publisher regardless of which Source id it is attributed to.
No new Source is ever silently created, and no second Source repository
is built.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.services.article_acquisition import ArticleAcquisitionError, ArticleBody, fetch_article
from app.services.article_dedup import find_duplicate_article, normalize_canonical_url
from app.services.industry_pulse.models import DiscoveryHit
from app.services.publication_enrichment import apply_deterministic_tags, enrich_publication_draft
from app.services.recall_audit.classify import WRAPPER_HOSTS, hostname
from app.services.source_completeness import with_source_completeness

PULSE_CATCHNET_SOURCE_ID = "source-industry-pulse-catchnet"

PRIORITY_NONE: dict[str, dict[str, str]] = {
    "reading": {"level": "none", "rationale": ""},
    "testing": {"level": "none", "rationale": ""},
    "commercial_position": {"level": "none", "rationale": ""},
    "monitoring": {"level": "none", "rationale": ""},
}


@dataclass
class IntakeItemResult:
    hit_id: str
    url: str
    outcome: str  # "created" | "duplicate" | "acquisition_failed_thin_draft" | "error"
    draft_id: str | None = None
    detail: str = ""


@dataclass
class IntakeSummary:
    considered: int = 0
    already_represented: int = 0
    acquisition_attempted: int = 0
    acquisition_succeeded: int = 0
    acquisition_failed: int = 0
    drafts_created: int = 0
    errors: int = 0
    results: list[IntakeItemResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "considered": self.considered,
            "already_represented": self.already_represented,
            "acquisition_attempted": self.acquisition_attempted,
            "acquisition_succeeded": self.acquisition_succeeded,
            "acquisition_failed": self.acquisition_failed,
            "drafts_created": self.drafts_created,
            "errors": self.errors,
            "results": [
                {"hit_id": r.hit_id, "url": r.url, "outcome": r.outcome, "draft_id": r.draft_id, "detail": r.detail}
                for r in self.results
            ],
        }


def _real_publisher_url(hit: DiscoveryHit) -> str:
    """The actual article URL, never a Google News wrapper."""
    candidate = hit.origin_publisher_url or hit.url
    return candidate or ""


def pulse_draft_id(hit: DiscoveryHit) -> str:
    """Deterministic id keyed on the real (normalized) publisher URL, not
    the query that found it -- re-running intake on the same story is
    idempotent, and a story found by both providers still gets one id."""
    url = normalize_canonical_url(_real_publisher_url(hit)) or hit.url
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return f"ev-pulse-{digest}"


def _source_by_hostname(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        host = hostname(source.get("url") or source.get("value") or "")
        if host and host not in WRAPPER_HOSTS:
            index.setdefault(host, source)
    return index


def resolve_attribution(
    hit: DiscoveryHit, *, sources: list[dict[str, Any]], source_index: dict[str, dict[str, Any]] | None = None
) -> tuple[str, str, str]:
    """Returns (source_id, source_name, source_url). Prefers a real,
    already-registered Source matched by publisher hostname; the discovery
    provider is never treated as the publisher. Falls back to the shared
    catch-net placeholder id while still carrying the real publisher name
    and URL on the draft itself."""

    url = _real_publisher_url(hit)
    host = hostname(url)
    index = source_index if source_index is not None else _source_by_hostname(sources)
    matched = index.get(host) if host else None
    if matched:
        name = matched.get("label") or matched.get("name") or matched.get("value") or host
        return str(matched["id"]), str(name), url
    return PULSE_CATCHNET_SOURCE_ID, (hit.origin_publisher_name or host or hit.source_domain or "Unknown publisher"), url


def _existing_record_view(record: dict[str, Any]) -> dict[str, Any]:
    """find_duplicate_article() reads canonical_url/resolved_canonical_url/
    title/source_id/published_date off both trusted Evidence and pending
    drafts -- both already carry source_url/title/source_id/published_date
    under those exact names, so no adapter needed beyond the url alias."""
    view = dict(record)
    view["canonical_url"] = record.get("source_url") or record.get("canonical_url") or ""
    return view


def build_pulse_draft(
    hit: DiscoveryHit,
    *,
    sources: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    source_index: dict[str, dict[str, Any]] | None = None,
    body: ArticleBody | None = None,
    failure_category: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    source_id, source_name, source_url = resolve_attribution(hit, sources=sources, source_index=source_index)
    published_date = (hit.published_date or "")[:10] or None
    captured_date = now.date().isoformat()
    summary = (hit.snippet or "").strip()
    if not summary:
        summary = f"Discovered via Industry Pulse from {source_name}."
    draft: dict[str, Any] = {
        "id": pulse_draft_id(hit),
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "industry_pulse_publication",
        "source_type": "news_search",
        "title": (hit.title or "").strip() or source_url,
        "source_name": source_name,
        "source_url": source_url,
        "published_date": published_date,
        "captured_date": captured_date,
        "summary": summary[:1200],
        "why_it_matters": "",
        "submitted_by": "industry_pulse/intake",
        "berry_ids": [],
        "geography_ids": [],
        "entity_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "strategic_question_ids": [],
        "tags": ["industry-pulse"],
        "attachments": [],
        "auto_captured": False,
        "priority": {k: dict(v) for k, v in PRIORITY_NONE.items()},
        "source_id": source_id,
        "evidence_role": "publication_artifact",
        # Distinct from media_orchestration's discovery_provenance (which
        # is shaped around a staged discovered_media_item this pipeline
        # never creates) -- this is the pulse-specific provenance the
        # mission requires preserved: which provider(s)/query found this,
        # not a claim about the confirmed berry/geography/topic of the
        # story itself (that comes from enrich_publication_draft below,
        # against the real acquired text).
        "pulse_provenance": {
            "providers": [hit.provider],
            "query_ids": [hit.query_id] if hit.query_id else [],
            "geography_query": hit.geography,
            "berry_query": hit.berry,
            "topic_query": hit.topic,
            "publisher_domain": hostname(source_url),
            "wrapper_url": hit.wrapper_url,
            "discovered_at": now.isoformat(),
        },
    }
    if body is not None:
        draft["article"] = body.as_dict()
        if not draft["published_date"] and body.published_date:
            draft["published_date"] = body.published_date[:10]
    berries = [record for record in entities if record.get("entity_type") == "berry"]
    geographies = [record for record in entities if record.get("entity_type") == "geography"]
    companies = [record for record in entities if record.get("entity_type") == "company"]
    item_view = {"description": hit.snippet, "title": hit.title}
    draft = enrich_publication_draft(
        draft, item_view, berries=berries, geographies=geographies, entities=companies, complete_json=None
    )
    if body is not None and body.paragraphs:
        extra_text = " ".join(p.text for p in body.paragraphs)
        draft = apply_deterministic_tags(draft, geographies=geographies, entities=companies, extra_text=extra_text[:4000])
    draft = with_source_completeness(draft, failure_category=failure_category)
    return draft


def intake_qualified_hits(
    hits: list[DiscoveryHit],
    *,
    sources: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    inbox_dir: Path,
    fetch: Any = fetch_article,
    max_acquisitions: int = 20,
    now: datetime | None = None,
    dry_run: bool = False,
) -> IntakeSummary:
    """Acquire and draft only NOVEL, QUALIFYING, deduplicated hits, bounded
    to `max_acquisitions` real body fetches per run. A single item's
    acquisition failure never aborts the run and never drops the item --
    it still becomes a thin draft with an honest failure_category, exactly
    matching how the existing collection pipeline handles a body-fetch
    failure. Never writes trusted Evidence; only ever writes
    `inbox/evidence/*.json` drafts."""

    now = now or datetime.now(UTC)
    summary = IntakeSummary()
    source_index = _source_by_hostname(sources)
    existing = [_existing_record_view(r) for r in published_evidence] + [_existing_record_view(r) for r in drafts]
    existing_ids = {str(r.get("id") or "") for r in drafts}
    evidence_dir = inbox_dir / "evidence"

    candidates = [h for h in hits if h.qualifying and not h.duplicate_of]
    acquisitions_used = 0
    for hit in candidates:
        summary.considered += 1
        draft_id = pulse_draft_id(hit)
        if draft_id in existing_ids:
            summary.already_represented += 1
            summary.results.append(IntakeItemResult(hit_id=hit.query_id, url=hit.url, outcome="duplicate", draft_id=draft_id, detail="already drafted"))
            continue
        item_view = {
            "canonical_url": _real_publisher_url(hit),
            "title": hit.title,
            "source_id": None,
            "published_date": hit.published_date,
        }
        duplicate_of = find_duplicate_article(item_view, existing_records=existing)
        if duplicate_of:
            summary.already_represented += 1
            summary.results.append(IntakeItemResult(hit_id=hit.query_id, url=hit.url, outcome="duplicate", draft_id=duplicate_of, detail="matched existing record"))
            continue

        body: ArticleBody | None = None
        failure_category: str | None = None
        if acquisitions_used < max_acquisitions:
            acquisitions_used += 1
            summary.acquisition_attempted += 1
            try:
                body = fetch(_real_publisher_url(hit))
                summary.acquisition_succeeded += 1
            except ArticleAcquisitionError as exc:
                summary.acquisition_failed += 1
                failure_category = exc.category
            except Exception as exc:  # noqa: BLE001 -- one item must not abort the intake run
                summary.acquisition_failed += 1
                summary.errors += 1
                summary.results.append(
                    IntakeItemResult(hit_id=hit.query_id, url=hit.url, outcome="error", detail=f"{type(exc).__name__}: {exc}")
                )
                continue

        try:
            draft = build_pulse_draft(
                hit, sources=sources, entities=entities, source_index=source_index, body=body,
                failure_category=failure_category, now=now,
            )
        except Exception as exc:  # noqa: BLE001 -- isolate per-item construction failures too
            summary.errors += 1
            summary.results.append(
                IntakeItemResult(hit_id=hit.query_id, url=hit.url, outcome="error", detail=f"{type(exc).__name__}: {exc}")
            )
            continue

        outcome = "created" if body is not None else "acquisition_failed_thin_draft"
        if not dry_run:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            import json

            path = evidence_dir / f"{draft['id']}.json"
            path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary.drafts_created += 1
        existing_ids.add(draft["id"])
        summary.results.append(IntakeItemResult(hit_id=hit.query_id, url=hit.url, outcome=outcome, draft_id=draft["id"]))

    return summary
