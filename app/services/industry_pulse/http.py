"""Map HTTP/gateway failures onto provider-neutral discovery errors."""

from __future__ import annotations

from typing import Any

import httpx

from app.services.ai_gateway.errors import (
    GatewayAuthError,
    GatewayError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    GatewayUnavailableError,
)
from app.services.industry_pulse.errors import (
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def raise_for_status(status: int, *, detail: str = "") -> None:
    message = f"discovery provider HTTP failure ({status})"
    if detail:
        message = f"{message}: {detail[:200]}"
    if status in (401, 403):
        raise ProviderAuthError(message)
    if status == 429:
        raise ProviderRateLimitError(message)
    if status >= 500:
        raise ProviderUnavailableError(message)
    if status >= 400:
        raise ProviderUnavailableError(message)


def map_transport(exc: BaseException) -> ProviderError:
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeoutError("discovery provider request timed out")
    if isinstance(exc, httpx.HTTPError):
        return ProviderUnavailableError(f"discovery provider transport failure ({type(exc).__name__})")
    return ProviderUnavailableError(f"discovery provider failure ({type(exc).__name__})")


def map_gateway(exc: BaseException) -> ProviderError:
    if isinstance(exc, GatewayAuthError):
        return ProviderAuthError("discovery provider rejected credentials")
    if isinstance(exc, GatewayRateLimitError):
        return ProviderRateLimitError("discovery provider rate limited the request")
    if isinstance(exc, GatewayTimeoutError):
        return ProviderTimeoutError("discovery provider request timed out")
    if isinstance(exc, GatewayUnavailableError):
        return ProviderUnavailableError("discovery provider is unavailable")
    if isinstance(exc, GatewayError):
        return ProviderUnavailableError("discovery provider request failed")
    return ProviderUnavailableError(f"discovery provider failure ({type(exc).__name__})")


def request_json(
    post: Any,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: float,
) -> Any:
    try:
        response = post(url, headers=headers, json=body, timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 — map onto provider errors
        raise map_transport(exc) from exc
    status = getattr(response, "status_code", 0)
    if status >= 400:
        detail = ""
        text = getattr(response, "text", "") or ""
        raise_for_status(status, detail=text)
    try:
        return response.json()
    except (ValueError, TypeError) as exc:
        raise ProviderUnavailableError("discovery provider returned a malformed response") from exc
