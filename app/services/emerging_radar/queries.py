"""Bounded Radar retrieval queries. Not the Pulse 32.

Google receives short theme searches. Exa receives natural-language
semantic probes for things an analyst did not type as a keyword query.
Specialist RSS stays the existing bounded catalog. APITube is never used
on this stack.
"""

from __future__ import annotations

from app.services.industry_pulse.matrix import GEO_EDITIONS, PulseQuery

_EDITION = GEO_EDITIONS["global"]

# Google News theme rows — concise concepts, not nested Boolean forests.
RADAR_GOOGLE_THEMES: tuple[tuple[str, str, str | None], ...] = (
    ("radar:g:partnership", "berry breeding partnership OR nursery license", None),
    ("radar:g:variety", "new berry cultivar OR variety launch OR seedless blackberry", None),
    ("radar:g:expansion", "blueberry production expansion OR new hectares berry", None),
    ("radar:g:access", "berry market access OR phytosanitary berry export", None),
    ("radar:g:retail", "retail berry program OR exclusive strawberry raspberry", None),
    ("radar:g:ip", "PBR berry OR plant variety protection blueberry strawberry", None),
    ("radar:g:cea", "greenhouse berry production OR controlled environment blueberry", None),
    ("radar:g:supply", "berry supply shortage OR raspberry harvest volume", None),
)

# Exa semantic radar — deliberately not a rewrite of week_unknown_unknown_queries
# and not a rewrite of generate_pulse_queries(). Crop name may be absent.
RADAR_SEMANTIC_THEMES: tuple[tuple[str, str, str | None], ...] = (
    ("radar:exa:breeding-partnerships", "berry breeding partnership announced by a nursery or genetics company", None),
    ("radar:exa:cultivar-commercialization", "new berry cultivar commercialization or managed variety release", None),
    ("radar:exa:licensing", "soft fruit variety licensing agreement or royalty program", None),
    ("radar:exa:cea-production", "controlled environment or greenhouse berry production expansion", None),
    ("radar:exa:disease-resistance", "disease resistant blueberry or strawberry cultivar from a breeding program", None),
    ("radar:exa:shelf-life", "shelf life genetics in blueberry or raspberry breeding", None),
    ("radar:exa:production-expansion", "new berry farm hectares or packing plant expansion", None),
    ("radar:exa:new-markets", "berry export market access or new destination for blueberries", None),
    ("radar:exa:supply-pressure", "berry supply pressure frost damage or harvest shortfall growers", None),
    ("radar:exa:retailer-programs", "retailer exclusive berry program or supermarket berry sourcing deal", None),
    ("radar:exa:unusual-rd", "unusual berry research gene editing or seedless blackberry innovation", None),
    ("radar:exa:emerging-systems", "vertical farm or substrate berry cultivation commercial scale", None),
)

RADAR_CATCHNET_THEMES: tuple[tuple[str, str, str | None], ...] = (
    ("radar:px:licensing", "berry variety licensing or breeding partnership this year", None),
    ("radar:px:expansion", "blueberry or raspberry production expansion outside the usual trade recap", None),
    ("radar:px:genetics", "new berry genetics or seedless caneberry commercialization", None),
)


def _query(query_id: str, text: str, berry: str | None, *, kind: str, topic: str) -> PulseQuery:
    return PulseQuery(
        id=query_id,
        text=text,
        berry=berry,
        geography="global",
        topic=topic,
        kind=kind,
        hl=_EDITION["hl"],
        gl=_EDITION["gl"],
        ceid=_EDITION["ceid"],
        date_window="30d",
    )


def radar_google_queries() -> list[PulseQuery]:
    return [
        _query(query_id, text, berry, kind="radar_theme", topic="radar_google")
        for query_id, text, berry in RADAR_GOOGLE_THEMES
    ]


def radar_semantic_queries() -> list[PulseQuery]:
    """Exa-only. Never sent to Google. Not the Pulse 32."""
    return [
        _query(query_id, text, berry, kind="radar_semantic", topic="radar_semantic")
        for query_id, text, berry in RADAR_SEMANTIC_THEMES
    ]


def radar_catchnet_queries() -> list[PulseQuery]:
    return [
        _query(query_id, text, berry, kind="radar_catchnet", topic="radar_catchnet")
        for query_id, text, berry in RADAR_CATCHNET_THEMES
    ]


def radar_query_budget() -> dict[str, int]:
    return {
        "google_themes": len(RADAR_GOOGLE_THEMES),
        "exa_semantic": len(RADAR_SEMANTIC_THEMES),
        "perplexity_optional": len(RADAR_CATCHNET_THEMES),
        "pulse_32": 0,
    }
