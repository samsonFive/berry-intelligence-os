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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.services.article_acquisition import ArticleAcquisitionError, fetch_article, repeated_body_conflict
from app.services.media_orchestration import (
    MediaOrchestrationError,
    MediaOrchestrationService,
    OrchestrationResult,
    ParentResolution,
)
from app.services.media_discovery import _next_article_content_check
from app.services.publication_enrichment import enrich_publication_draft
from app.services.relevance_screen import TIER_DIRECT, TIER_UNCERTAIN, screen_relevance
from app.services.source_completeness import RETRYABLE_FAILURES, normalize_failure_category, with_source_completeness


# app/services/article_acquisition.py's ArticleAcquisitionError categories
# that represent a genuine access limitation on content that is known to
# exist (a bot-wall, a paywall, or the extractor finding nothing readable
# at all) -- as opposed to a transient network condition (timeout,
# transport_error, redirect_error, http_error, malformed_html) that a plain
# retry can still resolve and must not be treated as permanently
# inaccessible.
_ACCESS_LIMITED_CATEGORIES = frozenset({"blocked", "paywall", "empty_body", "interstitial", "script_rendered"})


def _error_result(item_id: str, *, state: str, message: str, transcript_status: str = "not_applicable") -> OrchestrationResult:
    return OrchestrationResult(
        item_id=item_id,
        state=state,
        parent_resolution=ParentResolution(status="none", message=message),
        transcript_status=transcript_status,
        next_action="Resolve the underlying error before retrying.",
        errors=[message],
    )


def _persist_relevance_tier(inbox_dir: Path, draft_id: str | None, tier: str | None, *, dry_run: bool) -> None:
    """Writes relevance_tier onto the persisted draft file for the metadata-
    only fallback paths below, mirroring what the main body-acquired path
    already does at draft-write time. Without this, the tier only lived on
    the transient OrchestrationResult and never reached the review queue's
    own triage (app/services/morning_brief.py's assign_pending_triage reads
    it from the stored draft, not from a CLI return value)."""
    if dry_run or not draft_id or not tier:
        return
    draft_path = inbox_dir / "evidence" / f"{draft_id}.json"
    if not draft_path.exists():
        return
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft["relevance_tier"] = tier
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _persist_source_failure(
    inbox_dir: Path, draft_id: str | None, category: str, *, dry_run: bool,
) -> None:
    if dry_run or not draft_id:
        return
    draft_path = inbox_dir / "evidence" / f"{draft_id}.json"
    if not draft_path.exists():
        return
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    discovery = draft.setdefault("discovery_provenance", {})
    discovery["acquisition_failure_category"] = normalize_failure_category(category)
    draft = with_source_completeness(draft, failure_category=category)
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _content_check_requested(item: dict[str, Any]) -> bool:
    if item.get("discovery_changed_at"):
        return True
    next_raw = item.get("next_content_check_at")
    if not isinstance(next_raw, str):
        return False
    try:
        due = datetime.fromisoformat(next_raw)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return datetime.now(timezone.utc) >= due.astimezone(timezone.utc)


def _persist_content_check(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    body: Any,
    prior_hash: str | None,
    representation_id: str | None,
) -> str:
    """Persist an untrusted identity probe without touching a review record."""
    status = (
        "KNOWN_IDENTICAL"
        if prior_hash and prior_hash == body.content_sha256
        else "CONTENT_CHANGED"
        if prior_hash
        else "CONTENT_CHANGE_UNVERIFIED"
    )
    path = inbox_dir / "discovered_media" / f"{item['id']}.json"
    record = dict(item)
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
    checked_at = body.as_dict().get("acquisition", {}).get("fetched_at") or datetime.now(timezone.utc).isoformat()
    record.update(
        {
            "resolved_canonical_url": body.final_url or body.source_url,
            "last_content_check_at": checked_at,
            "next_content_check_at": _next_article_content_check(
                item["id"], item.get("published_date"), checked_at
            ),
            "article_identity_probe": {
                "status": status,
                "representation_id": representation_id,
                "prior_content_sha256": prior_hash,
                "observed_content_sha256": body.content_sha256,
                "final_url": body.final_url or body.source_url,
                "checked_at": checked_at,
            },
        }
    )
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return status


