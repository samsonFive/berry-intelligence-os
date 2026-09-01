"""Industry Pulse discovery + news recall.

Catch-net only. Does not publish Evidence, onboard Sources, or redesign
the homepage. Miss labels reuse app.services.recall_audit.classify.
"""

from app.services.industry_pulse.freshness import audit_freshness
from app.services.industry_pulse.matrix import generate_pulse_queries, query_count
from app.services.industry_pulse.providers import (
    DiscoveryProvider,
    GoogleNewsRssProvider,
    MemoryProvider,
    discover,
)
from app.services.industry_pulse.run import load_snapshot, persist_snapshot, run_pulse

__all__ = [
    "audit_freshness",
    "discover",
    "generate_pulse_queries",
    "query_count",
    "DiscoveryProvider",
    "GoogleNewsRssProvider",
    "MemoryProvider",
    "load_snapshot",
    "persist_snapshot",
    "run_pulse",
]
