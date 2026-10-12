"""Bounded quoted cultivar declarations in an explicitly selected paragraph.

No acquisition, title-case guessing, publication-tag crop assignment, or writes.
Paragraph context supplies a crop only when it names exactly one supported crop.
Anchored profile fields can also use an explicit source title or nearby crop heading.
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
_PROFILE_HEADING = re.compile(
    rf"\s*(?i:(?:(?:southern|northern)\s+highbush\s+|rabbiteye\s+|"
    rf"red\s+|black\s+|yellow\s+)?(?P<crop>{_CROP})\s+(?:variety|cultivar))\s*")


def paragraph_crop_ids(text):
    return sorted({_CROPS[m.group(1).casefold()] for m in _CROP_WORDS.finditer(text)})


def profile_heading_crop_ids(text):
    """A short crop/profile heading, never an arbitrary preceding paragraph."""
    heading = _PROFILE_HEADING.fullmatch(text)
    return [_CROPS[heading.group("crop").casefold()]] if heading else []


def explicit_article_formats(text, *, name_token, profile_crop_ids=()):
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

    # Original release articles can name a single cultivar in a sentence,
    # rather than a quoted portfolio list. Keep the assertion bounded to
    # variety/cultivar naming wording and one crop in this paragraph. Unicode
    # hyphens remain in the source name; no code/brand alias is inferred.
    single_token = name_token.replace(r"\-", r"\-\u2010\u2011")
    profile_name = rf"(?:'{single_token}'|\"{single_token}\"|‘{single_token}’|“{single_token}”|{single_token})"
    profile_code = r"[A-Za-z][A-Za-z0-9. \-]{0,59}"
    field = re.compile(
        rf"\s*(?:(?P<crop>(?i:{_CROP}))\s+)?(?i:variety|cultivar)\s+(?i:name)\s*:\s*"
        rf"(?P<name>{profile_name})(?:\s*\(\s*(?:(?i:selection\s+code)\s+"
        rf"(?P<code>{profile_code})|(?P<quoted_code>'{profile_code}'|\"{profile_code}\"|‘{profile_code}’|“{profile_code}”))\s*\))?\s*\.?\s*")
    for line in text.splitlines():
        match = field.fullmatch(line)
        if not match:
            continue
        explicit_crop = match.group("crop")
        crops = [_CROPS[explicit_crop.casefold()]] if explicit_crop else (crop_ids or list(profile_crop_ids))
        if len(crops) != 1:
            excluded.append({"name": match.group("name"), "reason": "berry_not_established"})
            continue
        code = (match.group("code") or match.group("quoted_code") or "").strip("'\"‘’“” ")
        if code and not re.search(r"\d", code):
            continue
        leads.append({"name": match.group("name").strip("'\"‘’“”"), "berry_id": crops[0],
                      "breeder_code": code, "kind": "article_cultivar_name_field",
                      "context": line.strip()[:240]})

    named_release = re.compile(
        rf"(?i:\b(?:name\s+of\s+(?:(?:the|our|this)\s+)?(?:new\s+)?"
        rf"(?:{_CROP}\s+)?(?:variety|cultivar)\s*[:;,]\s*(?:it\s+)?"
        rf"(?:will\s+be\s+|is\s+)?|(?:(?:the|our|this)\s+)?(?:new\s+)?"
        rf"(?:{_CROP})\s+(?:variety|cultivar)\s+(?:is\s+|will\s+be\s+))"
        rf"(?:called|named)\s+)(?P<name>{single_token})")
    for match in named_release.finditer(text):
        prefix = re.split(r"[.!?\n]", text[:match.start()])[-1]
        if re.search(r"\b(?:no|not|never|without|could|might|may|perhaps)\b", prefix, re.IGNORECASE):
            continue
        if len(crop_ids) != 1:
            excluded.append({"name": match.group("name"), "reason": "berry_not_established"})
            continue
        leads.append({"name": match.group("name"), "berry_id": crop_ids[0],
                      "kind": "article_named_release", "context": match.group(0).strip()[:240]})

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
