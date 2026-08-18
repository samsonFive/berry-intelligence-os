"""Bring written-article discovery into the normal recurring refresh path.

app/services/relevance_screen.py's two-stage, body-aware relevance screen and
app/services/article_acquisition.py's readable-text extraction were built
alongside a standalone CLI (scripts/ingest_articles.py) during the Article
Ingestion vertical slice. This module extracts that same per-item pipeline
(screen -> acquire -> screen again if borderline -> create draft -> enrich)
into one reusable function, so scripts/run_collection.py's recurring
orchestrate() path can also produce real, body-screened, enriched article
drafts for media_format == "web_article" items -- not just a thin
metadata-only draft from the generic media-orchestration path -- without
duplicating this logic in two places.

Always returns a real OrchestrationResult, so both existing consumers of
MediaOrchestrationService.process()'s return shape (scripts/ingest_articles.py's
own reporting, and CollectionRunner's generic _from_orchestration()) can use
this as a drop-in replacement for a plain process() call on article items.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.services.article_acquisition import ArticleAcquisitionError, fetch_article
from app.services.media_orchestration import (
    MediaOrchestrationError,
    MediaOrchestrationService,
    OrchestrationResult,
    ParentResolution,
)
from app.services.publication_enrichment import enrich_publication_draft
from app.services.relevance_screen import screen_relevance


def _error_result(item_id: str, *, state: str, message: str, transcript_status: str = "not_applicable") -> OrchestrationResult:
    return OrchestrationResult(
        item_id=item_id,
        state=state,
        parent_resolution=ParentResolution(status="none", message=message),
        transcript_status=transcript_status,
        next_action="Resolve the underlying error before retrying.",
        errors=[message],
    )


def process_discovered_article(
    item: dict[str, Any],
    *,
    orchestrator: MediaOrchestrationService,
    inbox_dir: Path,
    completer: Callable[..., Any] | None = None,
    berries: list[dict[str, Any]] | None = None,
    geographies: list[dict[str, Any]] | None = None,
    companies: list[dict[str, Any]] | None = None,
    relevance_threshold: int | None = None,
    dry_run: bool = False,
) -> tuple[OrchestrationResult, dict[str, Any]]:
    """Screen, acquire, and (if relevant) enrich one discovered web_article
    item. Returns (OrchestrationResult, extra_report) -- extra_report carries
    stage-A/B relevance detail and enrichment status for CLI/report consumers
    that want more than the generic OrchestrationResult exposes.
    """
    item_id = item["id"]
    threshold_kwargs = {"threshold": relevance_threshold} if relevance_threshold is not None else {}
    extra: dict[str, Any] = {}

    if dry_run:
        # No network calls in a dry-run, per this project's existing
        # dry-run contract ("makes no network calls and writes nothing").
        return orchestrator.process(item_id, dry_run=True), extra

    try:
        existing = orchestrator.resolve_publication_artifact(item)
    except MediaOrchestrationError as exc:
        return _error_result(item_id, state="orchestration_error", message=str(exc)), extra
    if existing.status != "none":
        # Already has a draft/trusted parent -- cheap, no network, and
        # defers to process()'s own idempotent resolution rather than
        # re-deriving the same answer here.
        return orchestrator.process(item_id, dry_run=False), extra

    stage_a = screen_relevance(title=item.get("title") or "", description=item.get("description") or "", **threshold_kwargs)
    extra["relevance_screen_stage_a"] = stage_a.as_dict()
    winning_tier = stage_a.tier
    if not stage_a.needs_body_check and not stage_a.relevant:
        return (
            OrchestrationResult(
                item_id=item_id,
                state="skipped_irrelevant",
                parent_resolution=ParentResolution(status="skipped", message=stage_a.reason),
                transcript_status="deferred",
                next_action="No action; item screened as clearly irrelevant before acquisition.",
            ),
            extra,
        )

    try:
        body = fetch_article(item.get("canonical_url") or "")
    except ArticleAcquisitionError as exc:
        extra["acquisition_failure_category"] = exc.category
        return (
            OrchestrationResult(
                item_id=item_id,
                state="article_acquisition_failed",
                parent_resolution=ParentResolution(status="none", message=str(exc)),
                # Reuses the same transcript_status string podcast/video
                # acquisition failures use, so CollectionRunner's existing
                # failure classification (retryable on acquisition_failed)
                # applies unchanged to articles too.
                transcript_status="acquisition_failed",
                next_action="Retry article acquisition; inspect acquisition_failure_category.",
                errors=[str(exc)],
            ),
            extra,
        )
    extra["acquired"] = True

    if stage_a.needs_body_check:
        stage_b = screen_relevance(
            title=item.get("title") or "",
            description=item.get("description") or "",
            body=body.full_text,
            **threshold_kwargs,
        )
        extra["relevance_screen_stage_b"] = stage_b.as_dict()
        winning_tier = stage_b.tier
        if not stage_b.relevant:
            return (
                OrchestrationResult(
                    item_id=item_id,
                    state="skipped_irrelevant",
                    parent_resolution=ParentResolution(status="skipped", message=stage_b.reason),
                    transcript_status="deferred",
                    next_action="No action; article body reviewed and confirmed irrelevant.",
                ),
                extra,
            )

    try:
        result = orchestrator.process(item_id, dry_run=False)
    except MediaOrchestrationError as exc:
        return _error_result(item_id, state="orchestration_error", message=str(exc)), extra
    if result.publication_draft_id is None:
        return result, extra

    draft_path = inbox_dir / "evidence" / f"{result.publication_draft_id}.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["article"] = body.as_dict()
    # "direct" | "adjacent" -- never "irrelevant" here, since an
    # irrelevant/borderline-rejected item never reaches draft creation.
    # Read by pending_publication_drafts()'s sort so direct berry
    # intelligence outranks adjacent stories in the review queue by
    # default, and by the review UI to label items explicitly rather
    # than presenting every draft as equally high-confidence.
    draft["relevance_tier"] = winning_tier
    extra["relevance_tier"] = winning_tier

    if completer is not None:
        # Reuse the shared enrichment mechanism (deterministic tagging +
        # optional AI suggestion, same trust markers the rest of the
        # Scanner/review UI already reads via ai_enrichment.model_
        # provenance.status) -- but feed it the real extracted article
        # text, not just the RSS blurb, since a generic-agriculture-style
        # summary alone is not enough for a useful CI summary.
        enrichment_item = dict(item)
        rss_description = (item.get("description") or "").strip()
        body_excerpt = body.full_text[:4000].strip()
        enrichment_item["publisher_description"] = (
            f"{rss_description}\n\nFull article text:\n{body_excerpt}" if rss_description else body_excerpt
        )[:4000]
        draft = enrich_publication_draft(
            draft,
            enrichment_item,
            berries=berries or [],
            geographies=geographies or [],
            entities=companies or [],
            complete_json=completer,
        )
        enrichment = draft.get("ai_enrichment") or {}
        extra["enrichment_status"] = (enrichment.get("model_provenance") or {}).get("status")
        extra["enrichment_caveats"] = enrichment.get("caveats")

    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result, extra
