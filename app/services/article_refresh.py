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
from app.services.relevance_screen import TIER_DIRECT, screen_relevance


# app/services/article_acquisition.py's ArticleAcquisitionError categories
# that represent a genuine access limitation on content that is known to
# exist (a bot-wall, a paywall, or the extractor finding nothing readable
# at all) -- as opposed to a transient network condition (timeout,
# transport_error, redirect_error, http_error, malformed_html) that a plain
# retry can still resolve and must not be treated as permanently
# inaccessible.
_ACCESS_LIMITED_CATEGORIES = frozenset({"blocked", "paywall", "empty_body"})


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
    always_body_check: bool = False,
) -> tuple[OrchestrationResult, dict[str, Any]]:
    """Screen, acquire, and (if relevant) enrich one discovered web_article
    item. Returns (OrchestrationResult, extra_report) -- extra_report carries
    stage-A/B relevance detail and enrichment status for CLI/report consumers
    that want more than the generic OrchestrationResult exposes.

    `always_body_check`: Stage A's metadata-only CONFIDENT-irrelevant exit
    (relevance_screen.py: zero category signal in title+description) is
    correct for the general web, but a source that is already scoped to
    berries/regulatory-trade by construction -- e.g. a government-register
    search feed built from a query like "strawberries antidumping" -- can
    still produce a docket-number-only headline with no berry word in it
    (found auditing the Mainstream News + Regulatory Coverage Recall
    Benchmark). Set True only for items from such a pre-scoped source so
    the body is always fetched and given a real Stage B read; Stage B's own
    berry-identity/adjacent-topic gate is unchanged and can still reject it.
    Default False preserves the existing Stage A behavior for every
    ordinary web source.
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
        if not always_body_check:
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
        extra["stage_a_override"] = (
            "always_body_check: source is pre-scoped (e.g. a government-register search feed); "
            "body fetched for a real Stage B read despite a CONFIDENT-irrelevant metadata screen."
        )

    try:
        body = fetch_article(item.get("canonical_url") or "")
    except ArticleAcquisitionError as exc:
        extra["acquisition_failure_category"] = exc.category
        # Only a genuine *access limitation* (bot-block, paywall, or the
        # extractor finding literally nothing readable -- never a transient
        # network condition like timeout/transport/redirect/http_error/
        # malformed_html, which a plain retry can still resolve) falls back
        # to a metadata-only draft. Conflating a timeout with "this content
        # is inaccessible" would wrongly turn every transient network
        # hiccup into a permanent metadata-only draft instead of a real
        # retry -- caught by tests/test_article_refresh.py's own retryable-
        # vs-operator contract.
        if stage_a.tier == TIER_DIRECT and exc.category in _ACCESS_LIMITED_CATEGORIES:
            # Stage A already confirmed relevance from title+description
            # alone (a real berry/cultivar name, not a guess) -- the body
            # fetch failing (paywall, bot-wall, rate limit) is an access
            # limitation on the *full text*, not on whether this item
            # belongs in review. Per this project's paywall/copyright
            # discipline (never bypass, never store unauthorized full text),
            # fall back to the same metadata-only draft path the generic
            # (non-web_article) orchestration already uses -- title,
            # canonical URL, publisher, date, and whatever description the
            # discovery feed itself legitimately provided, nothing scraped.
            extra["acquisition_fallback"] = (
                f"body fetch failed ({exc.category}); Stage A already confirmed relevance from metadata alone, "
                "so a metadata-only draft was created instead of dropping the item."
            )
            try:
                result = orchestrator.process(item_id, dry_run=dry_run)
            except MediaOrchestrationError as inner_exc:
                return _error_result(item_id, state="orchestration_error", message=str(inner_exc)), extra
            result.relevance_tier = winning_tier
            return result, extra
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

    if stage_a.needs_body_check or always_body_check:
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
