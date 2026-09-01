"""Scan trusted/public corpus for explicit Variety/cultivar identities.

Never writes data/entities. Never promotes trusted Varieties. Never scans
article bodies for capitalized words. Prefers structured fields, then
registry/index records, then the existing patent cultivar-name extractor.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.patent_monitor.normalize import extract_cultivar_name
from app.services.variety_universe.identity import (
    STATE_POSSIBLE_ALIAS,
    STATE_UNKNOWN,
    fold_identity,
    resolve_identity,
)
from app.services.variety_universe.registry_import import build_candidate

REGISTRY_SOURCE_TYPES = {
    "government_registry",
    "plant_breeders_rights_record",
    "patent_record",
    "patent",
    "patent_aggregator",
}
REGISTRY_TAGS = {"cultivar-registry", "registry", "government-registry"}
PUBLISHED = {"published"}
ACTIVE_FACTS = {"active"}

# Parentage/selection tokens, not cultivar identities we should promote.
_PARENTAGE_HINTS = (
    "parentage",
    "crossed with",
    "origin is given as",
    "seedling of",
    "open-pollinated",
)
_STOP_FOLDS = {
    "canada",
    "california",
    "united states",
    "portugal",
    "australia",
    "florida",
    "spain",
    "inc",
    "llc",
    "usda",
    "cfia",
    "cpvo",
    "driscoll s",
    "santa cruz county",
    "hillsborough county",
    "watsonville",
    "february",
    "april",
    "november",
    "certificate",
    "application",
    "michigan state",
    "usda public varieties",
    "fall creek entries",
    "food research entries",
    "new zealand plant",
    "the ozblu",
    "parentage",
    "origin",
}

_QUOTED_SUBJECT_RE = re.compile(
    r"(?:blueberry |strawberry |raspberry |blackberry )?(?:variety|cultivar|denomination)\s+['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”]",
    re.IGNORECASE,
)
_TRADE_NAME_RE = re.compile(
    r"trade name\s+([A-Z][A-Za-z0-9][A-Za-z0-9'’\-]*(?:\s+[A-Z][A-Za-z0-9'’\-]*){0,3})",
)
_TRADE_NAMES_INCLUDING_RE = re.compile(
    r"trade names including\s+(.+?)(?:,?\s+together with|,?\s+alongside|\.|$)",
    re.IGNORECASE,
)
_CULTIVARS_ONLY_RE = re.compile(
    r"cultivars only[:\s]+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
_TRADED_DENOMINATIONS_RE = re.compile(
    r"that\s+(.+?)\s+are all traded denominations",
    re.IGNORECASE,
)
_APPLICATION_FOR_RE = re.compile(
    r"(?:application|for)\s+['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”]",
    re.IGNORECASE,
)
_COMPARISON_VARIETIES_RE = re.compile(
    r"['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”](?:\s+and\s+['‘’\"“”]([^'‘’\"“”]+)['‘’\"“”])?\s+as comparison varieties",
    re.IGNORECASE,
)
_NAME_CODE_PAIR_RE = re.compile(
    r"([A-Z][A-Za-z0-9][A-Za-z0-9'’\-]*(?:\s+[A-Z][A-Za-z0-9'’\-]*){0,3})\s+['‘’\"“”]([A-Za-z0-9][A-Za-z0-9.\-]+)['‘’\"“”]"
)
_OWNER_DENOMINATIONS_RE = re.compile(
    r"([A-Z][A-Za-z0-9'’&.\-]+(?:\s+[A-Z][A-Za-z0-9'’&.\-]+){0,4})'s\s+(?:blueberry |strawberry |raspberry |blackberry )?(?:denominations|cultivars|varieties)",
    re.IGNORECASE,
)
_SPLIT_LIST_RE = re.compile(r"\s*(?:,|;|\band\b)\s*", re.IGNORECASE)
_PARENTAGE_CODE_RE = re.compile(r"^(?=.*\d)[A-Za-z0-9]{1,6}(?:[ \-][A-Za-z0-9]{1,6}){0,3}$")
_DENOMINATION_CODE_RE = re.compile(
    r"(?i)^(dris|pla|ridley|fc|fcm|ns|bb|fl|eb|th|zf|bk)"
)
LAUNCH_TITLE_SOURCE_TYPES = {
    "news_search",
    "trade_press",
    "company_press_release",
}
_LAUNCH_TITLE_RE = re.compile(
    r"(?i)\b(?:launches?|introduces?|unveils?|releases?)\s+"
    r"(?:the\s+|its\s+|a\s+|an\s+)?"
    r"([A-Z][A-Za-z0-9'’\-]+(?:\s+[A-Z][A-Za-z0-9'’\-]+){0,3})\s+"
    r"(?:blueberry|strawberry|raspberry|blackberry)\s+variet"
)
_NEW_NAMED_VARIETY_TITLE_RE = re.compile(
    r"(?i)\bnew\s+(?:blueberry|strawberry|raspberry|blackberry)\s+"
    r"(?:variety|cultivar)\s+"
    r"([A-Z][A-Za-z0-9'’\-]+(?:\s+[A-Z][A-Za-z0-9'’\-]+){0,3})"
)
_TITLE_STOP_FOLDS = {
    "two",
    "new",
    "its",
    "the",
    "first",
    "latest",
    "another",
    "several",
    "multiple",
}


def _active_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("status") in ACTIVE_FACTS and row.get("classification") == "fact"]


def _berries(record: dict[str, Any]) -> list[str]:
    berries = [str(item) for item in (record.get("berry_ids") or []) if item]
    berry = str(record.get("berry_id") or "").strip()
    if berry and berry not in berries:
        berries.append(berry)
    return berries


def _is_registry_source(evidence: dict[str, Any]) -> bool:
    if evidence.get("source_type") in REGISTRY_SOURCE_TYPES:
        return True
    tags = {str(tag).casefold() for tag in (evidence.get("tags") or [])}
    return bool(tags & {tag.casefold() for tag in REGISTRY_TAGS})


def _parentage_window(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 80) : min(len(text), end + 20)].casefold()
    return any(hint in window for hint in _PARENTAGE_HINTS)


def _looks_like_parentage_code(name: str) -> bool:
    compact = name.strip()
    if not compact:
        return True
    if _DENOMINATION_CODE_RE.match(compact):
        return False
    return bool(_PARENTAGE_CODE_RE.match(compact))


def _clean_name(name: str) -> str:
    text = (name or "").strip(" .;:,").strip("'\"‘’“”")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(?:the|a|an)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^[\-–—]+\s*", "", text)
    return text


def _is_stop_name(name: str, blocked_folds: set[str]) -> bool:
    folded = fold_identity(name)
    if len(folded) < 3:
        return True
    if folded in _STOP_FOLDS or folded in blocked_folds:
        return True
    if folded in {"including", "together", "additional", "entries", "programme", "varieties"}:
        return True
    return False


def _split_name_list(blob: str) -> list[str]:
    names: list[str] = []
    for part in _SPLIT_LIST_RE.split(blob or ""):
        cleaned = _clean_name(part)
        cleaned = re.sub(r"^(?:together with|alongside|including)\s+", "", cleaned, flags=re.IGNORECASE)
        if cleaned:
            names.append(cleaned)
    return names


def _blocked_folds(entities: list[dict[str, Any]]) -> set[str]:
    blocked: set[str] = set()
    for entity in entities:
        if entity.get("entity_type") not in {"company", "geography", "berry", "person", "source", "breeding_program", "retailer"}:
            continue
        for value in [entity.get("name"), *(entity.get("aliases") or [])]:
            folded = fold_identity(str(value or ""))
            if len(folded) >= 4:
                blocked.add(folded)
    return blocked


def _canonical_index(varieties: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for variety in varieties:
        vid = str(variety.get("id") or "")
        if not vid:
            continue
        for value in [variety.get("name"), *(variety.get("aliases") or [])]:
            folded = fold_identity(str(value or ""))
            if len(folded) >= 3:
                index.setdefault(folded, vid)
        attrs = variety.get("attributes") or {}
        for key in ("trade_name", "commercial_name", "denomination", "selection_code", "breeder_code"):
            folded = fold_identity(str(attrs.get(key) or ""))
            if len(folded) >= 3:
                index.setdefault(folded, vid)
    return index


def _candidate_index(candidates: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for row in candidates:
        if row.get("status") == "rejected":
            continue
        berry = str(row.get("berry_id") or (row.get("berry_ids") or [""])[0] or "")
        folded = fold_identity(str(row.get("candidate_name") or ""))
        if folded:
            index[f"{folded}|{berry}"] = str(row.get("id") or "")
    return index


def _mention(
    *,
    name: str,
    berry_id: str,
    kind: str,
    evidence: dict[str, Any] | None,
    fact: dict[str, Any] | None,
    breeder_owner: str = "",
    context: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = evidence or {}
    payload = {
        "candidate_name": name,
        "berry_id": berry_id,
        "berry_ids": [berry_id] if berry_id else [],
        "mention_kind": kind,
        "mention_context": context or "",
        "evidence_id": record.get("id") or "",
        "fact_id": (fact or {}).get("id") or "",
        "source_id": record.get("source_id") or record.get("id") or "",
        "source_type": record.get("source_type") or "",
        "source_tier": "tier_1_registry" if _is_registry_source(record) else "",
        "source_label": record.get("source_name") or record.get("source_id") or "",
        "source_url": record.get("source_url") or "",
        "published_date": record.get("published_date") or "",
        "breeder_owner": breeder_owner,
        "jurisdiction": "",
    }
    if extra:
        payload.update(extra)
    return payload


_BERRY_LABELS = {
    "blueberry": "berry-blueberry",
    "strawberry": "berry-strawberry",
    "raspberry": "berry-raspberry",
    "blackberry": "berry-blackberry",
}


def _berry_from_text(text: str, fallback: str) -> str:
    match = re.search(
        r"\b(blueberry|strawberry|raspberry|blackberry)\s+(?:cultivar|variety|denomination)",
        text or "",
        re.IGNORECASE,
    )
    if match:
        return _BERRY_LABELS[match.group(1).lower()]
    return fallback


def _extract_from_text(
    text: str,
    *,
    berry_id: str,
    evidence: dict[str, Any] | None,
    fact: dict[str, Any] | None,
    blocked: set[str],
    allow_lists: bool,
    allow_code_pairs: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mentions: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    berry_id = _berry_from_text(text, berry_id)
    breeder = ""
    owner_match = _OWNER_DENOMINATIONS_RE.search(text or "")
    if owner_match:
        breeder = _clean_name(owner_match.group(1))

    def consider(name: str, kind: str, start: int = 0, end: int = 0, extra: dict[str, Any] | None = None) -> None:
        cleaned = _clean_name(name)
        if not cleaned:
            return
        if _parentage_window(text, start, end or start):
            exclusions.append({"name": cleaned, "reason": "parentage_context", "kind": kind})
            return
        if _looks_like_parentage_code(cleaned):
            exclusions.append({"name": cleaned, "reason": "parentage_or_selection_code", "kind": kind})
            return
        if _is_stop_name(cleaned, blocked):
            exclusions.append({"name": cleaned, "reason": "not_a_variety", "kind": kind})
            return
        if re.search(r"\b(including|entries|selection codes|public varieties|together with)\b", cleaned, re.IGNORECASE):
            exclusions.append({"name": cleaned, "reason": "not_a_variety", "kind": kind})
            return
        if re.search(r"['\"‘’].*\s", cleaned) or re.search(r"\s['\"‘’]", cleaned):
            exclusions.append({"name": cleaned, "reason": "not_a_variety", "kind": kind})
            return
        mentions.append(
            _mention(
                name=cleaned,
                berry_id=berry_id,
                kind=kind,
                evidence=evidence,
                fact=fact,
                breeder_owner=breeder,
                context=text[:240],
                extra=extra,
            )
        )

    for match in _QUOTED_SUBJECT_RE.finditer(text or ""):
        consider(match.group(1), "quoted_cultivar", match.start(), match.end())
    for match in _TRADE_NAME_RE.finditer(text or ""):
        consider(match.group(1), "trade_name", match.start(), match.end())
    cultivar = extract_cultivar_name(text or "")
    if cultivar:
        consider(cultivar, "patent_cultivar_extractor")

    if allow_lists:
        for match in _TRADE_NAMES_INCLUDING_RE.finditer(text or ""):
            for name in _split_name_list(match.group(1)):
                consider(name, "trade_name_list", match.start(), match.end())
        for match in _CULTIVARS_ONLY_RE.finditer(text or ""):
            for name in _split_name_list(match.group(1)):
                consider(name, "cultivar_list", match.start(), match.end())
        for match in _TRADED_DENOMINATIONS_RE.finditer(text or ""):
            for name in _split_name_list(match.group(1)):
                consider(name, "traded_denomination_list", match.start(), match.end())
        for match in _COMPARISON_VARIETIES_RE.finditer(text or ""):
            for group in match.groups():
                if group:
                    consider(group, "comparison_variety", match.start(), match.end())
        for match in _APPLICATION_FOR_RE.finditer(text or ""):
            consider(match.group(1), "registry_application_denomination", match.start(), match.end())
    if allow_code_pairs:
        for match in _NAME_CODE_PAIR_RE.finditer(text or ""):
            code = match.group(2)
            if not re.search(r"\d", code):
                exclusions.append({"name": _clean_name(match.group(1)), "reason": "not_a_variety", "kind": "registry_name_code_pair"})
                continue
            consider(
                match.group(1),
                "registry_name_code_pair",
                match.start(),
                match.end(),
                extra={"breeder_code": code, "denomination": _clean_name(match.group(1))},
            )

    return mentions, exclusions


def _extract_launch_titles(
    evidence: dict[str, Any],
    *,
    berry_id: str,
    blocked: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Title-only launch/denomination patterns. Never scans article bodies."""
    mentions: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    if evidence.get("source_type") not in LAUNCH_TITLE_SOURCE_TYPES:
        return mentions, exclusions
    title = str(evidence.get("title") or "")
    if not title:
        return mentions, exclusions
    berry_id = _berry_from_text(title, berry_id)
    seen: set[str] = set()
    for regex, kind in (
        (_LAUNCH_TITLE_RE, "launch_title"),
        (_NEW_NAMED_VARIETY_TITLE_RE, "new_named_variety_title"),
    ):
        for match in regex.finditer(title):
            cleaned = _clean_name(match.group(1))
            folded = fold_identity(cleaned)
            if not cleaned or folded in seen:
                continue
            seen.add(folded)
            if folded in _TITLE_STOP_FOLDS or _is_stop_name(cleaned, blocked):
                exclusions.append({"name": cleaned, "reason": "not_a_variety", "kind": kind})
                continue
            if _looks_like_parentage_code(cleaned):
                exclusions.append({"name": cleaned, "reason": "parentage_or_selection_code", "kind": kind})
                continue
            mentions.append(
                _mention(
                    name=cleaned,
                    berry_id=berry_id,
                    kind=kind,
                    evidence=evidence,
                    fact=None,
                    context=title,
                )
            )
    return mentions, exclusions


