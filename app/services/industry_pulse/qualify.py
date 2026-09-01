"""Deterministic Industry Pulse qualification.

Berry identity is necessary but not sufficient. Recipes, lifestyle fluff,
generic nutrition, supermarket ads, and BlackBerry-device litigation are
rejected even when a berry word appears. Do not overfit to a frozen URL list.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.services.industry_pulse.models import DiscoveryHit
from app.services.relevance_screen import TIER_IRRELEVANT, screen_relevance

_REJECT = re.compile(
    r"\b("
    r"recipe|recipes|smoothie|smoothies|dessert|desserts|muffin|muffins|"
    r"pancake|pancakes|yogurt bowl|calories|calorie|superfood|antioxidant smoothie|"
    r"how to cook|what to cook|meal prep|salad idea|jam recipe|pie recipe|"
    r"nutrition facts|health benefits of eating|best berries for breakfast|"
    r"milkshake|bakery as creative|smartphone|bbm\b|qnx\b|"
    r"school cafeteria|pets of the week|pet of the week|music festival|"
    r"strawberry shortcake|grey's anatomy|plant vegetables|fast-growing picks"
    r")\b",
    re.IGNORECASE,
)
_DEVICE_BLACKBERRY = re.compile(
    r"\b(ip litigation|patent innovation|litigation insider|smartphone|rim\b)\b",
    re.IGNORECASE,
)
_PROMO = re.compile(
    r"\b(weekly ad|on sale|specials this week|club card|buy one get one|instacart deal)\b",
    re.IGNORECASE,
)
_STRONG_INDUSTRY = re.compile(
    r"\b("
    r"cultivar|breeder|breeding|genetics|nursery|pbr|"
    r"plant breeders|plant patent|cpvo|license|licensing|grower|"
    r"acreage|hectares|export|exports|import|imports|"
    r"acquisition|merger|field trial|"
    r"crop condition|orchard|production orchard|"
    r"new variety|variety launch|variety strategy|"
    r"seedless|crispr|gene-edit|gene edited|genome edit"
    r")\b",
    re.IGNORECASE,
)
_CROP_HARVEST = re.compile(
    r"\b("
    r"(?:blueberr\w*|strawberr\w*|raspberr\w*|blackberr\w*|caneberr\w*|berr(?:y|ies)|"
    r"ar[aá]ndano\w*|fresa\w*|frambuesa\w*|zarzamora\w*)"
    r".{0,40}harvest|"
    r"harvest.{0,40}"
    r"(?:blueberr\w*|strawberr\w*|raspberr\w*|blackberr\w*|caneberr\w*|berr(?:y|ies)|"
    r"ar[aá]ndano\w*|fresa\w*|frambuesa\w*|zarzamora\w*)"
    r")\b",
    re.IGNORECASE,
)
_RESEARCH = re.compile(r"\b(university|extension|research station|field trial)\b", re.IGNORECASE)
_WEATHER = re.compile(r"\b(frost|drought|crop condition)\b", re.IGNORECASE)


def _title_snippet(hit: DiscoveryHit) -> str:
    return f"{hit.title} {hit.snippet}"


def _named_in(text: str, names: Iterable[str]) -> str | None:
    folded = text
    for name in names:
        token = str(name or "").strip()
        if len(token) < 5:
            continue
        if re.search(rf"\b{re.escape(token)}\b", folded, flags=re.IGNORECASE):
            return token
    return None


def qualify_hit(
    hit: DiscoveryHit,
    *,
    company_names: Iterable[str] = (),
    variety_names: Iterable[str] = (),
) -> DiscoveryHit:
    text = _title_snippet(hit)
    if _REJECT.search(text):
        hit.qualifying = False
        hit.qualify_reason = "rejected: consumer recipe/lifestyle/nutrition"
        return hit
    if hit.berry == "blackberry" and _DEVICE_BLACKBERRY.search(text) and not _STRONG_INDUSTRY.search(text):
        hit.qualifying = False
        hit.qualify_reason = "rejected: BlackBerry-device / IP-litigation noise"
        return hit
    screen = screen_relevance(title=hit.title, description=hit.snippet)
    if screen.tier == TIER_IRRELEVANT and not screen.berry_identity_hit:
        hit.qualifying = False
        hit.qualify_reason = "rejected: no berry industry identity"
        return hit
    named_company = _named_in(text, company_names)
    named_variety = _named_in(text, variety_names)
    strong = bool(_STRONG_INDUSTRY.search(text))
    crop_harvest = bool(_CROP_HARVEST.search(text))
    research = bool(_RESEARCH.search(text))
    weather = bool(_WEATHER.search(text))
    industry = strong or (crop_harvest and strong) or research or weather
    promo = bool(_PROMO.search(text))
    if promo and not (named_company or strong):
        hit.qualifying = False
        hit.qualify_reason = "rejected: generic supermarket promotion"
        return hit
    if named_company or (named_variety and (strong or research)) or strong or research or weather:
        hit.qualifying = True
        if named_company:
            hit.qualify_reason = f"qualifying: named company {named_company!r}"
        elif named_variety:
            hit.qualify_reason = f"qualifying: named cultivar {named_variety!r}"
        else:
            hit.qualify_reason = "qualifying: berry market/production/trade/IP/research terms"
        return hit
    if crop_harvest and not strong:
        hit.qualifying = False
        hit.qualify_reason = "rejected: harvest mention without industry/company signal"
        return hit
    if screen.berry_identity_hit and screen.relevant:
        hit.qualifying = False
        hit.qualify_reason = "rejected: berry mention without industry relevance"
        return hit
    hit.qualifying = False
    hit.qualify_reason = "rejected: not berry-industry relevant"
    return hit
