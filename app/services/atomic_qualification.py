"""Deterministic scoring for Atomic Evidence extraction gold sets.

The scorer is deliberately closed-book: it compares structured proposals with
human-authored expectations and exact source excerpts.  It never asks another
model to judge a candidate and never writes Evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from app.services.ai_extraction import ExtractionProviderError, OpenAICompatibleExtractionProvider
from app.services.extraction_evaluation import candidate_preview
from app.services.transcript_evidence import ExtractionRequest, TranscriptArtifact


GOLD_SET_CONTRACT_VERSION = "atomic-evidence-gold-set-v1"
DEFAULT_THRESHOLDS = {
    "precision": 0.90,
    "recall": 0.90,
    "atomicity": 0.90,
    "grounding": 1.0,
    "entity_resolution": 0.90,
    "scope_preservation": 0.90,
    "overreach": 1.0,
    "duplication": 0.95,
}
_METRICS = tuple(DEFAULT_THRESHOLDS)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
    "their", "this", "to", "was", "were", "will", "with",
}


class GoldSetContractError(ValueError):
    """A gold-set fixture cannot be scored reproducibly."""


@dataclass(frozen=True)
class GoldProposition:
    proposition_id: str
    statement: str
    exact_excerpts: tuple[str, ...]
    entity_ids: tuple[str, ...]
    geography_ids: tuple[str, ...]
    berry_ids: tuple[str, ...]
    scope: dict[str, Any]
    claim_type: str | None
    required_terms: tuple[str, ...]
    minimum_term_coverage: float
    minimum_statement_f1: float
    start_seconds: float | None = None
    end_seconds: float | None = None


@dataclass(frozen=True)
class ForbiddenProposition:
    rule_id: str
    phrases: tuple[str, ...]
    required_terms: tuple[str, ...]
    severity: str
    reason: str


@dataclass(frozen=True)
class GoldCase:
    case_id: str
    title: str
    source_artifact: dict[str, Any]
    expected_propositions: tuple[GoldProposition, ...]
    forbidden_propositions: tuple[ForbiddenProposition, ...]
    scoring_metadata: dict[str, Any]


@dataclass(frozen=True)
class AtomicGoldSet:
    gold_set_id: str
    version: int
    description: str
    thresholds: dict[str, float]
    cases: tuple[GoldCase, ...]
    source_document: str | None = None
    source_document_sha256: str | None = None


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[\w]+", _normalized(value), flags=re.UNICODE)
        if len(token) >= 2 and token not in _STOPWORDS
    }


def _token_f1(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    precision = overlap / len(a)
    recall = overlap / len(b)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def _ratio(numerator: int | float, denominator: int | float, *, empty: float = 1.0) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else empty


def _only_keys(value: dict[str, Any], allowed: set[str], detail: str) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        raise GoldSetContractError(f"{detail} contains unsupported fields: {extra}")


def _string_list(value: Any, detail: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise GoldSetContractError(f"{detail} must be a string or nonempty string list")
    return tuple(item.strip() for item in value)


def _number(value: Any, detail: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise GoldSetContractError(f"{detail} must be numeric")
    return float(value)


def _source_segments(source: dict[str, Any], detail: str) -> list[dict[str, Any]]:
    segments = source.get("segments")
    if segments is None and isinstance(source.get("text"), str) and source["text"].strip():
        segments = [{"text": source["text"].strip(), "start_seconds": 0.0}]
    if not isinstance(segments, list) or not segments:
        raise GoldSetContractError(f"{detail}.source_artifact requires text or nonempty segments")
    output: list[dict[str, Any]] = []
    prior = -1.0
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise GoldSetContractError(f"{detail}.source_artifact.segments[{index}] must be an object")
        text = segment.get("text")
        start = segment.get("start_seconds")
        end = segment.get("end_seconds")
        source_location = segment.get("source_location")
        if not isinstance(text, str) or not text.strip():
            raise GoldSetContractError(f"{detail}.source_artifact.segments[{index}].text is required")
        if start is not None and (
            not isinstance(start, (int, float)) or isinstance(start, bool) or float(start) < prior
        ):
            raise GoldSetContractError(f"{detail}.source_artifact segment timestamps must be ordered")
        if end is not None and (
            start is None
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or end < start
        ):
            raise GoldSetContractError(f"{detail}.source_artifact.segments[{index}].end_seconds is invalid")
        if source_location is not None and (not isinstance(source_location, str) or not source_location.strip()):
            raise GoldSetContractError(f"{detail}.source_artifact.segments[{index}].source_location is invalid")
        if start is not None:
            prior = float(start)
        output.append({
            "text": text.strip(),
            "start_seconds": float(start) if start is not None else None,
            "end_seconds": float(end) if end is not None else None,
            **({"source_location": source_location.strip()} if isinstance(source_location, str) else {}),
            **({"speaker_label": segment["speaker_label"]} if isinstance(segment.get("speaker_label"), str) else {}),
        })
    return output


def _proposition(raw: Any, detail: str, index: int) -> GoldProposition:
    if not isinstance(raw, dict):
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}] must be an object")
    allowed = {
        "id", "proposition_id", "statement", "proposition", "exact_excerpt", "exact_excerpts",
        "entities", "entity_ids", "geography_ids", "berry_ids", "scope", "claim_type",
        "matching", "start_seconds", "end_seconds", "timestamp",
    }
    _only_keys(raw, allowed, f"{detail}.expected_propositions[{index}]")
    proposition_id = raw.get("id", raw.get("proposition_id"))
    statement = raw.get("statement", raw.get("proposition"))
    if not isinstance(proposition_id, str) or not proposition_id.strip():
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}].id is required")
    if not isinstance(statement, str) or not statement.strip():
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}].statement is required")
    excerpts = raw.get("exact_excerpts", raw.get("exact_excerpt"))
    exact_excerpts = _string_list(excerpts, f"{detail}.expected_propositions[{index}].exact_excerpts")
    if not exact_excerpts:
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}] requires an exact excerpt")
    entities = raw.get("entities", {})
    if entities is None:
        entities = {}
    if not isinstance(entities, dict):
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}].entities must be an object")
    matching = raw.get("matching", {}) or {}
    if not isinstance(matching, dict):
        raise GoldSetContractError(f"{detail}.expected_propositions[{index}].matching must be an object")
    _only_keys(matching, {"required_terms", "minimum_term_coverage", "minimum_statement_f1"}, f"{detail}.matching")
    required_terms = _string_list(matching.get("required_terms"), f"{detail}.matching.required_terms")
    if not required_terms:
        required_terms = tuple(sorted(_tokens(statement)))
    minimum_term_coverage = matching.get("minimum_term_coverage", 0.6)
    minimum_statement_f1 = matching.get("minimum_statement_f1", 0.35)
    for name, value in (("minimum_term_coverage", minimum_term_coverage), ("minimum_statement_f1", minimum_statement_f1)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise GoldSetContractError(f"{detail}.matching.{name} must be between 0 and 1")
    timestamp = raw.get("timestamp", {}) or {}
    if not isinstance(timestamp, dict):
        raise GoldSetContractError(f"{detail}.timestamp must be an object")
    scope = raw.get("scope", {}) or {}
    if not isinstance(scope, dict):
        raise GoldSetContractError(f"{detail}.scope must be an object")
    claim_type = raw.get("claim_type")
    if claim_type is not None and (not isinstance(claim_type, str) or not claim_type.strip()):
        raise GoldSetContractError(f"{detail}.claim_type must be a nonempty string")
    return GoldProposition(
        proposition_id.strip(), statement.strip(), exact_excerpts,
        _string_list(raw.get("entity_ids", entities.get("entity_ids")), f"{detail}.entity_ids"),
        _string_list(raw.get("geography_ids", entities.get("geography_ids")), f"{detail}.geography_ids"),
        _string_list(raw.get("berry_ids", entities.get("berry_ids")), f"{detail}.berry_ids"),
        scope, claim_type.strip() if isinstance(claim_type, str) else None, required_terms,
        float(minimum_term_coverage), float(minimum_statement_f1),
        _number(raw.get("start_seconds", timestamp.get("start_seconds")), f"{detail}.start_seconds"),
        _number(raw.get("end_seconds", timestamp.get("end_seconds")), f"{detail}.end_seconds"),
    )


def _forbidden(raw: Any, detail: str, index: int) -> ForbiddenProposition:
    if not isinstance(raw, dict):
        raise GoldSetContractError(f"{detail}.forbidden_propositions[{index}] must be an object")
    _only_keys(raw, {"id", "rule_id", "statement", "proposition", "phrases", "required_terms", "severity", "reason"}, f"{detail}.forbidden_propositions[{index}]")
    rule_id = raw.get("id", raw.get("rule_id"))
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise GoldSetContractError(f"{detail}.forbidden_propositions[{index}].id is required")
    statement = raw.get("statement", raw.get("proposition"))
    phrases = _string_list(raw.get("phrases", statement), f"{detail}.forbidden_propositions[{index}].phrases")
    terms = _string_list(raw.get("required_terms"), f"{detail}.forbidden_propositions[{index}].required_terms")
    if not phrases and not terms:
        raise GoldSetContractError(f"{detail}.forbidden_propositions[{index}] needs phrases or required_terms")
    severity = raw.get("severity", "critical")
    if severity not in {"critical", "major"}:
        raise GoldSetContractError(f"{detail}.forbidden_propositions[{index}].severity must be critical or major")
    reason = raw.get("reason", "unsupported inference")
    if not isinstance(reason, str) or not reason.strip():
        raise GoldSetContractError(f"{detail}.forbidden_propositions[{index}].reason is required")
    return ForbiddenProposition(rule_id.strip(), phrases, terms, severity, reason.strip())


def load_atomic_gold_set(path: Path) -> AtomicGoldSet:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GoldSetContractError(f"could not read atomic gold set: {exc}") from exc
    if not isinstance(payload, dict):
        raise GoldSetContractError("atomic gold set must be an object")
    _only_keys(payload, {
        "contract_version", "gold_set_id", "benchmark_id", "version", "description",
        "thresholds", "cases", "source_document", "source_document_sha256",
    }, "gold set")
    contract_version = payload.get("contract_version", GOLD_SET_CONTRACT_VERSION)
    if contract_version != GOLD_SET_CONTRACT_VERSION:
        raise GoldSetContractError(f"unsupported gold-set contract version: {contract_version!r}")
    gold_set_id = payload.get("gold_set_id", payload.get("benchmark_id"))
    if not isinstance(gold_set_id, str) or not gold_set_id.strip():
        raise GoldSetContractError("gold_set_id is required")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise GoldSetContractError("gold-set version must be a positive integer")
    description = payload.get("description", "")
    if not isinstance(description, str):
        raise GoldSetContractError("gold-set description must be text")
    thresholds = dict(DEFAULT_THRESHOLDS)
    custom = payload.get("thresholds", {}) or {}
    if not isinstance(custom, dict) or set(custom) - set(_METRICS):
        raise GoldSetContractError("gold-set thresholds contain unsupported metrics")
    for name, value in custom.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            raise GoldSetContractError(f"threshold {name} must be between 0 and 1")
        thresholds[name] = float(value)
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise GoldSetContractError("gold set requires nonempty cases")
    cases: list[GoldCase] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_cases):
        detail = f"cases[{index}]"
        if not isinstance(raw, dict):
            raise GoldSetContractError(f"{detail} must be an object")
        _only_keys(raw, {"id", "case_id", "title", "source_artifact", "expected_propositions", "expected_atomic_propositions", "forbidden_propositions", "entities", "scope", "claim_types", "scoring_metadata"}, detail)
        case_id = raw.get("id", raw.get("case_id"))
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", case_id) or case_id in seen:
            raise GoldSetContractError(f"{detail}.id must be unique lowercase kebab-case")
        seen.add(case_id)
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            raise GoldSetContractError(f"{detail}.title is required")
        source = raw.get("source_artifact")
        if not isinstance(source, dict):
            raise GoldSetContractError(f"{detail}.source_artifact must be an object")
        source = dict(source)
        source["segments"] = _source_segments(source, detail)
        expected_raw = raw.get("expected_propositions", raw.get("expected_atomic_propositions"))
        if not isinstance(expected_raw, list):
            raise GoldSetContractError(f"{detail}.expected_propositions must be a list")
        expected = tuple(_proposition(item, detail, item_index) for item_index, item in enumerate(expected_raw))
        forbidden_raw = raw.get("forbidden_propositions", [])
        if not isinstance(forbidden_raw, list):
            raise GoldSetContractError(f"{detail}.forbidden_propositions must be a list")
        forbidden = tuple(_forbidden(item, detail, item_index) for item_index, item in enumerate(forbidden_raw))
        metadata = raw.get("scoring_metadata", {}) or {}
        if not isinstance(metadata, dict):
            raise GoldSetContractError(f"{detail}.scoring_metadata must be an object")
        cases.append(GoldCase(case_id, title.strip(), source, expected, forbidden, metadata))
    source_document = payload.get("source_document")
    source_sha = payload.get("source_document_sha256")
    if source_document is not None and (not isinstance(source_document, str) or not source_document.strip()):
        raise GoldSetContractError("source_document must be nonempty text")
    if source_sha is not None and (
        not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha)
    ):
        raise GoldSetContractError("source_document_sha256 must be a lowercase SHA-256")
    return AtomicGoldSet(
        gold_set_id.strip(), version, description.strip(), thresholds, tuple(cases),
        source_document.strip() if isinstance(source_document, str) else None,
        source_sha,
    )


def gold_case_transcript(case: GoldCase) -> TranscriptArtifact:
    source = case.source_artifact
    source_id = source.get("id", f"gold-{case.case_id}")
    return TranscriptArtifact.from_dict({
        "transcript_id": f"gold-{case.case_id}",
        "parent_evidence_id": str(source_id),
        "language": source.get("language", "en"),
        "provenance": {"method": "human_provided", "created_by": "Atomic Evidence Gold Set", "created_at": "2026-08-23"},
        # The extraction provider currently consumes TranscriptArtifact windows.
        # Written sources use deterministic transport offsets internally only;
        # run_gold_set_benchmark removes them from persisted proposals and keeps
        # the real field/paragraph locator instead.
        "segments": [
            {
                **segment,
                "start_seconds": segment["start_seconds"] if segment["start_seconds"] is not None else float(index),
                "end_seconds": segment["end_seconds"],
            }
            for index, segment in enumerate(source["segments"])
        ],
    })


def gold_case_parent(case: GoldCase) -> dict[str, Any]:
    source = case.source_artifact
    return {
        "id": str(source.get("id", f"gold-{case.case_id}")),
        "record_type": "evidence", "status": "published", "review_state": "published",
        "evidence_role": "publication_artifact", "title": source.get("title", case.title),
        "source_name": source.get("source_name", "Atomic Evidence Gold Set"),
        "source_url": source.get("source_url", "https://example.invalid/atomic-gold-set"),
        "captured_date": source.get("captured_date", "2026-08-23"),
        "summary": source.get("summary", "Human-curated qualification source artifact."),
        "entity_ids": source.get("entity_ids", []), "geography_ids": source.get("geography_ids", []),
        "berry_ids": source.get("berry_ids", []), "submitted_by": "atomic-gold-set",
    }


def _term_coverage(statement: str, terms: tuple[str, ...]) -> float:
    normalized = _normalized(statement)
    return _ratio(sum(_normalized(term) in normalized for term in terms), len(terms))


def _match_strength(expected: GoldProposition, proposal: dict[str, Any]) -> tuple[float, float, float, bool]:
    statement = str(proposal.get("normalized_statement", ""))
    coverage = _term_coverage(statement, expected.required_terms)
    statement_f1 = _token_f1(statement, expected.statement)
    eligible = coverage >= expected.minimum_term_coverage and statement_f1 >= expected.minimum_statement_f1
    return round((coverage + statement_f1) / 2, 6), coverage, statement_f1, eligible


def _scope_terms(scope: dict[str, Any]) -> tuple[str, ...]:
    value = scope.get("required_terms", [])
    terms = value if isinstance(value, list) else [value]
    return tuple(str(term) for term in terms if str(term).strip())


def _entity_score(expected: GoldProposition, proposal: dict[str, Any]) -> float:
    wanted = set(expected.entity_ids + expected.geography_ids + expected.berry_ids)
    actual = {
        value for field in ("entity_ids", "geography_ids", "berry_ids")
        for value in proposal.get(field, []) if isinstance(value, str)
    }
    if not wanted and not actual:
        return 1.0
    if not wanted or not actual:
        return 0.0
    overlap = len(wanted & actual)
    return round(2 * (overlap / len(actual)) * (overlap / len(wanted)) / ((overlap / len(actual)) + (overlap / len(wanted))), 6) if overlap else 0.0


def _grounding_score(expected: GoldProposition, proposal: dict[str, Any], source_text: str) -> float:
    excerpt = _normalized(str(proposal.get("transcript_excerpt", proposal.get("exact_excerpt", ""))))
    if not excerpt or excerpt not in _normalized(source_text):
        return 0.0
    return 1.0 if any(_normalized(gold) in excerpt or excerpt in _normalized(gold) for gold in expected.exact_excerpts) else 0.0


def _scope_score(expected: GoldProposition, proposal: dict[str, Any]) -> float:
    terms = _scope_terms(expected.scope)
    if not terms:
        return 1.0
    candidate_scope = proposal.get("scope")
    if isinstance(candidate_scope, dict):
        haystack = json.dumps(candidate_scope, ensure_ascii=False, sort_keys=True)
    else:
        haystack = str(proposal.get("normalized_statement", ""))
    return _term_coverage(haystack, terms)


def _forbidden_hits(case: GoldCase, proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for proposal_index, proposal in enumerate(proposals):
        statement = _normalized(str(proposal.get("normalized_statement", "")))
        for rule in case.forbidden_propositions:
            phrase_hit = next((phrase for phrase in rule.phrases if _normalized(phrase) in statement), None)
            term_hit = bool(rule.required_terms) and all(_normalized(term) in statement for term in rule.required_terms)
            if phrase_hit or term_hit:
                hits.append({
                    "proposal_index": proposal_index, "rule_id": rule.rule_id,
                    "severity": rule.severity, "reason": rule.reason,
                    "matched_phrase": phrase_hit, "matched_required_terms": term_hit,
                })
    return hits


def _duplicate_pairs(proposals: list[dict[str, Any]]) -> list[list[int]]:
    pairs: list[list[int]] = []
    for left in range(len(proposals)):
        for right in range(left + 1, len(proposals)):
            a = str(proposals[left].get("normalized_statement", ""))
            b = str(proposals[right].get("normalized_statement", ""))
            union = _tokens(a) | _tokens(b)
            similarity = _ratio(len(_tokens(a) & _tokens(b)), len(union))
            if _normalized(a) == _normalized(b) or similarity >= 0.90:
                pairs.append([left, right])
    return pairs


def score_gold_case(case: GoldCase, proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Score already-normalized proposals without any model judge."""

    strengths: list[tuple[float, int, int, float, float]] = []
    coverage_by_proposal: list[list[str]] = [[] for _ in proposals]
    for expected_index, expected in enumerate(case.expected_propositions):
        for proposal_index, proposal in enumerate(proposals):
            strength, coverage, statement_f1, eligible = _match_strength(expected, proposal)
            if coverage >= expected.minimum_term_coverage:
                coverage_by_proposal[proposal_index].append(expected.proposition_id)
            if eligible:
                strengths.append((strength, expected_index, proposal_index, coverage, statement_f1))
    matches: list[dict[str, Any]] = []
    used_expected: set[int] = set()
    used_proposals: set[int] = set()
    source_text = "\n".join(segment["text"] for segment in case.source_artifact["segments"])
    for strength, expected_index, proposal_index, coverage, statement_f1 in sorted(strengths, key=lambda item: (-item[0], item[1], item[2])):
        if expected_index in used_expected or proposal_index in used_proposals:
            continue
        used_expected.add(expected_index)
        used_proposals.add(proposal_index)
        expected = case.expected_propositions[expected_index]
        proposal = proposals[proposal_index]
        matches.append({
            "expected_id": expected.proposition_id, "expected_index": expected_index,
            "proposal_index": proposal_index, "match_strength": strength,
            "term_coverage": coverage, "statement_token_f1": statement_f1,
            "grounding": _grounding_score(expected, proposal, source_text),
            "entity_resolution": _entity_score(expected, proposal),
            "scope_preservation": _scope_score(expected, proposal),
            "claim_type": expected.claim_type,
        })
    forbidden_hits = _forbidden_hits(case, proposals)
    duplicate_pairs = _duplicate_pairs(proposals)
    combined = [
        {"proposal_index": index, "expected_ids": ids}
        for index, ids in enumerate(coverage_by_proposal) if len(ids) > 1
    ]
    metrics = {
        "precision": _ratio(len(matches), len(proposals), empty=1.0 if not case.expected_propositions else 0.0),
        "recall": _ratio(len(matches), len(case.expected_propositions)),
        "atomicity": _ratio(len(proposals) - len(combined), len(proposals)),
        "grounding": round(sum(match["grounding"] for match in matches) / len(matches), 6) if matches else (1.0 if not case.expected_propositions else 0.0),
        "entity_resolution": round(sum(match["entity_resolution"] for match in matches) / len(matches), 6) if matches else (1.0 if not case.expected_propositions else 0.0),
        "scope_preservation": round(sum(match["scope_preservation"] for match in matches) / len(matches), 6) if matches else (1.0 if not case.expected_propositions else 0.0),
        "overreach": max(0.0, round(1.0 - sum(1.0 if hit["severity"] == "critical" else 0.5 for hit in forbidden_hits) / max(1, len(proposals)), 6)),
        "duplication": max(0.0, round(1.0 - len(duplicate_pairs) / max(1, len(proposals)), 6)),
    }
    return {
        "metrics": metrics,
        "matches": matches,
        "unmatched_expected_ids": [item.proposition_id for index, item in enumerate(case.expected_propositions) if index not in used_expected],
        "unmatched_proposal_indexes": [index for index in range(len(proposals)) if index not in used_proposals],
        "combined_claims": combined,
        "duplicate_pairs": duplicate_pairs,
        "forbidden_hits": forbidden_hits,
        "critical_overreach": any(hit["severity"] == "critical" for hit in forbidden_hits),
    }


