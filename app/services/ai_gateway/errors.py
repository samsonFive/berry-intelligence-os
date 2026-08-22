"""Provider-neutral failure taxonomy for the external-AI capability layer.

Every provider adapter (Perplexity today, others later) maps its own
provider-native failures onto these types before returning to a caller.
Two independent roots mirror the existing extraction module's own
provider-vs-response split: `GatewayError` is a transport/provider-level
failure (auth, rate limit, unavailable, timeout, model not found);
`GatewayMalformedResponseError` is a response-shape failure (unparsable
envelope, structured-output incompatibility). Nothing here is Perplexity-
specific; adapters supply the mapping, not the taxonomy.
"""

from __future__ import annotations


class GatewayError(RuntimeError):
    """A gateway/provider-level failure, normalized across providers."""


class GatewayAuthError(GatewayError):
    """Missing or rejected credentials."""


class GatewayRateLimitError(GatewayError):
    """The gateway rejected the request due to rate limiting."""


class GatewayUnavailableError(GatewayError):
    """The gateway or provider endpoint could not be reached."""


class GatewayTimeoutError(GatewayError):
    """The request exceeded its configured timeout."""


class GatewayModelNotFoundError(GatewayError):
    """The routed model is unknown, retired, or not permitted."""


class GatewayMalformedResponseError(RuntimeError):
    """The provider returned a response that could not be parsed or used."""


class GatewayStructuredResponseIncompatibleError(GatewayMalformedResponseError):
    """The provider could not or did not honor the requested structured schema."""
