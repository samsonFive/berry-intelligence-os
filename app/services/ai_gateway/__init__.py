"""External-AI capability layer: provider-neutral inference/research/search.

Domain services (extraction, future research/discovery) never call a vendor
SDK or build vendor-specific requests directly. They go through this layer,
which normalizes every provider's responses, identities, usage, and failures
into the same shapes regardless of which gateway/provider handled the call.

Perplexity is one provider adapter here, not a domain concept -- nothing
outside `app/services/ai_gateway/` should import a Perplexity-specific name.
"""
