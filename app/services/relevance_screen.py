"""Cheap, deterministic, two-stage relevance screening.

No AI call, no network cost of its own -- this is a triage proposal, not
trusted intelligence: it never writes to a trusted repository and its
output is always inspectable and overridable by an operator.

Design, per a real false-positive found during this project's own article
pilot: weak generic-agriculture signals (e.g. "production" + "export")
must never, on their own, make a non-berry article "relevant" -- an
onion, apple, fig, banana, tree-nut, or durian story that merely mentions
harvests and exports is not berry competitive intelligence. Berry
identity dominates: an item is only ever relevant if a berry/cultivar is
actually named, somewhere.

STAGE A (`screen_relevance(body=None)`, title + publisher description
only): a direct berry mention is CONFIDENT-relevant; zero category
signal at all is CONFIDENT-irrelevant (cheap exit, no need to acquire
the article body just to confirm nothing is there); anything in
between -- generic agriculture/pricing/technology language with no
berry mention -- is BORDERLINE, not relevant yet, and needs the real
article body to resolve honestly rather than guessing from a headline
alone.

STAGE B (`screen_relevance(body=...)`, called only for a borderline
Stage A result, once the body has been acquired anyway): the gate is
simply "does a berry/cultivar appear anywhere in the real text" -- no
score threshold, no AI. This is what lets a generically-headlined
article that turns out to genuinely discuss a berry crop still pass,
while a same-scoring article about onions or figs correctly does not.

Thresholds are configurable, not hardcoded architecture; the
weighted-category design remains a first draft meant to be recalibrated
against real discovered items, not a final tuning.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class _RelevanceCategory:
    name: str
    weight: int
    terms: tuple[str, ...]


CATEGORIES: tuple[_RelevanceCategory, ...] = (
    # Genuinely berry-specific names only. "variety"/"cultivar"/"breeding"/
    # "genetics" were removed from this category after a real false
    # positive during this redesign's own test writing: "the first apple
    # varieties from the new crop" matched "varieties" and, being in the
    # auto-relevant berry_identity category, made an apple-crop article
    # confidently relevant -- these are crop-agnostic genetics terms, not
    # berry identity, and belong in their own weaker, non-auto-triggering
    # category below (they can still contribute to a Stage B score
    # alongside an actual berry name, just never trigger relevance alone).
    _RelevanceCategory(
        "berry_identity", 3,
        ("blueberry", "blueberries", "strawberry", "strawberries", "raspberry", "raspberries",
         "blackberry", "blackberries", "highbush", "southern highbush"),
    ),
    # The generic, unspecific "berry"/"berries" alone deliberately does
    # NOT auto-trigger relevance -- a real pilot re-run found two
    # multi-commodity trade-delegation articles ("...spanning table
    # grapes, apples and pears, citrus, mangos, avocados, cherries,
    # berries, summer fruit...") where "berries" was one word in an
    # 8-item fruit list with zero actual berry-specific content anywhere
    # in the article. It still contributes to the score and can combine
    # with other signal, but only a *named* berry is confident identity.
    _RelevanceCategory("generic_berry_mention", 1, ("berry", "berries")),
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
    _RelevanceCategory(
        "crop_genetics", 1,
        ("cultivar", "cultivars", "variety", "varieties", "breeding", "genetics"),
    ),
)

DEFAULT_THRESHOLD = 4
RELEVANCE_SCREEN_VERSION = "relevance-screen-v2"

CONFIDENT = "confident"
BORDERLINE = "borderline"


@dataclass(frozen=True)
class RelevanceScreen:
    score: int
    threshold: int
    relevant: bool
    confidence: str  # "confident" | "borderline"
    berry_identity_hit: bool
    reason: str
    likely_topics: tuple[str, ...]
    matched_terms: tuple[str, ...]
    version: str = RELEVANCE_SCREEN_VERSION

    @property
    def needs_body_check(self) -> bool:
        """True when this was a Stage A (metadata-only) result that could
        not be confidently decided -- the caller should acquire the real
        article body and call screen_relevance() again with body= before
        treating this item as irrelevant."""
        return self.confidence == BORDERLINE

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "threshold": self.threshold,
            "relevant": self.relevant,
            "confidence": self.confidence,
            "berry_identity_hit": self.berry_identity_hit,
            "reason": self.reason,
            "likely_topics": list(self.likely_topics),
            "matched_terms": list(self.matched_terms),
            "version": self.version,
        }


def _word_present(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


# A capitalized 1-3-word proper noun immediately followed by "Berries"/
# "Berry" -- a company or brand name (e.g. "Twin River Berries", the real
# company in this project's own SanLucar-acquisition pilot article), not
# the generic common noun. Checked against the *original*-case text
# (company names are proper nouns; the rest of this module deliberately
# works case-insensitively). This is a real, narrow gap found manually
# inspecting that article: its body never once names a specific berry
# species, only the company name and "premium fruit" -- a genuine berry
# M&A story the species-name-only gate would otherwise miss entirely.
_BERRY_COMPANY_NAME_RE = re.compile(r"\b(?:[A-Z][A-Za-z'-]*\s+){1,3}Berr(?:y|ies)\b")


def _named_berry_company(original_case_text: str) -> str | None:
    match = _BERRY_COMPANY_NAME_RE.search(original_case_text or "")
    return match.group(0) if match else None


def _match(text: str) -> tuple[int, list[str], list[str], bool]:
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
    return score, matched_categories, matched_terms, berry_identity_hit


def screen_relevance(
    *,
    title: str,
    description: str,
    body: str | None = None,
    threshold: int = DEFAULT_THRESHOLD,
) -> RelevanceScreen:
    """Stage A when `body` is None (title + description only); Stage B
    when `body` is given (full text including the real article body).
    See this module's docstring for the two-stage design and why berry
    identity is the gate rather than an aggregate score threshold."""

    original_metadata_text = f"{title or ''} {description or ''}"
    metadata_text = original_metadata_text.casefold()

    if body is None:
        score, matched_categories, matched_terms, species_hit = _match(metadata_text)
        company_name = _named_berry_company(original_metadata_text)
        if company_name and not species_hit:
            matched_categories.append("berry_company_name")
            matched_terms.append(company_name)
        if species_hit or company_name:
            reason = (
                f"Berry/cultivar named directly in title or description (score {score})."
                if species_hit
                else f"Berry company/brand name ({company_name!r}) in title or description."
            )
            return RelevanceScreen(
                score=score, threshold=threshold, relevant=True, confidence=CONFIDENT,
                berry_identity_hit=True, reason=reason,
                likely_topics=tuple(dict.fromkeys(matched_categories)),
                matched_terms=tuple(dict.fromkeys(matched_terms)),
            )
        if score == 0:
            return RelevanceScreen(
                score=0, threshold=threshold, relevant=False, confidence=CONFIDENT,
                berry_identity_hit=False,
                reason="No berry/CI keyword signals matched title or description at all.",
                likely_topics=(), matched_terms=(),
            )
        return RelevanceScreen(
            score=score, threshold=threshold, relevant=False, confidence=BORDERLINE,
            berry_identity_hit=False,
            reason=(
                f"Generic agriculture signal only ({', '.join(matched_categories)}, score {score}) with no "
                "berry/cultivar mention -- not relevant on metadata alone; needs the real article body to confirm."
            ),
            likely_topics=tuple(dict.fromkeys(matched_categories)),
            matched_terms=tuple(dict.fromkeys(matched_terms)),
        )

    # Stage B: full text including the real article body. Berry identity
    # is the sole gate here -- no score threshold, deliberately, per this
    # module's docstring (a generic-agriculture score alone must never
    # carry an onion/apple/fig/banana/tree-nut/durian story through).
    original_full_text = f"{original_metadata_text} {(body or '')[:8000]}"
    full_text = f"{metadata_text} {(body or '')[:8000]}".casefold()
    score, matched_categories, matched_terms, species_hit = _match(full_text)
    company_name = _named_berry_company(original_full_text)
    berry_identity_hit = species_hit or bool(company_name)
    if company_name and not species_hit:
        matched_categories.append("berry_company_name")
        matched_terms.append(company_name)

    if species_hit:
        reason = f"Berry/cultivar mentioned in the article body ({', '.join(matched_categories)}, score {score})."
    elif company_name:
        reason = f"Berry company/brand name ({company_name!r}) found in the article -- no species named, but the entity itself is a berry business."
    else:
        reason = (
            f"Article body reviewed; no berry/cultivar mention found (generic signal only: "
            f"{', '.join(matched_categories) or 'none'}, score {score}). Not relevant."
        )
    return RelevanceScreen(
        score=score, threshold=threshold, relevant=berry_identity_hit, confidence=CONFIDENT,
        berry_identity_hit=berry_identity_hit, reason=reason,
        likely_topics=tuple(dict.fromkeys(matched_categories)),
        matched_terms=tuple(dict.fromkeys(matched_terms)),
    )