def _explicit_variety_ids(
    record: dict[str, Any],
    variety_ids: set[str],
) -> tuple[list[str], list[str]]:
    found: list[str] = []
    missing: list[str] = []
    for eid in record.get("entity_ids") or []:
        text = str(eid)
        if not text.startswith("variety-"):
            continue
        if text in variety_ids:
            found.append(text)
        else:
            missing.append(text)
    return found, missing


def discover_corpus_variety_mentions(
    *,
    varieties: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    existing_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return explicit cultivar mentions and how they resolve. Read-only."""

    evidence = [row for row in published_evidence if row.get("status") in PUBLISHED]
    evidence_by_id = {str(row["id"]): row for row in evidence if row.get("id")}
    facts_in = _active_facts(facts)
    variety_ids = {str(v["id"]) for v in varieties if v.get("id")}
    blocked = _blocked_folds(entities)
    canonical = _canonical_index(varieties)
    existing = existing_candidates or []
    already_candidate = _candidate_index(existing)

    mentions: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    already_canonical_ids: list[str] = []
    missing_variety_ids: list[str] = []

    def berry_for(record: dict[str, Any], fallback: dict[str, Any] | None = None) -> str:
        berries = _berries(record) or (_berries(fallback) if fallback else [])
        return berries[0] if berries else ""

    # 1. Explicit Variety IDs on trusted records.
    for record in [*evidence, *facts_in]:
        found, missing = _explicit_variety_ids(record, variety_ids)
        already_canonical_ids.extend(found)
        missing_variety_ids.extend(missing)
        for missing_id in missing:
            exclusions.append(
                {
                    "name": missing_id,
                    "reason": "unresolved_variety_id",
                    "record_id": record.get("id"),
                }
            )

    # 2. Structured named entities / extraction metadata.
    for record in evidence:
        berry_id = berry_for(record)
        for suggestion in record.get("entity_link_suggestions") or []:
            if suggestion.get("role") != "variety":
                continue
            name = _clean_name(str(suggestion.get("name") or ""))
            if not name:
                continue
            if suggestion.get("match_status") == "matched" and suggestion.get("match_entity_id") in variety_ids:
                already_canonical_ids.append(str(suggestion["match_entity_id"]))
                continue
            if _is_stop_name(name, blocked):
                exclusions.append({"name": name, "reason": "not_a_variety", "kind": "entity_link_suggestion"})
                continue
            mentions.append(
                _mention(
                    name=name,
                    berry_id=berry_id,
                    kind="entity_link_suggestion",
                    evidence=record,
                    fact=None,
                )
            )
        filing = record.get("patent_filing") or {}
        cultivar = str(filing.get("cultivar_name") or "").strip()
        if cultivar:
            mentions.append(
                _mention(
                    name=_clean_name(cultivar),
                    berry_id=berry_id,
                    kind="patent_filing_cultivar_name",
                    evidence=record,
                    fact=None,
                    extra={"denomination": cultivar},
                )
            )
        observation = record.get("commercial_observation") or {}
        obs_name = str(observation.get("variety_name") or observation.get("brand") or "").strip()
        if observation.get("variety_entity_id") in variety_ids:
            already_canonical_ids.append(str(observation["variety_entity_id"]))
        elif obs_name and not observation.get("variety_entity_id"):
            # Brand-only listings are not cultivar identities.
            if observation.get("variety_name"):
                mentions.append(
                    _mention(
                        name=_clean_name(obs_name),
                        berry_id=berry_id,
                        kind="commercial_observation_variety_name",
                        evidence=record,
                        fact=None,
                    )
                )

    # 3–5. Facts typed around cultivar/variety identity, then registry sources.
    # Text extraction is limited to those records; never general article bodies.
    for fact in facts_in:
        linked = [evidence_by_id[eid] for eid in (fact.get("evidence_ids") or []) if eid in evidence_by_id]
        registry_linked = any(_is_registry_source(row) for row in linked)
        statement = str(fact.get("statement") or "")
        cultivar_fact = bool(
            re.search(r"\b(cultivar|variety|denomination|trade name)\b", statement, re.IGNORECASE)
        )
        if not (registry_linked or cultivar_fact):
            continue
        evidence_row = linked[0] if linked else None
        berry_id = berry_for(evidence_row or {}, fact)
        allow_lists = registry_linked or bool(_TRADE_NAMES_INCLUDING_RE.search(statement) or _CULTIVARS_ONLY_RE.search(statement))
        found, excluded = _extract_from_text(
            statement,
            berry_id=berry_id,
            evidence=evidence_row,
            fact=fact,
            blocked=blocked,
            allow_lists=allow_lists,
            allow_code_pairs=registry_linked,
        )
        mentions.extend(found)
        exclusions.extend(excluded)

    for record in evidence:
        if not _is_registry_source(record):
            continue
        berry_id = berry_for(record)
        haystack = " ".join(
            str(record.get(key) or "") for key in ("title", "summary")
        )
        found, excluded = _extract_from_text(
            haystack,
            berry_id=berry_id,
            evidence=record,
            fact=None,
            blocked=blocked,
            allow_lists=True,
            allow_code_pairs=True,
        )
        mentions.extend(found)
        exclusions.extend(excluded)

    for record in evidence:
        berry_id = berry_for(record)
        found, excluded = _extract_launch_titles(record, berry_id=berry_id, blocked=blocked)
        mentions.extend(found)
        exclusions.extend(excluded)

    # Deduplicate mentions by folded name + berry, merging provenance.
    merged: dict[str, dict[str, Any]] = {}
    for mention in mentions:
        name = _clean_name(str(mention.get("candidate_name") or ""))
        if not name or _is_stop_name(name, blocked):
            exclusions.append({"name": name, "reason": "not_a_variety", "kind": mention.get("mention_kind")})
            continue
        mention["candidate_name"] = name
        berry = str(mention.get("berry_id") or "")
        key = f"{fold_identity(name)}|{berry}"
        current = merged.get(key)
        if current is None:
            mention["evidence_ids"] = [eid for eid in [mention.get("evidence_id")] if eid]
            mention["fact_ids"] = [fid for fid in [mention.get("fact_id")] if fid]
            merged[key] = mention
            continue
        for field in ("evidence_id", "fact_id", "source_url", "breeder_owner", "breeder_code"):
            if mention.get(field) and not current.get(field):
                current[field] = mention[field]
        if mention.get("evidence_id") and mention["evidence_id"] not in current["evidence_ids"]:
            current["evidence_ids"].append(mention["evidence_id"])
        if mention.get("fact_id") and mention["fact_id"] not in current["fact_ids"]:
            current["fact_ids"].append(mention["fact_id"])

    already_canonical: list[dict[str, Any]] = []
    already_candidate_rows: list[dict[str, Any]] = []
    new_mentions: list[dict[str, Any]] = []
    possible_aliases: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for key, mention in merged.items():
        folded = fold_identity(mention["candidate_name"])
        berry = str(mention.get("berry_id") or "")
        canonical_id = canonical.get(folded)
        if canonical_id:
            variety = next((row for row in varieties if row.get("id") == canonical_id), None)
            variety_berries = set(_berries(variety or {}))
            if not berry or not variety_berries or berry in variety_berries:
                mention["disposition"] = "already_canonical"
                mention["canonical_variety_id"] = canonical_id
                already_canonical.append(mention)
                continue
            mention["disposition"] = "berry_mismatch"
            exclusions.append(
                {
                    "name": mention["candidate_name"],
                    "reason": "berry_mismatch",
                    "canonical_variety_id": canonical_id,
                    "mention_berry": berry,
                }
            )
            continue
        if key in already_candidate:
            mention["disposition"] = "already_candidate"
            mention["existing_candidate_id"] = already_candidate[key]
            already_candidate_rows.append(mention)
            continue
        resolution = resolve_identity(mention, varieties)
        mention["identity_state"] = resolution["identity_state"]
        mention["candidate_canonical_match"] = resolution["candidate_canonical_match"]
        mention["match_reason"] = resolution["match_reason"]
        if resolution["identity_state"] == STATE_POSSIBLE_ALIAS:
            mention["disposition"] = "possible_alias"
            possible_aliases.append(mention)
        elif resolution["identity_state"] == STATE_UNKNOWN:
            mention["disposition"] = "unresolved"
            unresolved.append(mention)
        else:
            mention["disposition"] = "new_candidate"
        new_mentions.append(mention)

    return {
        "mentions": list(merged.values()),
        "mention_count": len(merged),
        "already_canonical": already_canonical,
        "already_candidate": already_candidate_rows,
        "new_mentions": new_mentions,
        "possible_aliases": possible_aliases,
        "unresolved": unresolved,
        "exclusions": exclusions,
        "explicit_variety_ids": sorted(set(already_canonical_ids)),
        "unresolved_variety_ids": sorted(set(missing_variety_ids)),
    }


def mentions_as_scoring_candidates(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Read-only candidate-shaped rows for recall scoring. No inbox writes."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mention in report.get("mentions") or []:
        if mention.get("disposition") == "berry_mismatch":
            continue
        name = str(mention.get("candidate_name") or "").strip()
        if not name:
            continue
        berry = str(mention.get("berry_id") or "")
        existing_id = str(mention.get("existing_candidate_id") or "")
        key = existing_id or f"mention:{fold_identity(name)}|{berry}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": key,
                "candidate_name": name,
                "name": name,
                "berry_id": berry,
                "disposition": mention.get("disposition"),
                "evidence_id": mention.get("evidence_id") or "",
                "evidence_ids": list(mention.get("evidence_ids") or []),
                "source_url": mention.get("source_url") or "",
                "published_date": mention.get("published_date") or "",
                "mention_kind": mention.get("mention_kind"),
            }
        )
    return rows


def mentions_to_import_rows(mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mention in mentions:
        if mention.get("disposition") == "already_canonical":
            continue
        if mention.get("disposition") == "already_candidate":
            continue
        if mention.get("disposition") == "berry_mismatch":
            continue
        evidence_id = mention.get("evidence_id") or (mention.get("evidence_ids") or [None])[0]
        rows.append(
            {
                "candidate_name": mention["candidate_name"],
                "denomination": mention.get("denomination") or mention["candidate_name"],
                "trade_name": mention["candidate_name"] if mention.get("mention_kind") in {"trade_name", "trade_name_list"} else "",
                "berry_id": mention.get("berry_id") or "",
                "source_id": mention.get("source_id") or evidence_id or "",
                "source_type": mention.get("source_type") or "",
                "source_tier": mention.get("source_tier") or "tier_1_registry",
                "source_label": mention.get("source_label") or mention.get("source_id") or "",
                "source_url": mention.get("source_url") or "",
                "breeder_owner": mention.get("breeder_owner") or "",
                "breeder_code": mention.get("breeder_code") or "",
                "published_date": mention.get("published_date") or "",
                "knowledge": {
                    "origin": "corpus_discovery",
                    "mention_kind": mention.get("mention_kind"),
                    "evidence_ids": mention.get("evidence_ids") or [],
                    "fact_ids": mention.get("fact_ids") or [],
                    "mention_context": mention.get("mention_context") or "",
                },
            }
        )
    return rows


def build_discovered_candidates(
    *,
    varieties: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    published_evidence: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    existing_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=published_evidence,
        facts=facts,
        existing_candidates=existing_candidates,
    )
    rows = mentions_to_import_rows(report["new_mentions"])
    built = [build_candidate(row, varieties=varieties) for row in rows]
    persistable = [row for row in built if row.get("status") != "rejected"]
    for row in persistable:
        row["knowledge"] = row.get("knowledge") or {}
        row["discovered_from"] = "corpus"
        row["human_gated"] = False
        row["auto_confirmed"] = False
    report["candidates"] = persistable
    report["rejected_builds"] = [row for row in built if row.get("status") == "rejected"]
    return report


def merge_visible_candidates(
    inbox_candidates: list[dict[str, Any]],
    discovered_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Inbox (possibly human-reviewed) wins. Discovered rows fill gaps. No writes."""
    seen = _candidate_index(inbox_candidates)
    merged = list(inbox_candidates)
    for row in discovered_candidates:
        berry = str(row.get("berry_id") or "")
        key = f"{fold_identity(str(row.get('candidate_name') or ''))}|{berry}"
        if key in seen or not row.get("id"):
            continue
        visible = {**row, "persisted": False, "discovered_from": "corpus"}
        merged.append(visible)
        seen[key] = str(row["id"])
    return merged
