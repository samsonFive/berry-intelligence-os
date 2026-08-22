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
from urllib.parse import urlsplit

_PUBLISHER_SUFFIX_RE = re.compile(r"\s+[-|–—]\s+[^-|–—]{2,40}$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


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
    query = f"?{parts.query}" if parts.query else ""
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
    item_url = normalize_canonical_url(item.get("canonical_url"))
    if item_url:
        for record in existing_records:
            record_url = normalize_canonical_url(
                record.get("source_url") or (record.get("article") or {}).get("final_url")
            )
            if record_url and record_url == item_url:
                return record.get("id")

    item_title = normalize_title(item.get("title"))
    item_source = item.get("source_id")
    item_date = (item.get("published_date") or "")[:10]
    if not (item_title and item_source and item_date):
        return None
    for record in existing_records:
        if record.get("source_id") != item_source:
            continue
        if (record.get("published_date") or "")[:10] != item_date:
            continue
        if normalize_title(record.get("title")) == item_title:
            return record.get("id")
    return None
