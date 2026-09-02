"""External-system layer classes. Not news semantics.

Each audited system is one of these. Do not force every source through
Industry Pulse / DiscoveryHit.
"""

from __future__ import annotations

DISCOVERY_PROVIDER = "DISCOVERY_PROVIDER"
ACQUISITION_PROVIDER = "ACQUISITION_PROVIDER"
AUTHORITATIVE_REGISTRY = "AUTHORITATIVE_REGISTRY"
STRUCTURED_DATASET = "STRUCTURED_DATASET"
SPECIALIST_SOURCE = "SPECIALIST_SOURCE"
NORMALIZATION_REFERENCE = "NORMALIZATION_REFERENCE"

LAYER_OF = {
    "google_news_rss": DISCOVERY_PROVIDER,
    "perplexity": DISCOVERY_PROVIDER,
    "exa": DISCOVERY_PROVIDER,
    "apitube": DISCOVERY_PROVIDER,
    "newscatcher_catchall": DISCOVERY_PROVIDER,
    "specialist_rss": DISCOVERY_PROVIDER,
    "usda_pvpo": AUTHORITATIVE_REGISTRY,
    "upov_pluto": NORMALIZATION_REFERENCE,
    "uspto_odp": AUTHORITATIVE_REGISTRY,
    "cpvo_register": AUTHORITATIVE_REGISTRY,
    "google_patents_bigquery": STRUCTURED_DATASET,
    "google_patents_json": DISCOVERY_PROVIDER,
    "hortidaily": SPECIALIST_SOURCE,
    "fruitnet": SPECIALIST_SOURCE,
    "freshplaza": SPECIALIST_SOURCE,
    "the_packer": SPECIALIST_SOURCE,
    "italian_berry": SPECIALIST_SOURCE,
    "freshfruitportal": SPECIALIST_SOURCE,
    "eastfruit": SPECIALIST_SOURCE,
    "produce_report": SPECIALIST_SOURCE,
    "perishable_news": SPECIALIST_SOURCE,
}