def _persist_blocked_content_check(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    category: str,
    representation_id: str | None,
) -> None:
    """Record a structural/access-limited probe without creating retries."""
    path = inbox_dir / "discovered_media" / f"{item['id']}.json"
    record = dict(item)
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record.update(
        {
            "last_content_check_at": checked_at,
            "next_content_check_at": _next_article_content_check(
                item["id"], item.get("published_date"), checked_at
            ),
            "article_identity_probe": {
                "status": "CHECK_BLOCKED",
                "category": category,
                "representation_id": representation_id,
                "checked_at": checked_at,
            },
        }
    )
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    geo_matchers: "list[tuple[str, Any]] | None" = None,
    company_matchers: "list[tuple[str, Any]] | None" = None,
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
        if _content_check_requested(item):
            extra["body_acquisition_attempted"] = True
            try:
                body = fetch_article(item.get("resolved_canonical_url") or item.get("canonical_url") or "")
            except ArticleAcquisitionError as exc:
                if exc.category in _ACCESS_LIMITED_CATEGORIES:
                    _persist_blocked_content_check(
                        inbox_dir,
                        item,
                        category=exc.category,
                        representation_id=existing.evidence_id or existing.draft_id,
                    )
                    extra["article_identity_probe"] = "CHECK_BLOCKED"
                    extra["duplicate_stage"] = "post_acquisition_structural_block"
                    result = orchestrator.process(item_id, dry_run=False)
                    result.duplicate_rejected_late = True
                    return result, extra
                result = _error_result(
                    item_id,
                    state="article_update_check_failed",
                    message=str(exc),
                    transcript_status="acquisition_failed",
                )
                result.parent_resolution = existing
                result.publication_draft_id = existing.draft_id
                return result, extra
            representation_id = existing.evidence_id or existing.draft_id
            prior_record = next(
                (record for record in orchestrator.publication_records() if record.get("id") == representation_id),
                {},
            )
            prior_hash = (prior_record.get("article") or {}).get("content_sha256")
            probe_status = _persist_content_check(
                inbox_dir,
                item,
                body=body,
                prior_hash=prior_hash,
                representation_id=representation_id,
            )
            extra["article_identity_probe"] = probe_status
            if probe_status == "KNOWN_IDENTICAL":
                extra["duplicate_stage"] = "post_acquisition_known_identical_refresh"
                result = orchestrator.process(item_id, dry_run=False)
                result.duplicate_rejected_late = True
                return result, extra
            return (
                OrchestrationResult(
                    item_id=item_id,
                    state=(
                        "article_update_detected"
                        if probe_status == "CONTENT_CHANGED"
                        else "article_update_unverified"
                    ),
                    parent_resolution=existing,
                    publication_draft_id=existing.draft_id,
                    transcript_status="not_applicable",
                    next_action=(
                        "Inspect the private article identity probe; the existing publication was not overwritten."
                    ),
                ),
                extra,
            )
        extra["duplicate_stage"] = "pre_acquisition_existing_representation"
        result = orchestrator.process(item_id, dry_run=False)
        result.duplicate_rejected_late = True
        return result, extra

    stage_a = screen_relevance(
        title=item.get("title") or "", description=item.get("description") or "",
        geo_matchers=geo_matchers, company_matchers=company_matchers, **threshold_kwargs,
    )
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

    extra["body_acquisition_attempted"] = True
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
            _persist_relevance_tier(inbox_dir, result.publication_draft_id, winning_tier, dry_run=dry_run)
            _persist_source_failure(inbox_dir, result.publication_draft_id, exc.category, dry_run=dry_run)
            return result, extra
        if (stage_a.query_corroboration or always_body_check) and exc.category in _ACCESS_LIMITED_CATEGORIES:
            # Two distinct real reasons Stage A was kept open despite zero
            # direct berry/CI metadata signal, both landing in the same
            # honest fallback: (a) a registered geography/company entity
            # plus a corporate-action term (relevance_screen.py's
            # _query_corroboration_hit), or (b) the source itself is
            # already pre-scoped by construction (always_body_check --
            # e.g. a government register or a CIK-scoped SEC EDGAR search
            # whose own query already names the entity/topic). Either way
            # the article body cannot be verified (a Google News redirect
            # page, or an SEC filing's raw SGML-wrapped document -- neither
            # is a real HTTP block, both are real, structural extraction
            # dead ends). Relevance is genuinely UNCONFIRMED here: query/
            # source provenance alone must never justify a DIRECT/ADJACENT
            # claim, so this creates the same kind of untrusted metadata-
            # only draft as the TIER_DIRECT fallback above, but explicitly
            # tagged TIER_UNCERTAIN so it is never presented as confident
            # berry intelligence -- a human decides, same as every other
            # draft.
            reason = (
                f"query-provenance + title corroboration ({stage_a.query_corroboration!r})"
                if stage_a.query_corroboration
                else "a pre-scoped source (always_body_check)"
            )
            extra["acquisition_fallback"] = (
                f"body fetch failed ({exc.category}); Stage A kept this open only on {reason}, not confirmed relevance -- an explicitly "
                "uncertain metadata-only draft was created for human review instead of dropping the item."
            )
            try:
                result = orchestrator.process(item_id, dry_run=dry_run)
            except MediaOrchestrationError as inner_exc:
                return _error_result(item_id, state="orchestration_error", message=str(inner_exc)), extra
            result.relevance_tier = TIER_UNCERTAIN
            _persist_relevance_tier(inbox_dir, result.publication_draft_id, TIER_UNCERTAIN, dry_run=dry_run)
            _persist_source_failure(inbox_dir, result.publication_draft_id, exc.category, dry_run=dry_run)
            return result, extra
        failure_code = normalize_failure_category(exc.category)
        retryable = failure_code in RETRYABLE_FAILURES
        extra["acquisition_failure_retryable"] = retryable
        return (
            OrchestrationResult(
                item_id=item_id,
                state="article_acquisition_failed",
                parent_resolution=ParentResolution(status="none", message=str(exc)),
                # Reuses the same transcript_status string podcast/video
                # acquisition failures use, so CollectionRunner's existing
                # failure classification (retryable on acquisition_failed)
                # applies unchanged to articles too.
                transcript_status="acquisition_failed" if retryable else "malformed",
                next_action=(
                    "Retry article acquisition under the existing bounded runner policy."
                    if retryable else
                    "Permanent/structural acquisition failure; operator inspection is required."
                ),
                errors=[str(exc)],
            ),
            extra,
        )
    extra["acquired"] = True

    if repeated_body_conflict(body, orchestrator.publication_records()):
        extra["acquisition_failure_category"] = "repeated_body"
        extra["acquisition_failure_retryable"] = False
        return (
            _error_result(
                item_id,
                state="article_acquisition_failed",
                message="REPEATED_BODY: identical extracted body already belongs to multiple distinct publication URLs",
                transcript_status="malformed",
            ),
            extra,
        )

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

    draft = with_source_completeness(draft)
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result, extra
