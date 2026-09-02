"""Shared live discovery stack for /week and Competitor Pulse.

CatchAll is deliberately excluded: it is an async 10-15 minute paid job,
not a request-time news search. Do not invent credentials.
"""

from __future__ import annotations

from typing import Any

from app.services.industry_pulse.apitube import ApiTubeSearchProvider
from app.services.industry_pulse.credentials import has_apitube, has_exa, has_perplexity
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider
from app.services.industry_pulse.providers import GoogleNewsRssProvider
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider


def optional_sync_discovery_providers() -> list[Any]:
    """Exa / APITube when keys exist. Same DiscoveryProvider seam. No CatchAll."""
    extra: list[Any] = []
    if has_exa():
        extra.append(ExaSearchProvider())
    if has_apitube():
        extra.append(ApiTubeSearchProvider())
    return extra


def week_discovery_stack(*, perplexity_enabled: bool) -> tuple[list[Any], Any, Any]:
    """Google (+ optional sync high-recall) / Perplexity catch-net / specialist RSS."""
    primary = [GoogleNewsRssProvider(), *optional_sync_discovery_providers()]
    catch_net = PerplexitySearchProvider() if (perplexity_enabled and has_perplexity()) else None
    specialist = SpecialistRssProvider()
    return primary, catch_net, specialist


def pulse_discovery_providers(*, perplexity_enabled: bool) -> list[Any]:
    """Company pulse stays one bounded query per provider. Specialist feeds stay week-only."""
    providers: list[Any] = [GoogleNewsRssProvider(), *optional_sync_discovery_providers()]
    if perplexity_enabled and has_perplexity():
        providers.append(PerplexitySearchProvider())
    return providers
