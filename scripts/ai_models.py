"""Read-only external-AI model discovery.

Lists the models a provider currently exposes, so an operator can choose an
exact model id to configure and qualify. This never writes anything: the model
catalog is live provider state, not trusted repository data, so nothing is
persisted here.

Usage:
    python scripts/ai_models.py --provider perplexity-agent
    python scripts/ai_models.py --provider perplexity-agent --json
    python scripts/ai_models.py --provider perplexity-agent --owned-by anthropic

PERPLEXITY_API_KEY is read from the environment if present. Perplexity's
`GET /v1/models` does not require authentication, so discovery works without a
key; a key is sent only if one is set.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_gateway.credentials import PERPLEXITY_API_KEY_ENV
from app.services.ai_gateway.errors import GatewayError, GatewayMalformedResponseError
from app.services.ai_gateway.perplexity_agent import DEFAULT_PERPLEXITY_MODELS_URL, list_agent_models


PROVIDER_CHOICES = ("perplexity-agent",)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only external-AI model discovery (no persistence).")
    parser.add_argument("--provider", choices=PROVIDER_CHOICES, default="perplexity-agent")
    parser.add_argument("--base-url", default=DEFAULT_PERPLEXITY_MODELS_URL)
    parser.add_argument("--owned-by", help="Filter to a single provider owner, e.g. anthropic, openai, google.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    api_key = os.environ.get(PERPLEXITY_API_KEY_ENV) or None
    try:
        models = list_agent_models(api_key=api_key, base_url=args.base_url)
    except (GatewayError, GatewayMalformedResponseError, ValueError) as exc:
        print(json.dumps({"state": "error", "provider": args.provider, "error": str(exc)}, indent=2))
        return 2

    if args.owned_by:
        needle = args.owned_by.strip().casefold()
        models = [model for model in models if model["owned_by"].casefold() == needle]

    if args.json:
        print(json.dumps({"provider": args.provider, "count": len(models), "models": models}, indent=2))
        return 0

    if not models:
        print(f"No models returned for {args.provider}.")
        return 0
    print(f"{args.provider}: {len(models)} model(s)")
    for model in models:
        owner = f"  [{model['owned_by']}]" if model["owned_by"] else ""
        print(f"  {model['id']}{owner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
