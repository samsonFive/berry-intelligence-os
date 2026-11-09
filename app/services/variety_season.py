"""Read-only source observations for the berry season comparisons."""

import json
import re
from pathlib import Path

from app.services.topic_retrieval import normalize


COMPARISON = Path("imports/blackberry-season-2027/comparison.json")
SEASON_CROPS = ("berry-blackberry", "berry-blueberry", "berry-raspberry", "berry-strawberry")
FACETS = {
    "region": "Comparison region",
    "habit": "Cultivar fruiting habit",
    "crops": "Harvested cane",
    "markets": "Market",
    "window": "Harvest window",
    "trial_site": "Trial site",
    "system": "Production system",
    "evidence_status": "Evidence status",
}


def comparison_path(berry):
    return Path(f"imports/{berry.removeprefix('berry-')}-season-2027/comparison.json")


def is_blackberry_floricane(plan, berry):
    return plan.cane_type == "floricane" and (
        berry == "berry-blackberry" or (berry in {None, "", "global"} and "blackberry" in plan.terms)
    )


def season_query_crop(plan, berry):
    if is_blackberry_floricane(plan, berry):
        return "berry-blackberry"
    terms = set(plan.terms)
    if not terms.intersection({"season", "2027"}) or plan.start or plan.end or plan.exclusions:
        return None
    named_crops = [crop for crop in SEASON_CROPS if crop.removeprefix("berry-") in terms]
    if len(named_crops) == 1 and berry in {None, "", "global", named_crops[0]}:
        return named_crops[0]
    if not named_crops and berry in SEASON_CROPS:
        return berry
    return None


def season_preview(data_dir, plan):
    """Show the bounded comparison separately from archive search results."""
    terms = set(plan.terms)
    if plan.start or plan.end or plan.exclusions or plan.phrases:
        return []
    overview_terms = {
        "blackberry", "floricane", "variety", "commercial", "season", "year", "2027",
        "this", "next", "upcoming", "note", "noteworthy", "northern", "hemisphere",
    }
    if terms - overview_terms:
        return []
    if not (Path(data_dir) / COMPARISON).is_file():
        return []
    data = blackberry_season(data_dir, "", {"habit": "Floricane"})
    return [
        {"name": row["name"], "region": row["region"], "observation": row["observation"],
         "sources": [data["sources"][key] for key in row["citations"]]}
        for row in data["rows"]
        if any(str(event[1] or "")[:4] >= "2024" for event in row["events"])
    ][:3]


def _values(row, field):
    value = row.get(field)
    return value if isinstance(value, list) else [value or "Unspecified"]


def season_source_leads(data_dir):
    """Yield attributed URLs for discovery, without asserting catalog traits."""
    for berry in SEASON_CROPS:
        path = Path(data_dir) / comparison_path(berry)
        if path.is_file():
            yield from _comparison_source_leads(json.loads(path.read_text(encoding="utf-8")))


def _comparison_source_leads(data):
    for row in data["rows"]:
        if not row["variety_id"]:
            continue
        for key in row["citations"]:
            title, url, _ = data["sources"][key]
            yield row["variety_id"], title, url, (row["habit"] or "", row["observation"])
        for label, _, detail, key in row["events"]:
            title, url, _ = data["sources"][key]
            yield row["variety_id"], title, url, (row["habit"] or "", label, detail)


def season_candidate_sources(data_dir, plan):
    """Seed explicit public discovery from inspected references, including uncataloged names."""
    terms = set(plan.terms)
    positive = normalize(re.sub(r'(?<!\w)-("[^"]+"|[\w-]+)', "", plan.interpreted_query))
    hits = {}
    for berry in SEASON_CROPS:
        if berry == "berry-blackberry" and not terms.intersection({"blackberry", "mora", "floricane", "primocane"}):
            continue
        crop = berry.removeprefix("berry-")
        other_crops = {key.removeprefix("berry-") for key in SEASON_CROPS if key != berry}
        if crop not in terms and terms.intersection(other_crops):
            continue
        path = Path(data_dir) / comparison_path(berry)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            for title, url, subject in _candidate_sources(data, plan, terms, positive):
                if url in hits and hits[url][2] != subject:
                    hits[url] = (title, url, "")
                else:
                    hits.setdefault(url, (title, url, subject))
    return list(hits.values())[:4]


def _candidate_sources(data, plan, terms, positive):
    keys = {}
    for row in data["rows"]:
        if any(
            len(name) >= 4 and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", positive)
            for name in map(normalize, [row["name"], *row["aliases"]])
        ):
            for key in [*row["citations"], *(event[-1] for event in row["events"])]:
                if key in keys and keys[key] != row["name"]:
                    keys[key] = ""
                else:
                    keys.setdefault(key, row["name"])
    if "blackberry" in terms:
        for catalog in data.get("market_catalogs", []):
            if (
                (not catalog.get("habit") or plan.cane_type == catalog["habit"])
                and set(catalog.get("required_terms", ())) <= terms
                and any(re.search(r"(?<!\w)" + re.escape(place) + r"(?!\w)", positive) for place in catalog["market_terms"])
            ):
                keys.setdefault(catalog["source_id"], "")
    return [(*data["sources"][key][:2], subject) for key, subject in list(keys.items())[:4]]


def blackberry_season(data_dir, query, filters, *, repositories=None):
    return berry_season(data_dir, "berry-blackberry", query, filters, repositories=repositories)


def berry_season(data_dir, berry, query, filters, *, repositories=None):
    data = json.loads((data_dir / comparison_path(berry)).read_text(encoding="utf-8"))
    facets = {
        field: ("Cultivar type" if field == "habit" and berry == "berry-blueberry" else label)
        for field, label in FACETS.items()
        if any(row.get(field) for row in data["rows"]) or field == "evidence_status"
    }
    for row in data["rows"]:
        reviewed = {}
        keys = set(row["citations"]) | {event[-1] for event in row["events"]}
        for key, evidence_id in data.get("reviewed_sources", {}).get(row["name"], {}).items():
            if repositories is None or key not in keys:
                continue
            evidence = repositories.evidence.get(evidence_id)
            if not evidence or evidence.get("status") != "published" or evidence.get("verification_state") == "disputed":
                continue
            if evidence.get("source_url") != data["sources"][key][1]:
                continue
            if any(
                fact and fact.get("status") == "active" and evidence_id in (fact.get("evidence_ids") or [])
                for fact in (repositories.facts.get(fact_id) for fact_id in evidence.get("fact_ids") or [])
            ):
                reviewed[key] = evidence_id
        row["reviewed"] = reviewed
        row["evidence_status"] = "Has reviewed evidence" if reviewed else "Source-reported only"
    options = {
        field: sorted({value for row in data["rows"] for value in _values(row, field)})
        for field in facets
    }
    terms = normalize(query).split()
    matches = []
    for row in data["rows"]:
        if any(value and value not in _values(row, field) for field, value in filters.items()):
            continue
        words = set(normalize(" ".join([row["name"], *row["aliases"], row["observation"]])).split())
        if all(term in words for term in terms):
            matches.append(row)
    return {**data, "rows": matches, "facets": facets, "options": options}
