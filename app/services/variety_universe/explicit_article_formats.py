"""Bounded quoted cultivar declarations in an explicitly selected paragraph.

No acquisition, title-case guessing, publication-tag crop assignment, or writes.
Paragraph context supplies a crop only when it names exactly one supported crop.
"""
import re

_CROPS = {
    "blueberry": "berry-blueberry", "blueberries": "berry-blueberry",
    "strawberry": "berry-strawberry", "strawberries": "berry-strawberry",
    "raspberry": "berry-raspberry", "raspberries": "berry-raspberry",
    "blackberry": "berry-blackberry", "blackberries": "berry-blackberry",
}
_CROP = r"blueberry|strawberry|raspberry|blackberry"
_CROP_WORDS = re.compile(r"\b(" + "|".join(_CROPS) + r")\b", re.IGNORECASE)
_LICENSE = re.compile(
    r"\blicen[cs]es?\b[^.!?\n:]{0,80}\bvarieties\s*:\s*", re.IGNORECASE)
_ATTRIBUTION = re.compile(
    r"\s+from\b[^.!?\n:;'‘’\"“”]{1,240},\s*(?:and\s+)?", re.IGNORECASE)


def paragraph_crop_ids(text):
    return sorted({_CROPS[m.group(1).casefold()] for m in _CROP_WORDS.finditer(text)})


def explicit_article_formats(text, *, name_token):
    """Return source assertions of names, never roles/traits/rights or aliases."""
    leads, excluded = [], []
    quoted = rf"(?:'{name_token}'|\"{name_token}\"|‘{name_token}’|“{name_token}”)"
    item = re.compile(quoted)
    separator = r"\s*(?:,\s*(?:and\s+)?|\band\s+)"
    names = rf"(?P<names>{quoted}(?:{separator}{quoted}){{0,63}})(?!{separator}['‘\"“])"
    reverse = re.compile(
        rf"(?:^\s*|(?<=[.!?])\s+){names}\s+(?i:are|were)\s+"
        rf"(?:(?i:(?:(?:the|our)\s+)?(?:(?:first|new|two|three|four)\s+){{0,2}})"
        rf"|(?i:some\s+of\s+(?:the|our)\s+)(?:(?!(?i:{_CROP})\b)[A-Z][\w-]*\s+){{0,3}})"
        rf"(?P<crop>(?i:{_CROP}))?\s*(?i:varieties|cultivars)\b")
    crop_ids = paragraph_crop_ids(text)

    def add(match, kind, explicit_crop=""):
        crop = _CROPS.get(explicit_crop.casefold()) if explicit_crop else (
            crop_ids[0] if len(crop_ids) == 1 else "")
        if not crop:
            excluded.append({"name": match.group("names"), "reason": "berry_not_established"})
            return
        for token in item.finditer(match.group("names")):
            leads.append({"name": token.group(0)[1:-1], "berry_id": crop,
                          "kind": kind, "context": match.group(0).strip()[:240]})

    for match in reverse.finditer(text):
        add(match, "quoted_article_variety_list", match.group("crop") or "")

    # Licensing declarations require an actual varieties colon, followed by a
    # quoted name list. Only another quoted list after a bounded 'from ...,'
    # attribution is eligible; brands/traits quoted elsewhere are not names.
    for declaration in _LICENSE.finditer(text):
        prefix = re.split(r"[.!?;\n]", text[:declaration.start()])[-1]
        if re.search(r"\b(?:no|not|without|never)\b", prefix, re.IGNORECASE):
            continue
        remaining = text[declaration.end():]
        for _ in range(8):
            group = re.match(names, remaining)
            if not group:
                break
            add(group, "quoted_article_license_list")
            rest = remaining[group.end():]
            attribution = _ATTRIBUTION.match(rest)
            if not attribution:
                break
            remaining = rest[attribution.end():]
    return leads, excluded
