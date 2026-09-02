"""Provider-neutral berry-industry intelligence qualification.

Layered and deterministic. Answers: is this result plausibly useful
berry-industry competitive intelligence? Reasons are inspectable.
Does not use an LLM. Does not write Evidence or onboard Sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.coverage_assurance.classes import (
    BREEDER_GENETICS_OWNER,
    GROWER_MARKETER_ORGANIZATION,
    NURSERY_PROPAGATION_CATALOGUE,
    PBR_PVP_REGISTRY,
    TRADE_PRESS,
    UNIVERSITY_EXTENSION,
    source_class_of,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.recall_audit.classify import hostname, publisher_hosts

QUALIFY = "QUALIFY"
REJECT = "REJECT"

EDITORIAL_COMPETITOR = "competitor_moves"
EDITORIAL_VARIETY = "variety_genetics"
EDITORIAL_MARKET = "market_trade"
EDITORIAL_RESEARCH = "research_regulation"
EDITORIAL_OTHER = "other_industry"

SOURCE_GOV_AG = "government_agriculture"
SOURCE_GOV_UNRELATED = "government_unrelated"
SOURCE_UNIVERSITY = "university"
SOURCE_BREEDER = "breeder"
SOURCE_TRADE = "trade_press"
SOURCE_COMPANY = "company_newsroom"
SOURCE_GENERAL = "general_press"
SOURCE_UNKNOWN = "unknown"

# --- compiled once at import ---

_RASPBERRY_PI = re.compile(r"\braspberry\s*pi\b|\braspi\b|\bgpio\b", re.IGNORECASE)
_BLACKBERRY_DEVICE = re.compile(
    r"\b("
    r"blackberry\s+(limited|os|qnx|bbm|smartphone|device|stock|shares|equity)|"
    r"ip litigation|litigation insider|research in motion|\brim\b|qnx\b|bbm\b|"
    r"smartphone|nasdaq:\s*bb\b|nyse:\s*bb\b"
    r")\b",
    re.IGNORECASE,
)
_FRUIT_BLACKBERRY = re.compile(
    r"\b(caneberr\w*|cultivar|grower|harvest|fruit|primocane|nursery|seedless)\b",
    re.IGNORECASE,
)
_CANNABIS = re.compile(
    r"\b("
    r"cannabis|marijuana|marihuana|cannoptikum|high times|"
    r"kind green buds|royal queen seeds|seed bank|thc\b|cbd oil|hemp flower|"
    r"weed strain|marijuana strain"
    r")\b",
    re.IGNORECASE,
)
_RECIPE_FOOD = re.compile(
    r"\b("
    r"recipe|recipes|smoothie|smoothies|dessert|desserts|muffin|muffins|"
    r"pancake|pancakes|yogurt bowl|calories|calorie|superfood|"
    r"how to cook|what to cook|meal prep|salad idea|jam recipe|pie recipe|"
    r"nutrition facts|health benefits of eating|best berries for breakfast|"
    r"milkshake|bakery as creative|strawberry shortcake|beer menu|restaurant menu"
    r")\b",
    re.IGNORECASE,
)
_JOBS = re.compile(
    r"\b("
    r"we'?re hiring|now hiring|job posting|job opening|job description|"
    r"vacancies|vacancy|apply now|careers page"
    r")\b",
    re.IGNORECASE,
)
_JOB_TITLE_LEAD = re.compile(
    r"^\s*(director of|postdoc|phd candidate|phd position|hiring)\b",
    re.IGNORECASE,
)
_LIVESTOCK = re.compile(
    r"\b("
    r"livestock|cattle|sheep|poultry|swine|veterinary|"
    r"livestock genetic|protection of livestock"
    r")\b",
    re.IGNORECASE,
)
_OTHER_CROP = re.compile(
    r"\b("
    r"potato(?:es)?|grape(?:s)?|apple(?:s)?|avocado(?:s)?|onion(?:s)?|"
    r"maize|\bcorn\b|wheat|soybean(?:s)?|kiwi(?:fruit)?|durian|banana(?:s)?|"
    r"pear(?:s)?|fig(?:s)?|tree-?nut"
    r")\b",
    re.IGNORECASE,
)
_EVENT_NOISE = re.compile(
    r"\b(music festival|harvest music festival|pets of the week|pet of the week|grey's anatomy|school cafeterias?)\b",
    re.IGNORECASE,
)
_GARDENING_HOBBY = re.compile(
    r"\b("
    r"care & growing guide|growing guide|houseplant|backyard garden|"
    r"how to grow .{0,20}in pots"
    r")\b",
    re.IGNORECASE,
)
_PROMO = re.compile(
    r"\b(weekly ad|on sale|specials this week|club card|buy one get one|instacart deal)\b",
    re.IGNORECASE,
)
_UNRELATED_SCIENCE = re.compile(
    r"\b("
    r"medical device|pma\.cfm|biologics? patent|ozempic|"
    r"weight-?loss drug|unusual place names"
    r")\b",
    re.IGNORECASE,
)
_BERRY_CROP = re.compile(
    r"(?:"
    r"\b(?:"
    r"blueberr\w*|strawberr\w*|raspberr\w*|blackberr\w*|caneberr\w*|"
    r"highbush|arándano\w*|arandano\w*|mirtill\w*|fresa\w*|fragol\w*|"
    r"frambuesa\w*|lampon\w*|zarzamora\w*"
    r")\b"
    r"|蓝莓|草莓|覆盆子|黑莓|ブルーベリー|イチゴ|ラズベリー|ブラックベリー"
    r")",
    re.IGNORECASE,
)
_BERRY_COLLECTIVE = re.compile(r"\bberr(?:y|ies)\b", re.IGNORECASE)
_INDUSTRY = re.compile(
    r"(?:"
    r"\b(?:"
    r"cultivar|breeder|breeding|genetics|nursery|pbr|"
    r"plant breeders|plant patent|plant variety|cpvo|"
    r"licensing|variety license|grower|growers|"
    r"acreage|hectares|export|exports|import|imports|"
    r"acquisition|merger|field trial|trial results|"
    r"crop condition|orchard|production|"
    r"new variety|variety launch|variety strategy|varieties|"
    r"seedless|crispr|gene-?edit(?:ed|ing)?|genome edit|"
    r"primocane|floricane|commercial deployment|commercial launch|"
    r"partnership|planting|harvest|pricing|spot price|"
    r"market report|supply|frost|drought|weather|"
    r"trade|tariff|university|extension|research station|"
    r"producing|yield|brix|volumes?|bumper|heatwave|"
    r"market access|branding"
    r")\b"
    r"|价格|出口|进口|品种|种植|育种|ブランド|輸出|産地"
    r")",
    re.IGNORECASE,
)
_VARIETY_TERMS = re.compile(
    r"\b("
    r"cultivar|variety|varieties|breeder|breeding|genetics|pbr|"
    r"plant patent|plant breeders|primocane|seedless|crispr|gene-?edit"
    r")\b",
    re.IGNORECASE,
)
_COMPETITOR_TERMS = re.compile(
    r"\b(acquisition|merger|partnership|joint venture|unveils|launches|opens|expansion)\b",
    re.IGNORECASE,
)
_MARKET_TERMS = re.compile(
    r"\b("
    r"acreage|hectares|export|exports|import|imports|harvest|"
    r"pricing|price|supply|production|trade|tariff|frost|drought|"
    r"crop condition|weather"
    r")\b",
    re.IGNORECASE,
)
_RESEARCH_TERMS = re.compile(
    r"\b(university|extension|research station|field trial|regulation|pbr|cpvo)\b",
    re.IGNORECASE,
)
_FOOD_RECALL = re.compile(r"\b(food recall|outbreak|pesticide residue|berry recall)\b", re.IGNORECASE)

_UNRELATED_GOV_SUFFIXES = (
    "fda.gov",
    "accessdata.fda.gov",
    "jobcorps.gov",
    "cdc.gov",
)
_AG_GOV_MARKERS = (
    "usda.gov",
    "agriculture.gov",
    "dalrrd.gov.za",
    "nda.gov.za",
    "plantvarieties.eu",
    "cpvo.europa.eu",
    "inspection.gc.ca",
    "defra.gov.uk",
)


@dataclass(frozen=True)
class QualificationIndex:
    """Compiled once per pulse/bake-off run. Do not rebuild per hit."""

    company_re: re.Pattern[str] | None = None
    variety_re: re.Pattern[str] | None = None
    host_class: dict[str, str] = field(default_factory=dict)

    @classmethod
    def compile(
        cls,
        *,
        company_names: Iterable[str] = (),
        variety_names: Iterable[str] = (),
        sources: Iterable[dict[str, Any]] = (),
        universe_entries: Iterable[dict[str, Any]] = (),
    ) -> "QualificationIndex":
        company_re = _name_regex(company_names)
        variety_re = _name_regex(variety_names)
        host_class: dict[str, str] = {}
        for row in universe_entries:
            host = hostname(row.get("hostname") or row.get("domain"))
            klass = str(row.get("source_class") or "")
            if host and klass:
                host_class[host] = klass
        for source in sources:
            klass = source_class_of(source)
            for host in publisher_hosts(source):
                host_class.setdefault(host, klass)
        return cls(company_re=company_re, variety_re=variety_re, host_class=host_class)


def _name_regex(names: Iterable[str]) -> re.Pattern[str] | None:
    tokens = sorted({str(name).strip() for name in names if len(str(name or "").strip()) >= 5}, key=len, reverse=True)
    if not tokens:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(token) for token in tokens) + r")\b", re.IGNORECASE)


def _named(pattern: re.Pattern[str] | None, text: str) -> str | None:
    if pattern is None:
        return None
    match = pattern.search(text)
    return match.group(0) if match else None


def source_context_of(host: str, *, host_class: dict[str, str]) -> str:
    folded = (host or "").lower().removeprefix("www.")
    if any(folded == suffix or folded.endswith("." + suffix) for suffix in _UNRELATED_GOV_SUFFIXES):
        return SOURCE_GOV_UNRELATED
    if any(folded == marker or folded.endswith("." + marker) or marker in folded for marker in _AG_GOV_MARKERS):
        return SOURCE_GOV_AG
    klass = host_class.get(folded, "")
    if klass in {BREEDER_GENETICS_OWNER, NURSERY_PROPAGATION_CATALOGUE}:
        return SOURCE_BREEDER
    if klass == TRADE_PRESS:
        return SOURCE_TRADE
    if klass in {UNIVERSITY_EXTENSION} or folded.endswith(".edu") or ".ac." in folded:
        return SOURCE_UNIVERSITY
    if klass == GROWER_MARKETER_ORGANIZATION:
        return SOURCE_COMPANY
    if klass == PBR_PVP_REGISTRY:
        return SOURCE_GOV_AG
    if klass:
        return SOURCE_GENERAL
    return SOURCE_UNKNOWN


def _crop_identity(text: str) -> str | None:
    match = _BERRY_CROP.search(text)
    if match:
        return match.group(0).lower()
    if _BERRY_COLLECTIVE.search(text):
        return "berry"
    return None


def _hard_exclusion(text: str, hit: DiscoveryHit) -> str | None:
    if _RASPBERRY_PI.search(text):
        return "Raspberry Pi ambiguity"
    if _CANNABIS.search(text):
        return "cannabis cultivar/product context"
    if _BLACKBERRY_DEVICE.search(text) and not _FRUIT_BLACKBERRY.search(text):
        return "BlackBerry device/company ambiguity"
    if _RECIPE_FOOD.search(text):
        return "recipe/foodservice noise"
    if _JOBS.search(text) or _JOB_TITLE_LEAD.search(hit.title or ""):
        return "jobs/recruiting"
    if _LIVESTOCK.search(text):
        return "livestock/veterinary"
    if _EVENT_NOISE.search(text):
        return "consumer/lifestyle event noise"
    if _UNRELATED_SCIENCE.search(text):
        return "unrelated scientific usage"
    if _GARDENING_HOBBY.search(text):
        return "gardening/hobby"
    if _PROMO.search(text) and not _INDUSTRY.search(text):
        return "generic retail promotion"
    other = _OTHER_CROP.search(text)
    if other and not _BERRY_CROP.search(text):
        return "unrelated produce"
    return None


def _editorial_topic(text: str) -> str | None:
    variety = bool(_VARIETY_TERMS.search(text))
    competitor = bool(_COMPETITOR_TERMS.search(text))
    market = bool(_MARKET_TERMS.search(text))
    research = bool(_RESEARCH_TERMS.search(text))
    if variety:
        return EDITORIAL_VARIETY
    if competitor:
        return EDITORIAL_COMPETITOR
    if market:
        return EDITORIAL_MARKET
    if research:
        return EDITORIAL_RESEARCH
    return None


def qualify_result(
    hit: DiscoveryHit,
    *,
    index: QualificationIndex | None = None,
    company_names: Iterable[str] = (),
    variety_names: Iterable[str] = (),
) -> DiscoveryHit:
    """Mutate hit with QUALIFY/REJECT, reasons, editorial topic, source context."""
    compiled = index or QualificationIndex.compile(
        company_names=company_names,
        variety_names=variety_names,
    )
    text = f"{hit.title} {hit.snippet}"
    host = hit.source_domain or hostname(hit.origin_publisher_url or hit.url)
    context = source_context_of(host, host_class=compiled.host_class)
    hit.source_context = context

    exclusion = _hard_exclusion(text, hit)
    if exclusion:
        return _reject(hit, exclusion)
    if context == SOURCE_GOV_UNRELATED and not (_BERRY_CROP.search(text) and _FOOD_RECALL.search(text)):
        return _reject(hit, "unrelated .gov / non-agricultural authority page")

    crop = _crop_identity(text)
    named_company = _named(compiled.company_re, text)
    named_variety = _named(compiled.variety_re, text)
    industry = bool(_INDUSTRY.search(text))
    reasons: list[str] = []
    if crop and crop != "berry":
        reasons.append(f"explicit {crop} crop")
    elif crop == "berry":
        reasons.append("explicit berry-industry collective")
    if named_company:
        reasons.append(f"named company {named_company}")
    if named_variety:
        reasons.append(f"named cultivar {named_variety}")
    if industry:
        reasons.append("berry-industry production/trade/genetics terms")
    if context in {SOURCE_TRADE, SOURCE_BREEDER, SOURCE_GOV_AG, SOURCE_UNIVERSITY} and crop:
        reasons.append(f"{context.replace('_', ' ')} context")

    if not crop and not named_company and not named_variety:
        return _reject(hit, "no berry-crop identity in title/snippet")
    if not industry and not named_company and not named_variety:
        if context in {SOURCE_TRADE, SOURCE_BREEDER, SOURCE_GOV_AG} and crop and crop != "berry":
            reasons.append("source/context modifier with named berry crop")
            return _qualify(hit, reasons, text)
        return _reject(hit, "berry mention without industry relevance")

    if crop == "berry" and not industry and not named_company:
        return _reject(hit, "collective berry word without industry context")

    return _qualify(hit, reasons, text)


def qualify_hit(
    hit: DiscoveryHit,
    *,
    company_names: Iterable[str] = (),
    variety_names: Iterable[str] = (),
    index: QualificationIndex | None = None,
    sources: Iterable[dict[str, Any]] = (),
) -> DiscoveryHit:
    """Public adapter. Same signature as V0 plus optional compiled index."""
    compiled = index
    if compiled is None and sources:
        compiled = QualificationIndex.compile(
            company_names=company_names,
            variety_names=variety_names,
            sources=sources,
        )
    return qualify_result(
        hit,
        index=compiled,
        company_names=company_names,
        variety_names=variety_names,
    )


def _reject(hit: DiscoveryHit, reason: str) -> DiscoveryHit:
    hit.qualifying = False
    hit.qualify_reasons = [reason]
    hit.qualify_reason = f"{REJECT}: {reason}"
    hit.editorial_topic = None
    return hit


def _qualify(hit: DiscoveryHit, reasons: list[str], text: str) -> DiscoveryHit:
    if not reasons:
        reasons = ["berry-industry competitive intelligence"]
    hit.qualifying = True
    hit.qualify_reasons = reasons
    hit.qualify_reason = f"{QUALIFY}: " + "; ".join(reasons)
    hit.editorial_topic = _editorial_topic(text)
    return hit


def rejection_reason_counts(hits: Iterable[DiscoveryHit]) -> dict[str, int]:
    """Tally first REJECT reason. Compile-friendly; no per-item corpus load."""
    counts: dict[str, int] = {}
    for hit in hits:
        if hit.qualifying:
            continue
        if hit.qualify_reasons:
            reason = hit.qualify_reasons[0]
        elif hit.qualify_reason.startswith(f"{REJECT}: "):
            reason = hit.qualify_reason[len(REJECT) + 2 :]
        else:
            reason = hit.qualify_reason or "unspecified"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def editorial_topic_counts(hits: Iterable[DiscoveryHit]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        if not hit.qualifying:
            continue
        key = hit.editorial_topic or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
