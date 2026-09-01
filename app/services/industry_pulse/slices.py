"""Bake-off query slices A–F. Semantic equivalents across providers."""

from __future__ import annotations

from app.services.industry_pulse.matrix import (
    ALL_BERRIES_TERMS,
    BERRY_TERMS,
    GEO_EDITIONS,
    PULSE_TOPICS,
    TOPIC_TERMS,
    PulseQuery,
    WINDOWS,
)

BAKEOFF_SLICES: tuple[dict[str, str | None], ...] = (
    {
        "id": "A",
        "berry": "blackberry",
        "geography": "europe",
        "topic": "breeder_genetics",
        "text": "blackberry cultivar variety breeder genetics Europe Spain Netherlands UK",
    },
    {
        "id": "B",
        "berry": "raspberry",
        "geography": "europe",
        "topic": "breeder_genetics",
        "text": "raspberry cultivar variety breeder genetics UK Scotland England",
    },
    {
        "id": "C",
        "berry": "blueberry",
        "geography": "africa",
        "topic": "breeder_genetics",
        "text": "blueberry genetics commercial deployment South Africa cultivar variety",
    },
    {
        "id": "D",
        "berry": "blueberry",
        "geography": "americas",
        "topic": "pbr_patent",
        "text": "blueberry genetics PBR patent plant breeders rights United States cultivar",
    },
    {
        "id": "E",
        "berry": "strawberry",
        "geography": "europe",
        "topic": "commercial_launch",
        "text": "strawberry genetics commercialization cultivar variety Europe breeder",
    },
    {
        "id": "F",
        "berry": None,
        "geography": "global",
        "topic": "industry_pulse",
        "text": "berry industry blueberry strawberry raspberry blackberry major developments cultivar",
    },
)

# Public pages only. Used if Firecrawl scrape credentials exist.
ACQUISITION_PROBE_URLS: tuple[tuple[str, str], ...] = (
    ("static_article", "https://www.freshplaza.com/"),
    ("trade_press", "https://www.freshfruitportal.com/"),
    ("js_or_waf", "https://www.growingproduce.com/fruits/berries/"),
    ("breeder_catalogue", "https://www.fallcreeknursery.com/"),
    ("cultivar_table", "https://www.blueberrybreeding.com/"),
    ("government", "https://www.ams.usda.gov/services/plant-variety-protection"),
    ("university", "https://extension.oregonstate.edu/"),
    ("pbr_registry", "https://online.plantvarieties.eu/"),
    ("south_africa", "https://www.dalrrd.gov.za/"),
    ("uk_gov", "https://www.gov.uk/government/organisations/animal-and-plant-health-agency"),
)


def google_news_text(row: dict[str, str | None]) -> str:
    """Documented Google News boolean translation. Same slice semantics."""
    berry = row.get("berry")
    parts = [BERRY_TERMS[berry]] if berry in BERRY_TERMS else [f"({ALL_BERRIES_TERMS})"]
    edition = GEO_EDITIONS.get(str(row["geography"])) or GEO_EDITIONS["global"]
    if edition["terms"]:
        parts.append(edition["terms"])
    topic = row.get("topic")
    if topic in TOPIC_TERMS:
        parts.append(TOPIC_TERMS[topic])
    else:
        parts.append(f"({PULSE_TOPICS})")
    return " ".join(parts)


def slice_query(row: dict[str, str | None], window: str, *, google_when: bool = False) -> PulseQuery:
    if window not in WINDOWS:
        raise ValueError(f"unsupported window: {window}")
    geography = str(row["geography"])
    edition = GEO_EDITIONS.get(geography) or GEO_EDITIONS["global"]
    text = google_news_text(row) if google_when else str(row["text"])
    query = PulseQuery(
        id=f"bakeoff:{row['id']}:{geography}",
        text=text,
        berry=row.get("berry"),
        geography=geography,
        topic=str(row["topic"]),
        kind="bakeoff",
        hl=edition["hl"],
        gl=edition["gl"],
        ceid=edition["ceid"],
        date_window=window,
    )
    if google_when:
        return query.with_window(window)
    return PulseQuery(
        id=f"{query.id}:{window}",
        text=query.text,
        berry=query.berry,
        geography=query.geography,
        topic=query.topic,
        kind=query.kind,
        hl=query.hl,
        gl=query.gl,
        ceid=query.ceid,
        date_window=window,
    )
