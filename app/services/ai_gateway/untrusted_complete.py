"""Provider-neutral JSON completion for low-risk, non-trusted suggestions.

This is not an extraction path and does not qualify a model. Callers must keep
the result explicitly untrusted. Failures raise; callers decide whether to
continue without suggestions.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from app.services.ai_gateway.credentials import PERPLEXITY_API_KEY_ENV, MissingCredentialError, resolve_perplexity_api_key
from app.services.ai_gateway.perplexity_agent import (
    DEFAULT_PERPLEXITY_AGENT_BASE_URL,
    PerplexityAgentTransport,
    agent_compatible_response_format,
)


@dataclass(frozen=True)
class UntrustedJsonResult:
    parsed: dict[str, Any]
    model: str | None
    provider: str


def _extract_object(content: str) -> dict[str, Any]:
    value = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", value, flags=re.IGNORECASE)
    if fence:
        value = fence.group(1).strip()
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("untrusted completer returned a non-object")
    return payload


def complete_untrusted_json(
    prompt: str,
    *,
    schema: dict[str, Any],
    model: str,
    provider: str = "perplexity-agent",
    max_output_tokens: int = 800,
) -> UntrustedJsonResult:
    if provider != "perplexity-agent":
        raise ValueError(f"unsupported untrusted-inference provider: {provider}")
    api_key = resolve_perplexity_api_key()
    transport = PerplexityAgentTransport(
        api_key=api_key,
        base_url=os.environ.get("BIOS_PERPLEXITY_AGENT_BASE_URL", DEFAULT_PERPLEXITY_AGENT_BASE_URL),
    )
    response_format = agent_compatible_response_format(
        {
            "type": "json_schema",
            "json_schema": {
                "name": "publication_enrichment_v1",
                "strict": True,
                "schema": schema,
            },
        }
    )
    response = transport.complete(
        model=model,
        instructions="Return JSON only. Do not search the web. Do not invent facts.",
        input_text=prompt,
        response_format=response_format,
        max_output_tokens=max_output_tokens,
    )
    return UntrustedJsonResult(
        parsed=_extract_object(response.content),
        model=response.model or model,
        provider=provider,
    )


def maybe_untrusted_completer() -> Any | None:
    """Return a live completer when a key is present; otherwise None."""

    if not (os.environ.get(PERPLEXITY_API_KEY_ENV) or "").strip():
        return None

    def _complete(prompt: str, **kwargs: Any) -> UntrustedJsonResult:
        return complete_untrusted_json(prompt, **kwargs)

    return _complete


def missing_credential_error() -> type[Exception]:
    return MissingCredentialError
