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
Stage A result, once the body has been acquired anyway): a bare "does a
berry species appear anywhere in the text" gate was found, from a real
refresh's own output, to be too permissive -- a passing one-sentence
comparison ("It doesn't work that way with strawberries, but it does
with raspberries" in an article fundamentally about pear-orchard solar
panels) was enough to pass. The real discriminator, checked against the
same real dataset: every genuine false positive found had the berry
mention confined to exactly one paragraph, while every genuinely
berry-relevant article had it recur across multiple paragraphs (or the
title/description, or a company name). So Stage B's DIRECT gate now
requires the species to appear in >=2 distinct paragraphs (paragraph
recurrence as a proxy for "the berry is a subject of this piece", not
"the berry was mentioned once") -- title/description-level mentions and
company-name hits remain a one-mention-is-enough DIRECT gate, since
those are already the article's declared subject, not incidental text
buried in the body. A single-paragraph mention combined with an
explicit adjacent-topic signal (agtech, trade/tariff policy, labor,
weather/climate -- the categories the product itself calls out as
worth retaining) becomes ADJACENT: created for review, but never
presented as high-confidence berry relevance. Still no AI, no score
threshold for the gate itself.

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
        (
            "blueberry", "blueberries", "strawberry", "strawberries", "raspberry", "raspberries",
            "blackberry", "blackberries", "highbush", "southern highbush",
            # Non-English species names -- this category previously had zero
            # non-English coverage of any kind, discovered when a real,
            # live-verified Italian-language source (Nova Siri Genetics,
            # onboarded for the Strawberry Vertical V1 depth mission,
            # 2026-08-20) was systematically screened irrelevant on every
            # item despite genuinely covering strawberry breeding, because
            # "fragola"/"fragole" (Italian for strawberry) matched nothing
            # here. A large share of this dataset's real sources are
            # Spanish-language (Huelva/Freshuelva) or Italian-language
            # (Nova Siri Genetics, CIV) -- added symmetrically across all
            # four berries rather than patching strawberry alone.
            "fresa", "fresas", "fragola", "fragole",
            "arándano", "arándanos", "arandano", "arandanos", "mirtillo", "mirtilli",
            "frambuesa", "frambuesas", "lampone", "lamponi",
            "mora", "moras",
            # Italian "more" (blackberries, plural) deliberately excluded --
            # it collides with the extremely common English word "more"
            # even under word-boundary matching (_word_present), which
            # would false-positive on ordinary English text constantly.
            # Known berry-industry trade association names, not generic
            # species words -- found missing a real article that discusses
            # "the Mexican berry industry" throughout via Aneberries (the
            # Mexican berry export association) without repeating a named
            # species across multiple paragraphs; "Aneberries" is a single
            # fused word so it doesn't match the multi-word company-name
            # regex below either. Treated exactly like a species name
            # since it's an unambiguous, always-berry-specific term, same
            # category the product asks for: "known company/entity".
            "aneberries", "ushbc", "narba",
        ),
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
RELEVANCE_SCREEN_VERSION = "relevance-screen-v3"

CONFIDENT = "confident"
BORDERLINE = "borderline"

# Direct berry relevance vs. a genuinely different but worth-retaining
# story (agtech, trade/tariff policy, labor, weather/climate) vs. neither.
# DIRECT and ADJACENT are both `relevant=True` (both get acquired and
# created as drafts); the distinction is carried in `tier` so a caller
# (the review queue, a ranking) can put direct berry intelligence ahead
# of adjacent stories by default, never mixed in undifferentiated.
TIER_DIRECT = "direct"
TIER_ADJACENT = "adjacent"
TIER_IRRELEVANT = "irrelevant"

# Not scored toward CATEGORIES -- used only to decide whether a
# single-paragraph, non-recurring berry mention is worth retaining as an
# explicitly-labeled ADJACENT story rather than dropped outright. Kept
# deliberately narrow and named for the exact categories the product
# calls out (agtech, trade, labor, weather), not a general keyword net.
ADJACENT_TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "agtech": ("solar panel", "solar panels", "agrivoltaic", "agrivoltaics", "robot", "robotic",
               "automation", "automated", "precision agriculture", "drone", "sensor"),
    "trade_policy": ("tariff", "tariffs", "antidumping", "anti-dumping", "trade agreement",
                      "trade war", "export ban", "import ban", "sanctions", "quota"),
    "labor": ("labor shortage", "farmworker", "farmworkers", "guest worker", "h-2a", "visa program",
              "workforce shortage", "minimum wage"),
    "weather_climate": ("frost", "drought", "heatwave", "heat wave", "climate change", "hail",
                         "flooding", "wildfire", "extreme weather"),
}


def _adjacent_topic_hit(text: str) -> str | None:
    for topic, terms in ADJACENT_TOPIC_TERMS.items():
        if any(term in text for term in terms):
            return topic
    return None


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
    tier: str | None = None  # "direct" | "adjacent" | "irrelevant" | None (Stage A borderline, pending Stage B)
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
            "tier": self.tier,
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
                tier=TIER_DIRECT,
            )
        if score == 0:
            return RelevanceScreen(
                score=0, threshold=threshold, relevant=False, confidence=CONFIDENT,
                berry_identity_hit=False,
                reason="No berry/CI keyword signals matched title or description at all.",
                likely_topics=(), matched_terms=(),
                tier=TIER_IRRELEVANT,
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
            tier=None,
        )

    # Stage B: full text including the real article body. Berry identity
    # is still the gate -- no score threshold, deliberately, per this
    # module's docstring (a generic-agriculture score alone must never
    # carry an onion/apple/fig/banana/tree-nut/durian story through) --
    # but a bare species mention is no longer sufficient on its own: it
    # must recur across >=2 distinct paragraphs (article_acquisition.py's
    # ArticleBody.full_text joins paragraphs with "\n\n"), the same
    # discriminator a real false positive/true positive comparison found
    # cleanly separates "the berry is a subject of this piece" from "the
    # berry was named once in passing".
    original_full_text = f"{original_metadata_text} {(body or '')[:8000]}"
    full_text = f"{metadata_text} {(body or '')[:8000]}".casefold()
    score, matched_categories, matched_terms, species_hit = _match(full_text)
    company_name = _named_berry_company(original_full_text)
    if company_name and not species_hit:
        matched_categories.append("berry_company_name")
        matched_terms.append(company_name)

    species_paragraph_count = 0
    total_paragraphs = 0
    if species_hit:
        body_paragraphs = [p for p in (body or "")[:8000].split("\n\n") if p.strip()]
        total_paragraphs = len(body_paragraphs)
        species_terms = next(c.terms for c in CATEGORIES if c.name == "berry_identity")
        species_paragraph_count = sum(
            1 for paragraph in body_paragraphs
            if any(_word_present(paragraph.casefold(), term) for term in species_terms)
        )

    # Recurrence across >=2 paragraphs is the discriminator for longer
    # articles, but a short article (<=2 total paragraphs) has no sea of
    # unrelated paragraphs for a false positive to hide in -- a single
    # hit there is already the whole point of the piece, not a passing
    # comparison. Every real false positive this screen was built against
    # (pear/solar, prune/banana, tomato-trade, Ohio-climate, Thai-apples)
    # ran 9+ total paragraphs; the genuine short-blurb case this
    # exception protects never does.
    short_article = 0 < total_paragraphs <= 2
    recurs = species_paragraph_count >= 2 or (short_article and species_paragraph_count >= 1)
    berry_identity_hit = bool(company_name) or recurs
    if berry_identity_hit:
        reason = (
            f"Berry company/brand name ({company_name!r}) found in the article."
            if company_name and not recurs
            else f"Berry/cultivar named in {species_paragraph_count} of {total_paragraphs} paragraphs of the article body ({', '.join(matched_categories)}, score {score})."
        )
        return RelevanceScreen(
            score=score, threshold=threshold, relevant=True, confidence=CONFIDENT,
            berry_identity_hit=True, reason=reason,
            likely_topics=tuple(dict.fromkeys(matched_categories)),
            matched_terms=tuple(dict.fromkeys(matched_terms)),
            tier=TIER_DIRECT,
        )

    if species_hit:
        adjacent_topic = _adjacent_topic_hit(full_text)
        if adjacent_topic:
            return RelevanceScreen(
                score=score, threshold=threshold, relevant=True, confidence=CONFIDENT,
                berry_identity_hit=False,
                reason=(
                    f"Berry species named once in passing (not a recurring subject of the piece), but the "
                    f"article is a genuine {adjacent_topic.replace('_', ' ')} story -- retained as adjacent, "
                    "not presented as direct berry intelligence."
                ),
                likely_topics=tuple(dict.fromkeys([*matched_categories, adjacent_topic])),
                matched_terms=tuple(dict.fromkeys(matched_terms)),
                tier=TIER_ADJACENT,
            )
        return RelevanceScreen(
            score=score, threshold=threshold, relevant=False, confidence=CONFIDENT,
            berry_identity_hit=False,
            reason=(
                "Berry species named exactly once in the article body, with no recurrence and no adjacent-topic "
                "signal -- read as an incidental mention (e.g. a comparison to another crop), not the article's subject."
            ),
            likely_topics=tuple(dict.fromkeys(matched_categories)),
            matched_terms=tuple(dict.fromkeys(matched_terms)),
            tier=TIER_IRRELEVANT,
        )

    reason = (
        f"Article body reviewed; no berry/cultivar mention found (generic signal only: "
        f"{', '.join(matched_categories) or 'none'}, score {score}). Not relevant."
    )
    return RelevanceScreen(
        score=score, threshold=threshold, relevant=False, confidence=CONFIDENT,
        berry_identity_hit=False, reason=reason,
        likely_topics=tuple(dict.fromkeys(matched_categories)),
        matched_terms=tuple(dict.fromkeys(matched_terms)),
        tier=TIER_IRRELEVANT,
    )
