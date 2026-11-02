"""Explicit, resumable deep research. Never used by browse or extraction.

Provider contract rechecked November 2, 2026 against the Agent API effort
and background documentation. Medium remains the general research default;
Learn explicitly selects high for deep, source-heavy research.
"""
from dataclasses import asdict, dataclass
import re
from urllib.parse import urlsplit

import httpx

from app.services.ai_gateway.perplexity_agent import (
    DEFAULT_PERPLEXITY_AGENT_BASE_URL, agent_auth_headers,
    extract_output_text, normalize_responses_usage,
)

CONFIG = {"provider": "perplexity", "endpoint": DEFAULT_PERPLEXITY_AGENT_BASE_URL,
          "effort": "medium", "background": True, "max_steps": 15,
          "max_output_tokens": 6000, "prompt_version": "learn-deep-v1"}
STATUSES = {"queued", "in_progress", "completed", "failed", "cancelled", "incomplete", "cancelling"}


class ResearchError(ValueError):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def submission_configuration(saved=None):
    """Translate historical preset snapshots without changing saved history.

    Only our bounded research profiles are accepted. Runtime metadata cannot
    change the destination or silently select a more expensive research level.
    """
    saved = CONFIG if saved is None else saved
    if not isinstance(saved, dict):
        raise ResearchError("Saved research settings are unavailable. No request was sent.")
    effort = saved.get("effort") or saved.get("preset")
    if (saved.get("provider") != "perplexity" or saved.get("endpoint") != CONFIG["endpoint"]
            or not isinstance(effort, str) or effort not in {"medium", "high"} or saved.get("background") is not True
            or type(saved.get("max_steps")) is not int or not 1 <= saved["max_steps"] <= 15
            or type(saved.get("max_output_tokens")) is not int or not 1 <= saved["max_output_tokens"] <= 6000
            or not isinstance(saved.get("prompt_version"), str) or not 1 <= len(saved["prompt_version"]) <= 150):
        raise ResearchError("Saved research settings are unsupported. No request was sent.")
    return {key: saved[key] for key in ("provider", "endpoint", "background", "max_steps", "max_output_tokens", "prompt_version")} | {"effort": effort}


def safe_url(value):
    if not isinstance(value, str) or len(value) > 3000:
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme in {"https", "http"} and parts.hostname and not parts.username and not parts.password:
            return value
    except ValueError:
        pass
    return ""


def normalize(envelope):
    if not isinstance(envelope, dict):
        raise ResearchError("The research service returned an unreadable result.", uncertain=True)
    key = envelope.get("id") or envelope.get("response_id")
    status = envelope.get("status")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,180}", key) or status not in STATUSES:
        raise ResearchError("The research service did not return a usable run reference.", uncertain=True)
    output = envelope.get("output") or []
    citations, seen = [], {}
    # Only provider tool results and native citation annotations are provenance.
    # A URL invented inside generated prose is never promoted to a citation.
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        candidates = list(item.get("results") or []) if isinstance(item.get("results"), list) else []
        content = item.get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict):
                annotations = block.get("annotations")
                candidates += [a for a in annotations if isinstance(a, dict) and a.get("type") == "url_citation"] if isinstance(annotations, list) else []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate = candidate.get("url_citation", candidate)
            url = safe_url(candidate.get("url")) if isinstance(candidate, dict) else ""
            if url:
                source_id = candidate.get("id")
                tag = "web:" + str(source_id) if isinstance(source_id, int) and not isinstance(source_id, bool) and 0 < source_id < 100000 else ""
                if url not in seen:
                    seen[url] = {"url": url, "title": str(candidate.get("title") or url)[:500], "reference_ids": []}
                    citations.append(seen[url])
                if tag and tag not in seen[url]["reference_ids"]:
                    seen[url]["reference_ids"].append(tag)
    return {"provider_id": key, "provider_status": status,
            "text": (extract_output_text(output) or "") if isinstance(output, list) else "",
            "citations": citations, "model": str(envelope.get("model") or "")[:150],
            "reported_effort": envelope["effort"][:150] if isinstance(envelope.get("effort"), str) else "",
            "usage": asdict(normalize_responses_usage(envelope.get("usage")))}


@dataclass
class DeepResearchClient:
    api_key: str
    post: object = httpx.post
    get: object = httpx.get
    configuration: dict | None = None

    def _request(self, method, url, *, body=None, submitting=False):
        try:
            kwargs = {"headers": agent_auth_headers(self.api_key), "timeout": 30.0}
            if body is not None:
                kwargs["json"] = body
            response = method(url, **kwargs)
        except httpx.HTTPError as exc:
            # Submission uncertainty cannot safely be resolved with another POST.
            raise ResearchError("The research service could not be reached. Check this run before starting another.", uncertain=submitting) from exc
        if response.status_code >= 400:
            message = "The research service could not complete this request."
            if response.status_code in {401, 403}:
                message = "Research access is unavailable. Check the configured provider credentials."
            elif response.status_code == 429:
                message = "The research service is busy. Try checking the run again later."
            # Never persist a provider error body, which may echo secrets or input.
            raise ResearchError(message, uncertain=submitting and response.status_code >= 500)
        try:
            return normalize(response.json())
        except (ValueError, TypeError) as exc:
            if isinstance(exc, ResearchError):
                raise
            raise ResearchError("The research service returned an unreadable result.", uncertain=submitting) from exc

    def start(self, prompt):
        configuration = submission_configuration(self.configuration)
        return self._request(self.post, CONFIG["endpoint"], body={
            key: configuration[key] for key in ("effort", "background", "max_steps", "max_output_tokens")
        } | {"input": prompt}, submitting=True)

    def check(self, provider_id):
        return self._request(self.get, self._run_url(provider_id))

    def cancel(self, provider_id):
        return self._request(self.post, self._run_url(provider_id) + "/cancel")

    @staticmethod
    def _run_url(provider_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,180}", provider_id):
            raise ResearchError("The research run reference is unavailable.")
        return CONFIG["endpoint"] + "/" + provider_id