def score_gold_set(gold_set: AtomicGoldSet, case_proposals: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    cases = []
    for case in gold_set.cases:
        score = score_gold_case(case, case_proposals.get(case.case_id, []))
        cases.append({"case_id": case.case_id, "title": case.title, **score})
    metric_values = {
        name: round(sum(case["metrics"][name] for case in cases) / len(cases), 6)
        for name in _METRICS
    }
    threshold_results = {name: metric_values[name] >= gold_set.thresholds[name] for name in _METRICS}
    critical_overreach = any(case["critical_overreach"] for case in cases)
    return {
        "gold_set": {
            "id": gold_set.gold_set_id,
            "version": gold_set.version,
            "case_count": len(cases),
            "source_document": gold_set.source_document,
            "source_document_sha256": gold_set.source_document_sha256,
        },
        "scoring_method": "deterministic-token-and-exact-excerpt-v1",
        "metrics": metric_values,
        "thresholds": gold_set.thresholds,
        "threshold_results": threshold_results,
        "critical_overreach": critical_overreach,
        "passed": all(threshold_results.values()) and not critical_overreach,
        "cases": cases,
    }


def run_gold_set_benchmark(provider: OpenAICompatibleExtractionProvider, gold_set: AtomicGoldSet) -> dict[str, Any]:
    proposals_by_case: dict[str, list[dict[str, Any]]] = {}
    raw_outputs: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, str]] = []
    performance: list[dict[str, Any]] = []
    for case in gold_set.cases:
        transcript = gold_case_transcript(case)
        try:
            candidates = provider.extract(ExtractionRequest(transcript=transcript, parent_evidence=gold_case_parent(case)))
            proposals = [candidate_preview(transcript, candidate, provider=provider) for candidate in candidates]
            if case.source_artifact.get("locator_kind") == "written_text":
                for proposal in proposals:
                    proposal["source_locations"] = [
                        case.source_artifact["segments"][index].get("source_location", f"segment[{index}]")
                        for index in proposal["segment_indexes"]
                    ]
                    proposal.pop("start_seconds", None)
                    proposal.pop("end_seconds", None)
        except ExtractionProviderError as exc:
            proposals = []
            failures.append({"case_id": case.case_id, "error": str(exc)})
        proposals_by_case[case.case_id] = proposals
        raw_outputs[case.case_id] = list(getattr(provider, "last_raw_outputs", []))
        metrics = provider.last_run_report.as_dict() if provider.last_run_report else {}
        performance.append({
            "case_id": case.case_id,
            "wall_seconds": metrics.get("elapsed_seconds"),
            "propositions": len(proposals),
            "input_tokens": metrics.get("input_tokens"),
            "output_tokens": metrics.get("output_tokens"),
            "total_tokens": metrics.get("total_tokens"),
            "estimated_cost_usd": metrics.get("estimated_cost_usd"),
        })
    report = score_gold_set(gold_set, proposals_by_case)
    report.update({
        "provider": provider.provenance["provider"], "model": provider.provenance["model"],
        "prompt_version": provider.provenance["prompt_version"],
        "normalized_proposals": proposals_by_case, "raw_model_outputs": raw_outputs,
        "failures": failures, "performance": performance,
        "failure_rate": _ratio(len(failures), len(gold_set.cases), empty=0.0),
    })
    report["passed"] = report["passed"] and not failures
    return report
