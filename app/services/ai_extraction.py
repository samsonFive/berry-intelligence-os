"""OpenAI-compatible model provider for transcript Evidence proposals.

The provider owns model I/O, deterministic context windows, defensive response
parsing, and cross-window deduplication.  It never writes records.  The existing
TranscriptEvidenceExtractionService remains authoritative for Evidence IDs,
timestamps, repository-link validation, provenance, and inbox persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
import re
import time
from typing import Any, Callable
import unicodedata

import httpx

from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact


PROMPT_VERSION = "atomic-ci-v1"
_CANDIDATE_FIELDS = {
    "normalized_statement",
    "segment_indexes",
    "entity_ids",
    "geography_ids",
    "berry_ids",
}


class ExtractionProviderError(RuntimeError):
    """A model run could not produce any safely usable result."""


class ExtractionResponseError(ExtractionProviderError):
    """A model response violated the structured-output contract."""


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value in (None, "") else int(value)


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value in (None, "") else float(value)


@dataclass(frozen=True)
class OpenAICompatibleExtractionConfig:
    base_url: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 120.0
    window_chars: int = 12_000
    overlap_segments: int = 8
    temperature: float = 0.0
    max_candidates_per_window: int = 12
    max_total_candidates: int = 100
    response_format: str = "json_schema"
    max_link_candidates: int = 80

    def __post_init__(self) -> None:
        if not self.base_url.strip() or not self.model.strip():
            raise ValueError("extraction base URL and model are required")
        if self.timeout_seconds <= 0 or self.window_chars < 500:
            raise ValueError("timeout must be positive and window_chars must be at least 500")
        if self.overlap_segments < 0:
            raise ValueError("overlap_segments cannot be negative")
        if self.max_candidates_per_window < 1 or self.max_total_candidates < 1:
            raise ValueError("candidate limits must be positive")
        if self.response_format not in {"json_schema", "json_object"}:
            raise ValueError("response_format must be json_schema or json_object")

    @classmethod
    def from_environment(cls, **overrides: Any) -> "OpenAICompatibleExtractionConfig":
        api_key_env = overrides.pop("api_key_env", "BIOS_EXTRACT_API_KEY")
        values = {
            "base_url": os.environ.get("BIOS_EXTRACT_BASE_URL", ""),
            "model": os.environ.get("BIOS_EXTRACT_MODEL", ""),
            "api_key": os.environ.get(api_key_env) or None,
            "timeout_seconds": _env_float("BIOS_EXTRACT_TIMEOUT_SECONDS", 120.0),
            "window_chars": _env_int("BIOS_EXTRACT_WINDOW_CHARS", 12_000),
            "overlap_segments": _env_int("BIOS_EXTRACT_OVERLAP_SEGMENTS", 8),
            "temperature": _env_float("BIOS_EXTRACT_TEMPERATURE", 0.0),
            "max_candidates_per_window": _env_int("BIOS_EXTRACT_MAX_CANDIDATES", 12),
            "max_total_candidates": _env_int("BIOS_EXTRACT_MAX_TOTAL_CANDIDATES", 100),
            "response_format": os.environ.get("BIOS_EXTRACT_RESPONSE_FORMAT", "json_schema"),
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)


@dataclass(frozen=True)
class TranscriptWindow:
    number: int
    start_index: int
    end_index: int
    segment_indexes: tuple[int, ...]


def build_transcript_windows(
    transcript: TranscriptArtifact, *, max_chars: int, overlap_segments: int
) -> list[TranscriptWindow]:
    """Split on segment boundaries with deterministic segment overlap."""
    if max_chars < 1 or overlap_segments < 0:
        raise ValueError("invalid window settings")
    windows: list[TranscriptWindow] = []
    start = 0
    total = len(transcript.segments)
    while start < total:
        end = start
        used = 0
        while end < total:
            line_size = len(transcript.segments[end].text) + len(str(end)) + 8
            if end > start and used + line_size > max_chars:
                break
            used += line_size
            end += 1
        indexes = tuple(range(start, end))
        windows.append(TranscriptWindow(len(windows), start, end - 1, indexes))
        if end >= total:
            break
        next_start = max(start + 1, end - overlap_segments)
        start = next_start
    return windows


@dataclass(frozen=True)
class ProviderRunReport:
    provider: str
    model: str
    prompt_version: str
    segment_count: int
    window_count: int
    model_calls: int
    candidates_before_validation: int
    invalid_candidates: int
    duplicates_removed: int
    candidates_after_validation: int
    elapsed_seconds: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _statement_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _mentioned(text: str, name: str) -> bool:
    value = name.strip().casefold()
    return len(value) >= 3 and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text) is not None


def _extract_json(content: str) -> dict[str, Any]:
    value = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", value, flags=re.IGNORECASE)
    if fence:
        value = fence.group(1).strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ExtractionResponseError(f"invalid JSON response: {exc.msg}") from exc
    if not isinstance(payload, dict) or set(payload) != {"candidates"}:
        raise ExtractionResponseError("response must be an object containing only candidates")
    if not isinstance(payload["candidates"], list):
        raise ExtractionResponseError("candidates must be an array")
    return payload


def _response_schema(max_candidates: int) -> dict[str, Any]:
    string_ids = {"type": "array", "items": {"type": "string"}}
    return {
        "name": "atomic_ci_candidates",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["candidates"],
            "properties": {
                "candidates": {
                    "type": "array",
                    "maxItems": max_candidates,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": sorted(_CANDIDATE_FIELDS),
                        "properties": {
                            "normalized_statement": {"type": "string"},
                            "segment_indexes": {"type": "array", "items": {"type": "integer"}},
                            "entity_ids": string_ids,
                            "geography_ids": string_ids,
                            "berry_ids": string_ids,
                        },
                    },
                }
            },
        },
    }


class OpenAICompatibleExtractionProvider:
    """Real-model provider using the OpenAI-compatible chat-completions wire contract."""

    method = "ai_assisted"

    def __init__(
        self,
        *,
        config: OpenAICompatibleExtractionConfig,
        repositories: Any,
        post: Callable[..., Any] = httpx.post,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._repos = repositories
        self._post = post
        self._clock = clock
        self.name = f"openai-compatible:{config.model}:{PROMPT_VERSION}"
        self.provenance = {
            "provider": "openai-compatible",
            "model": config.model,
            "prompt_version": PROMPT_VERSION,
        }
        self.last_run_report: ProviderRunReport | None = None

    @property
    def endpoint(self) -> str:
        base = self.config.base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    def extract(self, request: ExtractionRequest) -> list[dict[str, Any]]:
        started = self._clock()
        windows = build_transcript_windows(
            request.transcript,
            max_chars=self.config.window_chars,
            overlap_segments=self.config.overlap_segments,
        )
        allowed = self._allowed_links(request)
        accepted: list[dict[str, Any]] = []
        errors: list[str] = []
        before = invalid = duplicates = calls = 0
        input_tokens = output_tokens = total_tokens = 0
        usage_seen = False

        for window in windows:
            calls += 1
            try:
                payload = self._call(request, window, allowed)
                usage = payload.pop("_usage", {})
                if usage:
                    usage_seen = True
                    input_tokens += int(usage.get("prompt_tokens", 0) or 0)
                    output_tokens += int(usage.get("completion_tokens", 0) or 0)
                    total_tokens += int(usage.get("total_tokens", 0) or 0)
                raw_candidates = payload["candidates"]
                if len(raw_candidates) > self.config.max_candidates_per_window:
                    raise ExtractionResponseError(
                        f"response exceeds {self.config.max_candidates_per_window} candidates for one window"
                    )
                before += len(raw_candidates)
                for candidate_number, raw in enumerate(raw_candidates):
                    try:
                        candidate = self._validate_candidate(raw, window, allowed)
                    except ExtractionResponseError as exc:
                        invalid += 1
                        errors.append(f"window {window.number} candidate {candidate_number}: {exc}")
                        continue
                    if self._is_duplicate(candidate, accepted):
                        duplicates += 1
                        continue
                    if len(accepted) < self.config.max_total_candidates:
                        accepted.append(candidate)
            except (ExtractionProviderError, httpx.HTTPError, TimeoutError) as exc:
                errors.append(f"window {window.number}: {exc}")

        self.last_run_report = ProviderRunReport(
            provider="openai-compatible",
            model=self.config.model,
            prompt_version=PROMPT_VERSION,
            segment_count=len(request.transcript.segments),
            window_count=len(windows),
            model_calls=calls,
            candidates_before_validation=before,
            invalid_candidates=invalid,
            duplicates_removed=duplicates,
            candidates_after_validation=len(accepted),
            elapsed_seconds=round(self._clock() - started, 3),
            input_tokens=input_tokens if usage_seen else None,
            output_tokens=output_tokens if usage_seen else None,
            total_tokens=total_tokens if usage_seen else None,
            errors=tuple(errors),
        )
        if errors and not accepted and len(errors) >= len(windows):
            raise ExtractionProviderError("all extraction windows failed: " + "; ".join(errors))
        return accepted

    def _call(
        self, request: ExtractionRequest, window: TranscriptWindow, allowed: dict[str, dict[str, str]]
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        response_format: dict[str, Any]
        if self.config.response_format == "json_schema":
            response_format = {"type": "json_schema", "json_schema": _response_schema(self.config.max_candidates_per_window)}
        else:
            response_format = {"type": "json_object"}
        body = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "response_format": response_format,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._window_prompt(request, window, allowed)},
            ],
        }
        try:
            response = self._post(self.endpoint, headers=headers, json=body, timeout=self.config.timeout_seconds)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ExtractionProviderError("model request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ExtractionProviderError(f"model HTTP failure ({exc.response.status_code})") from exc
        except httpx.HTTPError as exc:
            raise ExtractionProviderError(f"model transport failure ({type(exc).__name__})") from exc
        try:
            envelope = response.json()
            choice = envelope["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ExtractionResponseError("malformed chat-completions envelope") from exc
        if choice.get("finish_reason") == "length":
            raise ExtractionResponseError("model response was truncated")
        if isinstance(message.get("refusal"), str) and message["refusal"].strip():
            raise ExtractionResponseError("model refused the extraction request")
        if not isinstance(content, str):
            raise ExtractionResponseError("model response content must be text")
        parsed = _extract_json(content)
        parsed["_usage"] = envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
        return parsed

    def _allowed_links(self, request: ExtractionRequest) -> dict[str, dict[str, str]]:
        transcript_text = " ".join(segment.text for segment in request.transcript.segments).casefold()
        parent_ids = set()
        for field_name in ("entity_ids", "geography_ids", "berry_ids"):
            values = request.parent_evidence.get(field_name, [])
            if isinstance(values, list):
                parent_ids.update(value for value in values if isinstance(value, str))
        grouped = {"entity_ids": {}, "geography_ids": {}, "berry_ids": {}}
        for entity in self._repos.entities.list():
            entity_id = entity.get("id")
            name = entity.get("name")
            if not isinstance(entity_id, str) or not isinstance(name, str):
                continue
            aliases = [name] + [value for value in entity.get("aliases", []) if isinstance(value, str)]
            mentioned = any(_mentioned(transcript_text, value) for value in aliases)
            if entity_id not in parent_ids and not mentioned:
                continue
            entity_type = entity.get("entity_type")
            field_name = "geography_ids" if entity_type == "geography" else "berry_ids" if entity_type == "berry" else "entity_ids"
            if len(grouped[field_name]) < self.config.max_link_candidates:
                grouped[field_name][entity_id] = name
        return grouped

    @staticmethod
    def _system_prompt() -> str:
        return f'''You extract atomic competitive-intelligence evidence from machine transcripts.
Prompt version: {PROMPT_VERSION}.
Extract discrete, independently supportable source statements; do not summarize the episode.
Preserve epistemic qualifiers and attribution exactly: plans, expects, believes, may, could,
approximately, potentially, and speaker opinion must never become stronger factual language.
You are recording what the source says, not deciding whether it is objectively true.
Use no outside knowledge. Skip corrupted or uncertain transcript passages, especially numbers.
Split independent claims. Greetings, advertisements, and casual discussion may yield zero candidates.
Use only exact global segment indexes shown in the transcript window, in contiguous ascending order.
Use only supplied repository IDs; an unlinked claim is preferable to an invented link.
Never return timestamps, Evidence IDs, provenance, source IDs, review state, Facts, Relationships,
Assessments, or Recommendations. Return only the required JSON object.
Negative examples: "We haven't announced any expansion plans" does not support "Company plans to expand."
"Some people have suggested demand may increase" does not support "Demand is increasing."'''

    def _window_prompt(
        self, request: ExtractionRequest, window: TranscriptWindow, allowed: dict[str, dict[str, str]]
    ) -> str:
        lines = []
        for index in window.segment_indexes:
            segment = request.transcript.segments[index]
            speaker = f" {segment.speaker_label}:" if segment.speaker_label else ""
            lines.append(f"[{index}]{speaker} {segment.text}")
        allowed_json = json.dumps(allowed, ensure_ascii=False, sort_keys=True)
        return (
            f"Publication title: {request.parent_evidence.get('title', '')}\n"
            f"Language: {request.transcript.language}\n"
            f"Allowed repository IDs by output field: {allowed_json}\n"
            f"Maximum candidates: {self.config.max_candidates_per_window}\n"
            "Candidate shape: normalized_statement, segment_indexes, entity_ids, geography_ids, berry_ids.\n"
            "Potential CI subjects include volume, acreage, yield, supply, demand, pricing, preference, "
            "cultivar adoption or launch, breeding, grower behavior, investment, capacity, geography, "
            "market entry or exit, partnerships, M&A, regulation, climate, strategy, technology, and constraints.\n"
            "Transcript window:\n" + "\n".join(lines)
        )

    def _validate_candidate(
        self, raw: Any, window: TranscriptWindow, allowed: dict[str, dict[str, str]]
    ) -> dict[str, Any]:
        if not isinstance(raw, dict) or set(raw) != _CANDIDATE_FIELDS:
            raise ExtractionResponseError("candidate fields do not match the contract")
        statement = raw["normalized_statement"]
        indexes = raw["segment_indexes"]
        if not isinstance(statement, str) or not statement.strip():
            raise ExtractionResponseError("normalized_statement must be nonempty text")
        if (
            not isinstance(indexes, list)
            or not indexes
            or any(not isinstance(value, int) or isinstance(value, bool) for value in indexes)
            or indexes != sorted(set(indexes))
            or indexes != list(range(indexes[0], indexes[-1] + 1))
            or any(value not in window.segment_indexes for value in indexes)
        ):
            raise ExtractionResponseError("segment_indexes must be contiguous indexes from this window")
        candidate = {"normalized_statement": " ".join(statement.strip().split()), "segment_indexes": indexes}
        for field_name in ("entity_ids", "geography_ids", "berry_ids"):
            values = raw[field_name]
            if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                raise ExtractionResponseError(f"{field_name} must be a string array")
            if len(values) != len(set(values)) or any(value not in allowed[field_name] for value in values):
                raise ExtractionResponseError(f"{field_name} contains an unsupported repository ID")
            candidate[field_name] = values
        return candidate

    @staticmethod
    def _is_duplicate(candidate: dict[str, Any], accepted: list[dict[str, Any]]) -> bool:
        candidate_indexes = set(candidate["segment_indexes"])
        key = _statement_key(candidate["normalized_statement"])
        return any(
            key == _statement_key(existing["normalized_statement"])
            and bool(candidate_indexes.intersection(existing["segment_indexes"]))
            for existing in accepted
        )
