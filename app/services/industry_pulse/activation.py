"""Configuration-only activation for paid discovery providers.

No credential is invented here. A missing key means the adapter is
complete and the provider stays dark. Setting the documented env var is
the only operator step required to go live.

CatchAll is background-only. It is never a request-time /week provider.
"""

from __future__ import annotations

from typing import Any

from app.services.industry_pulse.credentials import (
    APITUBE_API_KEY_ENV,
    CATCHALL_API_KEY_ENV,
    EXA_API_KEY_ENV,
    NEWSCATCHER_API_KEY_ENV,
    PERPLEXITY_API_KEY_ENV,
    has_apitube,
    has_catchall,
    has_exa,
    has_perplexity,
)
from app.services.patent_monitor.bigquery_patents import PROJECT_ENV, available as bigquery_available
from app.services.patent_monitor.uspto_odp import API_KEY_ENV as USPTO_ODP_KEY_ENV
from app.services.patent_monitor.uspto_odp import odp_available

LANE_FAST = "FAST_REQUEST_TIME"
LANE_BACKGROUND = "BACKGROUND_HIGH_RECALL"
LANE_SPECIALIST = "DIRECT_SPECIALIST"
LANE_REGISTRY = "AUTHORITATIVE_REGISTRY"
LANE_DATASET = "STRUCTURED_DATASET"

APITUBE_CONTRACT = {
    "provider": "apitube",
    "lane": LANE_FAST,
    "env": APITUBE_API_KEY_ENV,
    "operator_step": f"SET {APITUBE_API_KEY_ENV} → provider becomes available",
    "endpoint": "https://api.apitube.io/v1/news/everything",
    "method": "GET",
    "auth": "X-API-Key header (Authorization: Bearer also accepted by vendor)",
    "account": "APITube dashboard News API key. Live keys start with api_live_.",
    "free_plan": {
        "requests_per_day": 100,
        "requests_per_minute": 10,
        "per_page_max": 10,
        "pages_max": 5,
        "body": "200-character preview",
        "documented_embargo_delay": "none documented; free plan is quota/preview limited, not a 24h delay",
    },
    "paid_notes": "Starter per_page 50; Basic+ per_page 250. Redistribution/full-text retention need vendor review.",
    "result_limit_this_adapter": 10,
    "estimated_unit_cost_usd": 0.0,  # free-plan evaluation; paid plans are subscription
    "boot_required": False,
}

EXA_CONTRACT = {
    "provider": "exa",
    "lane": LANE_FAST,
    "env": EXA_API_KEY_ENV,
    "operator_step": f"SET {EXA_API_KEY_ENV} → provider becomes available",
    "endpoint": "https://api.exa.ai/search",
    "method": "POST",
    "auth": "Authorization: Bearer",
    "account": "https://dashboard.exa.ai/api-keys",
    "plan": {
        "signup_credits_usd": 20,
        "monthly_free_credits_usd": 10,
        "search_usd_per_1k": 7.0,
        "extra_result_usd_per_1k": 1.0,
        "num_results_public_max": 100,
        "num_results_this_adapter": 10,
    },
    "unknown_unknown_role": (
        "Neural/auto search for genetics, licensing, partnerships, and "
        "commercialization where the crop name may be absent from the title."
    ),
    "boot_required": False,
}

CATCHALL_CONTRACT = {
    "provider": "newscatcher_catchall",
    "lane": LANE_BACKGROUND,
    "env": [NEWSCATCHER_API_KEY_ENV, CATCHALL_API_KEY_ENV],
    "operator_step": (
        f"SET {NEWSCATCHER_API_KEY_ENV} or {CATCHALL_API_KEY_ENV} "
        "→ scheduled CatchAll recall writes the shared cache; /week consumes it"
    ),
    "endpoint_submit": "https://catchall.newscatcherapi.com/catchAll/submit",
    "endpoint_pull": "https://catchall.newscatcherapi.com/catchAll/pull/{job_id}",
    "auth": "x-api-key / x-api-token",
    "latency": "Base mode typically 10-15 minutes. Not request-time.",
    "mode": "base",
    "cost": "About 10 credits per validated Base record (~$0.10/record in 2026 list pricing).",
    "request_time_week": False,
    "boot_required": False,
}

USPTO_CONTRACT = {
    "provider": "uspto_odp",
    "lane": LANE_REGISTRY,
    "env": USPTO_ODP_KEY_ENV,
    "operator_step": f"SET {USPTO_ODP_KEY_ENV} → ODP berry search becomes live",
    "endpoint": "https://api.uspto.gov/api/v1/patent/applications/search",
    "fallback_without_key": "google_patents_json (public XHR, no USPTO key)",
    "avoid": "Patent Public Search UI automation",
    "boot_required": False,
}

BIGQUERY_CONTRACT = {
    "provider": "google_patents_bigquery",
    "lane": LANE_DATASET,
    "env": PROJECT_ENV,
    "operator_step": (
        f"SET {PROJECT_ENV} and Application Default Credentials "
        "→ bounded BigQuery templates can execute"
    ),
    "tables": [
        "patents-public-data.patents.publications",
        "patents-public-data.google_patents_research.publications",
    ],
    "on_demand_usd_per_tib": 6.25,
    "free_tib_per_month": 1.0,
    "boot_required": False,
}


def activation_status() -> dict[str, Any]:
    """Read-only. Never logs secret values."""
    return {
        "apitube": {**APITUBE_CONTRACT, "available": has_apitube(), "live": has_apitube()},
        "exa": {**EXA_CONTRACT, "available": has_exa(), "live": has_exa()},
        "newscatcher_catchall": {
            **CATCHALL_CONTRACT,
            "available": has_catchall(),
            "live": has_catchall(),
        },
        "perplexity": {
            "provider": "perplexity",
            "lane": LANE_FAST,
            "env": PERPLEXITY_API_KEY_ENV,
            "operator_step": f"SET {PERPLEXITY_API_KEY_ENV} → catch-net available (ENABLE_PERPLEXITY_PULSE to use on /week)",
            "available": has_perplexity(),
            "live": has_perplexity(),
            "boot_required": False,
        },
        "uspto_odp": {**USPTO_CONTRACT, "available": odp_available(), "live": odp_available()},
        "google_patents_bigquery": {
            **BIGQUERY_CONTRACT,
            "available": bigquery_available(),
            "live": bigquery_available(),
        },
    }


def operator_steps() -> list[str]:
    return [
        APITUBE_CONTRACT["operator_step"],
        EXA_CONTRACT["operator_step"],
        CATCHALL_CONTRACT["operator_step"],
        USPTO_CONTRACT["operator_step"],
        BIGQUERY_CONTRACT["operator_step"],
    ]
