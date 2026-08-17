"""Runtime-only credential resolution for the external-AI gateway.

`PERPLEXITY_API_KEY` is read from the environment at call time only. It is
never written to a file, never embedded in provenance, status, or review
output, and never duplicated into another env var name (existing local
extraction config keeps using `BIOS_EXTRACT_API_KEY` unrelated to this).
`sanitize()` must be applied to any error text that might echo a secret
before that text is stored, printed, or returned to a caller.
"""

from __future__ import annotations

import os


PERPLEXITY_API_KEY_ENV = "PERPLEXITY_API_KEY"


class MissingCredentialError(RuntimeError):
    """The required runtime credential is not present."""


def resolve_perplexity_api_key(env: dict[str, str] | None = None) -> str:
    """Reads PERPLEXITY_API_KEY from the environment; never prompts, never logs it."""

    source = env if env is not None else os.environ
    value = (source.get(PERPLEXITY_API_KEY_ENV) or "").strip()
    if not value:
        raise MissingCredentialError(
            f"{PERPLEXITY_API_KEY_ENV} is not set in this environment. "
            "Set it for this PowerShell session with:\n"
            f'  $env:{PERPLEXITY_API_KEY_ENV} = "<key>"'
        )
    return value


def sanitize(text: str, *secrets: str | None) -> str:
    """Redacts any given secret value (e.g. an API key) from text before it
    is logged, persisted, or surfaced to an operator."""

    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized
