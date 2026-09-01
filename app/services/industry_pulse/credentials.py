"""Resolve discovery-provider credentials without logging secrets."""

from __future__ import annotations

import os

EXA_API_KEY_ENV = "EXA_API_KEY"
FIRECRAWL_API_KEY_ENV = "FIRECRAWL_API_KEY"
BRIGHTDATA_API_KEY_ENV = "BRIGHTDATA_API_KEY"
BRIGHTDATA_ZONE_ENV = "BRIGHTDATA_SERP_ZONE"
PERPLEXITY_API_KEY_ENV = "PERPLEXITY_API_KEY"


def env_key(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def has_exa() -> bool:
    return bool(env_key(EXA_API_KEY_ENV))


def has_firecrawl() -> bool:
    return bool(env_key(FIRECRAWL_API_KEY_ENV))


def has_brightdata() -> bool:
    return bool(env_key(BRIGHTDATA_API_KEY_ENV) and env_key(BRIGHTDATA_ZONE_ENV))


def has_perplexity() -> bool:
    return bool(env_key(PERPLEXITY_API_KEY_ENV))
