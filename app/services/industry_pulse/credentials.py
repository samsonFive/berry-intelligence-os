"""Resolve discovery-provider credentials without logging secrets.

Canonical Cloud / process names are ``EXA_API_KEY``, ``APITUBE_API_KEY``,
and ``NEWSCATCHER_API_KEY``. Dashboard slugs that have appeared on fresh
boots (``exa_api``, ``apitube``, ``newscatcher_events_api``) are accepted
as aliases until those names are renamed to match the repo. Never invent
a value. Never log a value.
"""

from __future__ import annotations

import os

EXA_API_KEY_ENV = "EXA_API_KEY"
FIRECRAWL_API_KEY_ENV = "FIRECRAWL_API_KEY"
BRIGHTDATA_API_KEY_ENV = "BRIGHTDATA_API_KEY"
BRIGHTDATA_ZONE_ENV = "BRIGHTDATA_SERP_ZONE"
PERPLEXITY_API_KEY_ENV = "PERPLEXITY_API_KEY"
NEWSCATCHER_API_KEY_ENV = "NEWSCATCHER_API_KEY"
CATCHALL_API_KEY_ENV = "CATCHALL_API_KEY"
APITUBE_API_KEY_ENV = "APITUBE_API_KEY"

# Dashboard names seen on a later environment boot. Johnny is renaming
# those slugs to the canonical names above. Read both; prefer canonical.
EXA_API_KEY_ALIASES = (EXA_API_KEY_ENV, "exa_api")
APITUBE_API_KEY_ALIASES = (APITUBE_API_KEY_ENV, "apitube")
NEWSCATCHER_API_KEY_ALIASES = (
    NEWSCATCHER_API_KEY_ENV,
    CATCHALL_API_KEY_ENV,
    "newscatcher_events_api",
)


def env_key(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def first_env(*names: str) -> str:
    """First non-empty env value among ``names``. Empty string if none."""
    for name in names:
        value = env_key(name)
        if value:
            return value
    return ""


def exa_key() -> str:
    return first_env(*EXA_API_KEY_ALIASES)


def apitube_key() -> str:
    return first_env(*APITUBE_API_KEY_ALIASES)


def has_exa() -> bool:
    return bool(exa_key())


def has_firecrawl() -> bool:
    return bool(env_key(FIRECRAWL_API_KEY_ENV))


def has_brightdata() -> bool:
    return bool(env_key(BRIGHTDATA_API_KEY_ENV) and env_key(BRIGHTDATA_ZONE_ENV))


def has_perplexity() -> bool:
    return bool(env_key(PERPLEXITY_API_KEY_ENV))


def catchall_key() -> str:
    return first_env(*NEWSCATCHER_API_KEY_ALIASES)


def has_catchall() -> bool:
    return bool(catchall_key())


def has_apitube() -> bool:
    return bool(apitube_key())
