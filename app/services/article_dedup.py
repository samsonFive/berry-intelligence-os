"""Bounded, deterministic cross-pipeline duplicate detection for articles.

A real gap found running the recurring refresh twice: the same real-world
article can already be trusted under one deterministic id (created by an
earlier discovery pass) and get re-discovered under a *different*
deterministic id later (a different capture pipeline, or the publisher's
own title text drifting -- e.g. one capture kept a " - Publisher Name"
suffix, another stripped it). `MediaOrchestrationService.resolve_
publication_artifact()`'s own dedup only ever catches the *same*
`discovered_item_id`/`publication_draft_id` -- by design, since that's an
exact, deterministic content-derived match, not a fuzzy one. This module
adds a second, narrower check specifically for the cross-pipeline case,
run *before* acquisition so a genuine duplicate never costs a fetch.

Two evidence tiers, checked in order, both conservative by design:

1. Normalized canonical URL -- the strongest possible signal (the same
   real webpage), so an exact match here is enough on its own.
2. Normalized title + matching source_id + matching published_date (day
   granularity) -- all three must agree. Title normalization strips a
   trailing " - Publisher" / " | Publisher" suffix and punctuation, but
   never does fuzzy/similarity matching -- two articles with merely
   *similar* titles are never treated as the same story. Source id and
   date are both required alongside the title match specifically so a
   wire-service headline echoed verbatim by two different outlets on two
   different days is never conflated with a real duplicate.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

_PUBLISHER_SUFFIX_RE = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Parameters whose documented/common purpose is request attribution rather
# than resource identity.  This is intentionally an allow-list: unknown
# parameters remain part of the identity because API/search endpoints often
# encode the actual record in their query string (TD-040).
_TRACKING_QUERY_PARAMETERS = {
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "vero_conv",
    "vero_id",
}


def _is_tracking_parameter(name: str) -> bool:
    folded = name.casefold()
    return folded.startswith("utm_") or folded in _TRACKING_QUERY_PARAMETERS


def normalize_canonical_url(url: str | None) -> str:
    """Scheme/host lowercased, no fragment, no trailing slash --
    deliberately not stripping path segments OR the query string, since
    two different articles on the same site legitimately have different
    paths, and (found live, Global Qualitative Coverage Expansion V1,
    2026-08-21) a REST API search endpoint's query string can be the
    *only* thing that identifies a distinct record -- e.g. every openFDA
    recall this project acquires shares the identical path
    (api.fda.gov/food/enforcement.json) and differs only by its
    ?search=recall_number:... query string. Dropping the query string
    unconditionally collapsed every real, distinct FDA recall onto the
    same 'existing draft' the first time this ran (see TD-040) -- keeping
    it is strictly more conservative (fewer false-positive duplicate
    collapses) and no existing test relied on query-string stripping."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = parts.netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    semantic_query = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_parameter(name)
    ]
    # Sorting makes parameter-order variants deterministic without changing
    # which semantic parameters participate in identity.
    query_text = urlencode(sorted(semantic_query), doseq=True)
    query = f"?{query_text}" if query_text else ""
    return f"{host}{path}{query}".casefold()


def normalize_title(title: str | None) -> str:
    """Strips one trailing " - Publisher"/" | Publisher"-style suffix
    (the real, observed cause of a false non-match between two captures
    of the same article), then reduces to lowercase alphanumerics only so
    punctuation/quote-style differences don't defeat an otherwise exact
    match. This is normalization for an exact-match comparison, not a
    similarity score -- two genuinely different titles are never treated
    as equal by this function."""
    if not title:
        return ""
    stripped = _PUBLISHER_SUFFIX_RE.sub("", title.strip())
    return _NON_ALNUM_RE.sub("", stripped.casefold())


def _publisher_identity(record: dict[str, Any]) -> set[str]:
    """Exact publisher names/hosts declared by discovery or acquisition."""
    raw = record.get("raw_metadata") or {}
    article = record.get("article") or {}
    identities = {
        normalize_title(raw.get("origin_publisher_name")),
        normalize_title(record.get("source_name")),
    }
    for url in (raw.get("origin_publisher_url"), article.get("final_url"), record.get("source_url")):
        normalized = normalize_canonical_url(url)
        if normalized:
            identities.add(normalized.split("/", 1)[0])
    return {value for value in identities if value}


def _lineage_rank(record: dict[str, Any]) -> tuple[int, str]:
    """Prefer a direct publisher record when deterministic matches tie."""
    source_url = normalize_canonical_url(record.get("source_url"))
    source_id = str(record.get("source_id") or "")
    raw = record.get("raw_metadata") or {}
    generic_search = (
        source_url.startswith("news.google.com/")
        or "news-search" in source_id
        or bool(raw.get("origin_publisher_name"))
    )
    return (1 if generic_search else 0, str(record.get("id") or ""))


def _preferred_id(records: list[dict[str, Any]]) -> str | None:
    ranked = sorted((record for record in records if record.get("id")), key=_lineage_rank)
    return ranked[0].get("id") if ranked else None


def find_duplicate_article(
    item: dict[str, Any],
    *,
    existing_records: list[dict[str, Any]],
) -> str | None:
    """Returns the id of an existing trusted Evidence record or pending
    draft that is the same real-world article as `item` (a discovered_media
    item), or None. `existing_records` should include both trusted
    published Evidence and pending inbox drafts -- a duplicate of either
    is still a duplicate."""
    item_urls = {
        normalize_canonical_url(item.get("canonical_url")),
        normalize_canonical_url(item.get("resolved_canonical_url")),
    } - {""}
    if item_urls:
        matches: list[dict[str, Any]] = []
        for record in existing_records:
            record_urls = {
                normalize_canonical_url(record.get("source_url")),
                normalize_canonical_url((record.get("article") or {}).get("final_url")),
            } - {""}
            if item_urls & record_urls:
                matches.append(record)
        if matches:
            return _preferred_id(matches)

    item_title = normalize_title(item.get("title"))
    item_source = item.get("source_id")
    item_date = (item.get("published_date") or "")[:10]
    if not (item_title and item_source and item_date):
        return None
    same_source_matches = []
    for record in existing_records:
        if record.get("source_id") != item_source:
            continue
        if (record.get("published_date") or "")[:10] != item_date:
            continue
        if normalize_title(record.get("title")) == item_title:
            same_source_matches.append(record)
    if same_source_matches:
        return _preferred_id(same_source_matches)
    # Observed deterministic cross-pipeline case: Google News supplies an
    # opaque redirect URL and a different source_id from the publisher RSS,
    # but explicitly names the origin publisher. Exact title, date, and
    # publisher name/host are high-confidence identity; no fuzzy match.
    item_publishers = _publisher_identity(item)
    if item_publishers:
        publisher_matches = []
        for record in existing_records:
            if (record.get("published_date") or "")[:10] != item_date:
                continue
            if normalize_title(record.get("title")) != item_title:
                continue
            if item_publishers & _publisher_identity(record):
                publisher_matches.append(record)
        if publisher_matches:
            return _preferred_id(publisher_matches)
    return None
