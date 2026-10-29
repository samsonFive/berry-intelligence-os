"""Disambiguate software-company news without banning fruit or agtech terms."""
import re

_BLACKBERRY = re.compile(r"\bblackberry\b", re.IGNORECASE)
_BRAND_CASE = re.compile(r"\bBlackBerry\b")
_SOFTWARE = re.compile(
    r"\b(qnx|bbm|research in motion|smartphones?|cybersecurity|cyber[ -]security|"
    r"endpoint security|mobile devices?|enterprise software|software[ -]defined|"
    r"blackberry\s+(limited|os|passport|keyone|key2|z10|z30|bold|curve|stock|shares|equity))\b"
    r"|\b(?:NYSE|NASDAQ)\s*:\s*BB\b|\$BB\b",
    re.IGNORECASE,
)
_CORPORATE = re.compile(
    r"\b(licensing|licen[cs]es?|sovereignty|shareholders?|earnings|stock|investors?|patent portfolio)\b",
    re.IGNORECASE,
)
_AGRICULTURE = re.compile(
    r"\b(blueberr\w*|strawberr\w*|raspberr\w*|cranberr\w*|blackberries|berries|"
    r"fruit\w*|agricultur\w*|agronom\w*|horticultur\w*|cultivars?|breeding|breeders?|"
    r"growers?|nurser(?:y|ies)|orchards?|farms?|farming|harvest\w*|crops?|"
    r"primocane|caneberr\w*|seedless|plant\s+patents?)\b",
    re.IGNORECASE,
)


def has_agriculture_context(text: str) -> bool:
    return bool(_AGRICULTURE.search(text))


def blackberry_company_noise(text: str) -> bool:
    """Require a company cue; capitalization or 'licensing' alone is not enough.

    BlackBerry's distinctive brand spelling plus corporate context catches
    thin RSS headlines. Explicit crop context keeps mixed agtech available.
    No classification here approves evidence or deletes a captured record.
    """
    return bool(_BLACKBERRY.search(text) and not has_agriculture_context(text) and (
        _SOFTWARE.search(text) or (_BRAND_CASE.search(text) and _CORPORATE.search(text))))
