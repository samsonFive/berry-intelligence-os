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
    "usda_pvpo": AUTHORITATIVE_REGISTRY,
    "upov_pluto": NORMALIZATION_REFERENCE,
    "uspto_odp": AUTHORITATIVE_REGISTRY,
    "google_patents_bigquery": STRUCTURED_DATASET,
    "google_patents_json": DISCOVERY_PROVIDER,
    "newscatcher_catchall": DISCOVERY_PROVIDER,
    "hortidaily": SPECIALIST_SOURCE,
}
