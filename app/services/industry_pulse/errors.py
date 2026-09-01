"""Provider-neutral discovery failures. Do not leak vendor error bodies."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """A discovery-provider failure mapped off the vendor wire."""


class ProviderUnavailableError(ProviderError):
    """Missing credentials, 5xx, or the provider cannot be reached."""


class ProviderTimeoutError(ProviderError):
    """The request exceeded its configured timeout."""


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request due to rate limiting."""


class ProviderAuthError(ProviderUnavailableError):
    """Missing or rejected credentials."""
