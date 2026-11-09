"""Read-only source observations for the blackberry season comparison."""

import json
from pathlib import Path

from app.services.topic_retrieval import normalize


COMPARISON = Path("imports/blackberry-season-2027/comparison.json")
FACETS = {
    "region": "Comparison region",
    "habit": "Cultivar fruiting habit",
    "crops": "Harvested cane",
    "markets": "Market",
    "window": "Harvest window",
    "trial_site": "Trial site",
    "system": "Production system",
}


def is_blackberry_floricane(plan, berry):
    return plan.cane_type == "floricane" and (
        berry == "berry-blackberry" or (berry in {None, "", "global"} and "blackberry" in plan.terms)
    )


def _values(row, field):
    value = row.get(field)
    return value if isinstance(value, list) else [value or "Unspecified"]


def season_source_leads(data_dir):
    """Yield attributed URLs for discovery, without asserting catalog traits."""
    path = Path(data_dir) / COMPARISON
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["rows"]:
        if not row["variety_id"]:
            continue
        for key in row["citations"]:
            title, url, _ = data["sources"][key]
            yield row["variety_id"], title, url, (row["habit"], row["observation"])
        for label, _, detail, key in row["events"]:
            title, url, _ = data["sources"][key]
            yield row["variety_id"], title, url, (row["habit"], label, detail)


def blackberry_season(data_dir, query, filters):
    data = json.loads((data_dir / COMPARISON).read_text(encoding="utf-8"))
    options = {
        field: sorted({value for row in data["rows"] for value in _values(row, field)})
        for field in FACETS
    }
    terms = normalize(query).split()
    matches = []
    for row in data["rows"]:
        if any(value and value not in _values(row, field) for field, value in filters.items()):
            continue
        words = set(normalize(" ".join([row["name"], *row["aliases"], row["observation"]])).split())
        if all(term in words for term in terms):
            matches.append(row)
    return {**data, "rows": matches, "facets": FACETS, "options": options}
