"""Unit coverage for app/services/article_dedup.py's deterministic
cross-pipeline duplicate detection: normalized canonical URL first, then
conservative normalized title + source + published-date matching as
secondary evidence. Distinct stories must never merge on title
resemblance alone.
"""

from __future__ import annotations

from app.services.article_dedup import (
    find_duplicate_article,
    normalize_canonical_url,
    normalize_title,
)


def test_normalize_canonical_url_ignores_scheme_www_and_trailing_slash() -> None:
    a = normalize_canonical_url("https://www.example.com/news/blueberry-story/")
    b = normalize_canonical_url("http://example.com/news/blueberry-story")
    assert a == b


def test_normalize_canonical_url_keeps_distinct_paths_distinct() -> None:
    a = normalize_canonical_url("https://example.com/news/blueberry-story")
    b = normalize_canonical_url("https://example.com/news/strawberry-story")
    assert a != b


def test_normalize_canonical_url_empty_input() -> None:
    assert normalize_canonical_url(None) == ""
    assert normalize_canonical_url("") == ""


def test_normalize_canonical_url_keeps_distinct_query_strings_distinct() -> None:
    # Real bug found live, Global Qualitative Coverage Expansion V1
    # (2026-08-21): every openFDA recall this project acquires shares the
    # identical path (api.fda.gov/food/enforcement.json) and differs only
    # by its ?search=recall_number:... query string. Stripping the query
    # string collapsed every distinct real FDA recall onto the same
    # "existing draft" the first time this ran -- the first-processed
    # recall silently absorbed every later one instead of each getting its
    # own Evidence draft. Query strings must be preserved for a REST-API
    # search endpoint where they are the resource identifier, not a
    # tracking parameter.
    a = normalize_canonical_url('https://api.fda.gov/food/enforcement.json?search=recall_number:"H-1181-2026"')
    b = normalize_canonical_url('https://api.fda.gov/food/enforcement.json?search=recall_number:"H-0522-2026"')
    assert a != b


def test_normalize_canonical_url_ignores_only_fragment() -> None:
    a = normalize_canonical_url("https://example.com/news/blueberry-story?ref=twitter")
    b = normalize_canonical_url("https://example.com/news/blueberry-story?ref=twitter#comments")
    assert a == b


def test_normalize_title_strips_trailing_publisher_suffix() -> None:
    a = normalize_title("Blueberry Variety Dispute Escalates - Produce Report")
    b = normalize_title("Blueberry Variety Dispute Escalates")
    assert a == b


def test_normalize_title_strips_pipe_style_suffix_and_punctuation() -> None:
    a = normalize_title("Blueberry Variety Dispute Escalates | Produce Report")
    b = normalize_title("Blueberry Variety Dispute Escalates!")
    assert a == b


def test_normalize_title_does_not_conflate_genuinely_different_titles() -> None:
    a = normalize_title("Blueberry Variety Dispute Escalates - Produce Report")
    b = normalize_title("Raspberry Import Quota Raised - Produce Report")
    assert a != b


def _evidence(**changes) -> dict:
    record = {
        "id": "ev-trusted-one",
        "title": "Blueberry Variety Dispute Escalates - Produce Report",
        "source_url": "https://example.com/news/blueberry-dispute",
        "source_id": "source-produce-report",
        "published_date": "2026-08-10",
    }
    record.update(changes)
    return record


def _draft(**changes) -> dict:
    record = {
        "id": "ev-media-pendingone",
        "title": "Blueberry Variety Dispute Escalates",
        "source_url": "https://example.com/news/blueberry-dispute-mirror",
        "source_id": "source-produce-report",
        "published_date": "2026-08-10",
    }
    record.update(changes)
    return record


def _item(**changes) -> dict:
    item = {
        "id": "media-new-discovery",
        "title": "Blueberry Variety Dispute Escalates",
        "canonical_url": "https://www.example.com/news/blueberry-dispute/",
        "source_id": "source-produce-report",
        "published_date": "2026-08-10",
    }
    item.update(changes)
    return item


def test_find_duplicate_article_matches_on_normalized_url_alone() -> None:
    existing = [_evidence(title="A totally different headline that would never title-match")]
    match = find_duplicate_article(_item(), existing_records=existing)
    assert match == "ev-trusted-one"


def test_find_duplicate_article_matches_on_title_source_and_date_when_url_differs() -> None:
    existing = [_draft()]
    match = find_duplicate_article(
        _item(canonical_url="https://example.com/completely/different/path"),
        existing_records=existing,
    )
    assert match == "ev-media-pendingone"


def test_find_duplicate_article_requires_matching_source_id() -> None:
    existing = [_draft(source_id="source-other-outlet")]
    match = find_duplicate_article(
        _item(canonical_url="https://example.com/completely/different/path"),
        existing_records=existing,
    )
    assert match is None


def test_find_duplicate_article_requires_matching_published_date() -> None:
    existing = [_draft(published_date="2026-08-11")]
    match = find_duplicate_article(
        _item(canonical_url="https://example.com/completely/different/path"),
        existing_records=existing,
    )
    assert match is None


def test_find_duplicate_article_never_merges_on_title_similarity_alone() -> None:
    """Two real, distinct stories that happen to share several words in
    their headlines must not be treated as duplicates -- only an exact
    (post-normalization) title match, combined with matching source and
    date, counts."""
    existing = [
        _draft(
            title="China Announces Anti-Dumping Measures On Pecans",
            source_id="source-produce-report",
            published_date="2026-08-10",
        )
    ]
    item = _item(
        title="China Announces Anti-Dumping Measures On Blueberries",
        canonical_url="https://example.com/completely/different/path",
        source_id="source-produce-report",
        published_date="2026-08-10",
    )
    assert find_duplicate_article(item, existing_records=existing) is None


def test_find_duplicate_article_no_match_returns_none() -> None:
    existing = [_evidence(), _draft()]
    item = _item(
        title="An Entirely Unrelated Story About Trade Logistics",
        canonical_url="https://example.com/unrelated/story",
        published_date="2026-08-12",
    )
    assert find_duplicate_article(item, existing_records=existing) is None
