"""Cheap, deterministic pre-acquisition/pre-AI relevance screening.

Runs on title + publisher description (and, for articles, the acquired
body when available) alone -- no model call, no network, no cost -- so
neither expensive audio transcription nor an AI enrichment call ever runs
against content with no berry competitive-intelligence signal. This is a
triage proposal, not trusted intelligence: it never writes to a trusted
repository and its output is always inspectable and overridable by an
operator.

Thresholds are configurable (constructor arguments), not hardcoded
architecture; the weighted-category design and default threshold are a
first draft meant to be recalibrated once run against real discovered
items, not a final tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class _RelevanceCategory:
    name: str
    weight: int
    terms: tuple[str, ...]


# "berry_identity" is the one category whose weight (3) alone clears the
# default threshold and whose presence overrides the aggregate score
# entirely (see screen_relevance): a title/description that names a berry
# or cultivar directly should never be screened out on aggregate score
# alone, even with no other signal.
CATEGORIES: tuple[_RelevanceCategory, ...] = (
    _RelevanceCategory(
        "berry_identity", 3,
        ("blueberry", "blueberries", "strawberry", "strawberries", "raspberry", "raspberries",
         "blackberry", "blackberries", "berry", "berries", "highbush", "southern highbush",
         "cultivar", "cultivars", "variety", "varieties", "breeding", "genetics"),
    ),
    _RelevanceCategory(
        "commercial_volume_geography", 2,
        ("acreage", "hectare", "hectares", "yield", "season", "harvest", "export", "import",
         "grower", "growers", "shipper", "shippers", "production"),
    ),
    _RelevanceCategory(
        "market_pricing", 2,
        ("pricing", "price", "prices", "demand", "supply", "retail", "consumer", "shelf life",
         "retailer", "retailers", "packaging"),
    ),
    _RelevanceCategory(
        "disease_technology", 1,
        ("disease", "pest", "technology", "mechanization", "cold storage", "packing"),
    ),
)

DEFAULT_THRESHOLD = 4
RELEVANCE_SCREEN_VERSION = "relevance-screen-v1"


@dataclass(frozen=True)
class RelevanceScreen:
    score: int
    threshold: int
    relevant: bool
    reason: str
    likely_topics: tuple[str, ...]
    matched_terms: tuple[str, ...]
    version: str = RELEVANCE_SCREEN_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "threshold": self.threshold,
            "relevant": self.relevant,
            "reason": self.reason,
            "likely_topics": list(self.likely_topics),
            "matched_terms": list(self.matched_terms),
            "version": self.version,
        }


def _word_present(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def screen_relevance(
    *,
    title: str,
    description: str,
    body: str | None = None,
    threshold: int = DEFAULT_THRESHOLD,
) -> RelevanceScreen:
    """Deterministic, keyword-weighted first pass. No AI call, no network.

    `body` is optional and, when given, is truncated to its first 4000
    characters before matching -- enough to catch real signal in a long
    article without materially changing runtime cost versus title+
    description alone.
    """

    text = f"{title or ''} {description or ''} {(body or '')[:4000]}".casefold()
    score = 0
    matched_categories: list[str] = []
    matched_terms: list[str] = []
    berry_identity_hit = False
    for category in CATEGORIES:
        hits = [term for term in category.terms if _word_present(text, term)]
        if not hits:
            continue
        score += category.weight
        matched_categories.append(category.name)
        matched_terms.extend(hits)
        if category.name == "berry_identity":
            berry_identity_hit = True

    relevant = score >= threshold or berry_identity_hit
    if not matched_categories:
        reason = f"No berry/CI keyword signals matched (score 0/{threshold})."
    elif relevant:
        reason = f"Matched {', '.join(matched_categories)} (score {score}, threshold {threshold})."
    else:
        reason = f"Weak signal only: {', '.join(matched_categories)} (score {score}, below threshold {threshold})."

    return RelevanceScreen(
        score=score,
        threshold=threshold,
        relevant=relevant,
        reason=reason,
        likely_topics=tuple(dict.fromkeys(matched_categories)),
        matched_terms=tuple(dict.fromkeys(matched_terms)),
    )
