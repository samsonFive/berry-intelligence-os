"""Deterministic paid-provider fallback. Production pulse does not use this."""

from __future__ import annotations

from app.services.industry_pulse.errors import ProviderError
from app.services.industry_pulse.matrix import PulseQuery
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import DiscoveryProvider


def discover_with_fallback(
    query: PulseQuery,
    *,
    primary: DiscoveryProvider,
    fallback: DiscoveryProvider,
) -> list[DiscoveryHit]:
    """Use fallback when the paid primary is missing, timed out, or rate-limited."""
    try:
        return primary.discover(query)
    except ProviderError:
        return fallback.discover(query)
