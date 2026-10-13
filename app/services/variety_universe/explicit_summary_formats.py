"""Bounded, explicit crop/name declarations in stored summaries only.

No body hydration, HTML scraping, provider calls, identity decisions or writes.
Table headings and each row's crop establish scope; publication-wide crop tags
are never a substitute. Translated declarations require an explicit crop.
"""
import re


_CROPS = {
    "blueberry": "berry-blueberry", "strawberry": "berry-strawberry",
    "raspberry": "berry-raspberry", "red raspberry": "berry-raspberry",
    "black raspberry": "berry-raspberry", "yellow raspberry": "berry-raspberry",
    "purple raspberry": "berry-raspberry", "blackberry": "berry-blackberry",
    "arándano": "berry-blueberry", "arándanos": "berry-blueberry",
    "fresa": "berry-strawberry", "fresas": "berry-strawberry",
    "frutilla": "berry-strawberry", "frutillas": "berry-strawberry",
    "frambuesa": "berry-raspberry", "frambuesas": "berry-raspberry",
    "zarzamora": "berry-blackberry", "zarzamoras": "berry-blackberry",
    "malina": "berry-raspberry", "maliny": "berry-raspberry",
    "malina czerwona": "berry-raspberry", "malina czarna": "berry-raspberry",
    "malina żółta": "berry-raspberry", "malina purpurowa": "berry-raspberry",
    "jeżyna": "berry-blackberry", "jeżyny": "berry-blackberry",
    "truskawka": "berry-strawberry", "truskawki": "berry-strawberry",
    "borówka": "berry-blueberry", "borówki": "berry-blueberry",
}
_HEADINGS = {
    "crop": "crop", "berry": "crop", "uprawa": "crop", "cultivo": "crop",
    "name": "name", "cultivar": "name", "variety": "name",
    "odmiana": "name", "nazwa": "name", "variedad": "name", "nombre": "name",
    "code": "code", "selection code": "code", "breeder code": "code",
    "kod": "code", "código": "code",
}
_SEPARATOR = re.compile(r":?-{3,}:?")
_CODE = re.compile(r"(?=.*\d)[A-Za-z][A-Za-z0-9. \-]{0,59}")
_DECLARATION = (
    r"(?i:\b(?:variedades\s+de\s+(?P<es>arándanos?|fresas?|frutillas?|frambuesas?|zarzamoras?)"
    r"|odmiany\s+(?P<pl>maliny|jeżyny|truskawki|borówki)))\s*:\s*"
)
_CONJUNCTION = re.compile(r"\s*(?:,|;|\by\b|\be\b|\bi\b|\boraz\b)\s*")


def explicit_summary_formats(summary, *, name_token):
    """Yield leads and exclusions, preserving whole names, codes and row text."""
    leads, excluded = [], []
    quotes = "'‘’\"“”"
    name_pattern = (
        rf"(?:'{name_token}'|\"{name_token}\"|‘{name_token}’|“{name_token}”|"
        rf"{name_token}(?![{quotes}]))"
    )
    columns = None
    for line in summary.splitlines():
        if "|" not in line or len(line) > 8000:
            columns = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        headings = [_HEADINGS.get(cell.casefold()) for cell in cells]
        if (len(cells) in {2, 3} and None not in headings
                and len(set(headings)) == len(headings)
                and {"crop", "name"}.issubset(headings)):
            columns = headings
            continue
        if sum(heading is not None for heading in headings) >= 2:
            # A second, unsupported table must not inherit the preceding layout.
            columns = None
            excluded.append({"name": line, "reason": "table_heading_format_unresolved"})
            continue
        if columns is None or all(_SEPARATOR.fullmatch(cell) for cell in cells):
            continue
        if len(cells) != len(columns):
            excluded.append({"name": line, "reason": "table_row_shape_unresolved"})
            continue
        row = dict(zip(columns, cells))
        berry = _CROPS.get(row["crop"].casefold())
        name = row["name"]
        if not berry:
            excluded.append({"name": name, "reason": "berry_not_established"})
        elif not re.fullmatch(name_pattern, name):
            excluded.append({"name": name, "reason": "table_name_format_unresolved"})
        elif row.get("code") and not _CODE.fullmatch(row["code"]):
            excluded.append({"name": name, "reason": "table_code_format_unresolved"})
        else:
            leads.append({"name": name, "berry_id": berry, "breeder_code": row.get("code", ""),
                          "kind": "explicit_summary_table", "context": line})

    names = rf"(?P<names>{name_pattern}(?:\s*(?:,\s*(?:(?:y|e|i|oraz)\s+)?|;\s*|\b(?:y|e|i|oraz)\s+){name_pattern})*)"
    for match in re.finditer(_DECLARATION + names, summary):
        # Do not turn a negated or absent declaration into a positive name list.
        prefix = re.split(r"[.!?;\n]", summary[:match.start()])[-1]
        if re.search(r"\b(?:no|sin|nie|brak)\b", prefix, re.IGNORECASE):
            continue
        berry = _CROPS[(match.group("es") or match.group("pl")).casefold()]
        for name in _CONJUNCTION.split(match.group("names")):
            leads.append({"name": name, "berry_id": berry, "breeder_code": "",
                          "kind": "explicit_summary_translated_list", "context": match.group(0)})
    return leads, excluded
