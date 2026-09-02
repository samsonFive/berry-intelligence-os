"""Shared live discovery stack for /week and Competitor Pulse.

FAST REQUEST-TIME: Google, Perplexity, APITube, Exa.
BACKGROUND HIGH-RECALL: CatchAll cache only — never a live CatchAll submit.
DIRECT SPECIALIST: SpecialistRssProvider.

Publisher != discovery provider. Do not invent credentials.
SET APITUBE_API_KEY / EXA_API_KEY to activate those providers with no code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.industry_pulse.apitube import ApiTubeSearchProvider
from app.services.industry_pulse.catchall_cache import hits_from_cache
from app.services.industry_pulse.credentials import has_apitube, has_exa, has_perplexity
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.models import DiscoveryHit
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


def radar_discovery_stack(*, perplexity_enabled: bool) -> tuple[list[Any], Any, Any]:
    """Request-time Radar stack from the live provider bake-off.

    CORE: Google News RSS, specialist RSS, Exa (when keyed).
    OPTIONAL: Perplexity, three catch-net themes.
    NOT REQUEST-TIME: APITube, live CatchAll.
    """
    primary: list[Any] = [GoogleNewsRssProvider()]
    if has_exa():
        primary.append(ExaSearchProvider())
    catch_net = PerplexitySearchProvider() if (perplexity_enabled and has_perplexity()) else None
    specialist = SpecialistRssProvider()
    return primary, catch_net, specialist


def week_background_hits(*, inbox_dir: Path | None = None) -> list[DiscoveryHit]:
    """Already-fetched CatchAll rows. Empty when the cache has not been written."""
    return hits_from_cache(inbox_dir)


def pulse_discovery_providers(*, perplexity_enabled: bool) -> list[Any]:
    """Company pulse stays one bounded query per provider. Specialist feeds stay week-only."""
    providers: list[Any] = [GoogleNewsRssProvider(), *optional_sync_discovery_providers()]
    if perplexity_enabled and has_perplexity():
        providers.append(PerplexitySearchProvider())
    return providers
