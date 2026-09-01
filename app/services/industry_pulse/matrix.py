"""Compact Industry Pulse query matrix.

Canonical dimensions generate a bounded set of Google News queries.
This is not hundreds of Source records. Berry × geography pulse rows
carry a bundled industry clause; topic intensifiers run globally with
all four berries OR'd together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

BERRIES = ("blueberry", "strawberry", "raspberry", "blackberry")
# Regional rows first so a later global hit of the same story does not
# steal attribution. Dedup also prefers specific geography over global.
GEOGRAPHIES = ("americas", "europe", "africa", "apac", "global")
TOPICS = (
    "new_variety",
    "breeder_genetics",
    "commercial_launch",
    "licensing_partnership",
    "pbr_patent",
    "acreage_production",
    "trade",
    "weather_crop",
    "pricing_market",
    "ma_investment",
    "trials_academic",
    "disease_regulation",
)
WINDOWS = ("24h", "3d", "7d")
WINDOW_WHEN = {"24h": "1d", "3d": "3d", "7d": "7d"}
WINDOW_DAYS = {"24h": 1, "3d": 3, "7d": 7}

BERRY_TERMS: dict[str, str] = {
    "blueberry": "(blueberry OR blueberries OR arándano OR arandano OR myrtille)",
    "strawberry": "(strawberry OR strawberries OR fresa OR fraise)",
    "raspberry": "(raspberry OR raspberries OR frambuesa OR framboise)",
    "blackberry": "(blackberry OR blackberries OR zarzamora OR caneberry)",
}
BERRY_IDS: dict[str, str] = {
    "blueberry": "berry-blueberry",
    "strawberry": "berry-strawberry",
    "raspberry": "berry-raspberry",
    "blackberry": "berry-blackberry",
}
ALL_BERRIES_TERMS = " OR ".join(BERRY_TERMS.values())

GEO_EDITIONS: dict[str, dict[str, str]] = {
    "global": {"hl": "en-US", "gl": "US", "ceid": "US:en", "terms": ""},
    "americas": {
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
        "terms": "(Peru OR Chile OR Mexico OR Canada OR Brazil OR California OR Florida OR Argentina OR Colombia)",
    },
    "europe": {
        "hl": "en-GB",
        "gl": "GB",
        "ceid": "GB:en",
        "terms": "(Europe OR Spain OR UK OR Netherlands OR Poland OR Germany OR Italy OR Portugal OR Belgium)",
    },
    "africa": {
        "hl": "en-ZA",
        "gl": "ZA",
        "ceid": "ZA:en",
        "terms": "(Africa OR \"South Africa\" OR Morocco OR Maroc OR Egypt OR Kenya OR Zimbabwe)",
    },
    "apac": {
        "hl": "en-AU",
        "gl": "AU",
        "ceid": "AU:en",
        "terms": "(Australia OR China OR Japan OR Korea OR \"New Zealand\" OR India OR Vietnam OR Tasmania)",
    },
}

PULSE_TOPICS = (
    "variety OR cultivar OR breeder OR genetics OR launch OR PBR OR patent "
    "OR export OR import OR harvest OR acreage OR price OR licensing"
)

TOPIC_TERMS: dict[str, str] = {
    "new_variety": '("new variety" OR cultivar OR "variety launch")',
    "breeder_genetics": "(breeder OR breeding OR genetics OR nursery OR genetics)",
    "commercial_launch": "(launch OR launches OR unveils OR introduces OR debut)",
    "licensing_partnership": "(license OR licensing OR partnership OR royalty)",
    "pbr_patent": '(PBR OR "plant breeders rights" OR "plant patent" OR CPVO OR USPTO)',
    "acreage_production": "(acreage OR hectares OR production OR planting OR harvest)",
    "trade": '(export OR exports OR import OR imports OR "market access" OR tariff)',
    "weather_crop": '(frost OR drought OR "crop condition" OR weather OR hail)',
    "pricing_market": '(price OR pricing OR "spot price" OR "market report")',
    "ma_investment": '(acquisition OR merger OR investment OR "private equity" OR "joint venture")',
    "trials_academic": '(trial OR "field trial" OR university OR extension OR "research station")',
    "disease_regulation": "(disease OR pest OR SWD OR residue OR regulation OR recall)",
}


@dataclass(frozen=True)
class PulseQuery:
    id: str
    text: str
    berry: str | None
    geography: str
    topic: str
    kind: str
    hl: str
    gl: str
    ceid: str
    date_window: str | None = None

    def with_window(self, window: str) -> "PulseQuery":
        if window not in WINDOW_WHEN:
            raise ValueError(f"unsupported window: {window}")
        when = WINDOW_WHEN[window]
        text = f"{self.text} when:{when}"
        return PulseQuery(
            id=f"{self.id}:{window}",
            text=text,
            berry=self.berry,
            geography=self.geography,
            topic=self.topic,
            kind=self.kind,
            hl=self.hl,
            gl=self.gl,
            ceid=self.ceid,
            date_window=window,
        )

    def feed_url(self) -> str:
        return (
            "https://news.google.com/rss/search?"
            f"q={quote(self.text)}&hl={self.hl}&gl={self.gl}&ceid={self.ceid}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "berry": self.berry,
            "geography": self.geography,
            "topic": self.topic,
            "kind": self.kind,
            "hl": self.hl,
            "gl": self.gl,
            "ceid": self.ceid,
            "feed_url": self.feed_url(),
        }


def generate_pulse_queries() -> list[PulseQuery]:
    """Berry × geography pulse (20) plus global topic intensifiers (12) = 32."""
    rows: list[PulseQuery] = []
    for berry in BERRIES:
        berry_terms = BERRY_TERMS[berry]
        for geography in GEOGRAPHIES:
            edition = GEO_EDITIONS[geography]
            parts = [berry_terms]
            if edition["terms"]:
                parts.append(edition["terms"])
            parts.append(f"({PULSE_TOPICS})")
            rows.append(
                PulseQuery(
                    id=f"pulse:{berry}:{geography}",
                    text=" ".join(parts),
                    berry=berry,
                    geography=geography,
                    topic="industry_pulse",
                    kind="berry_geography",
                    hl=edition["hl"],
                    gl=edition["gl"],
                    ceid=edition["ceid"],
                )
            )
    global_edition = GEO_EDITIONS["global"]
    for topic in TOPICS:
        rows.append(
            PulseQuery(
                id=f"topic:{topic}:global",
                text=f"({ALL_BERRIES_TERMS}) {TOPIC_TERMS[topic]}",
                berry=None,
                geography="global",
                topic=topic,
                kind="topic_global",
                hl=global_edition["hl"],
                gl=global_edition["gl"],
                ceid=global_edition["ceid"],
            )
        )
    return rows


def query_count() -> int:
    return len(generate_pulse_queries())


# Regions where the bake-off found Google News RSS historically underperforms
# (docs/v2/RETRIEVAL-PROVIDER-BAKE-OFF-V1.md: Google is Europe-heavy; Perplexity
# showed broader Americas/Africa recall and better date-window fidelity).
CATCH_NET_GEOGRAPHIES = ("americas", "africa")


def catch_net_queries(queries: list[PulseQuery]) -> list[PulseQuery]:
    """Bounded query subset for an optional semantic catch-net provider.

    Deliberately not the full 32-query matrix: doubling every query to a
    second, paid provider is not justified where Google's baseline already
    performs adequately (Europe, APAC, and the global-geography berry rows).
    Routes only the two regions where the bake-off found Google weakest
    (Americas, Africa) plus the 12 global topic intensifiers -- the
    "semantic/high-value topic" queries a semantic provider is best suited
    to -- for 20 of 32 queries (~63%), not a doubled 32.
    """
    return [
        query
        for query in queries
        if query.kind == "topic_global" or query.geography in CATCH_NET_GEOGRAPHIES
    ]
