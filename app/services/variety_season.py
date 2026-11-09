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


def _values(row, field):
    value = row.get(field)
    return value if isinstance(value, list) else [value or "Unspecified"]


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
