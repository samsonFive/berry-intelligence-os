"""Private cultivar research, projected through the existing human Fact gate.

Staging is additive and never writes a Fact, Entity, Evidence or Market
Observation. An approved source is insufficient: a reviewed projection needs
the exact active Fact/Claim, source version confirmation and measurement digest.
All scope, units and source-native values survive import without conversion.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator, FormatChecker

from app.repositories.paths import SCHEMAS_DIR
from app.services.draft_delivery import atomic_write_json
from app.services.publication_review_repository import DurableReviewRepository
from app.services.review_events import append_review_event, load_review_events
from app.services.review_publish import ApproveClaimRequest

FOLDER = "cultivar_measurements"
WORKFLOW = "cultivar_measurement_review"
_KINDS = {"cultivar", "aggregate", "unidentified", "accession", "unresolved_identity"}
_STAGING_FIELDS = {"id", "captured_at", "import_batch_id", "content_sha256", "series_key"}


class CultivarMeasurementError(ValueError):
    """Invalid, conflicting or stale private research; fail closed."""


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _content(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in _STAGING_FIELDS}


def _url(value: Any) -> str:
    parts = urlsplit(str(value or "").strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def _safe_id(record_id: str) -> str:
    if not re.fullmatch(r"cm-[a-z0-9-]+-[a-f0-9]{16}", str(record_id)):
        raise CultivarMeasurementError("Invalid cultivar measurement id.")
    return record_id


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / "cultivar-measurement.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _crop_ids(entity: dict[str, Any]) -> set[str]:
    attributes = entity.get("attributes") or {}
    values = [entity.get("berry_id"), attributes.get("berry_id")]
    values.extend(entity.get("berry_ids") or [])
    values.extend(attributes.get("berry_ids") or [])
    return {str(value) for value in values if value}


def compatibility_key(record: dict[str, Any]) -> str:
    """Do not collapse independent datasets, populations, metrics or cohorts.

This is an exact source-native series identity, not permission to compare
different series. It deliberately does not deduplicate across publishers.
"""
    return _hash({
        key: record.get(key) for key in (
            "berry_id", "record_kind", "cultivar_label", "cultivar_entity_id",
            "region", "subregion", "metric", "unit", "denominator", "data_period",
            "cohort", "production_system",
        )
    } | {"sources": sorted([
        {"source_id": item["source_id"], "source_dataset": item.get("source_dataset", ""),
         "source_url": _url(item["source_url"])}
        for item in record.get("source_bindings", [])
    ], key=lambda item: (item["source_id"], item["source_dataset"], item["source_url"]))})


def validate_measurement(record: dict[str, Any], *,
                         entities_by_id: dict[str, dict[str, Any]] | None = None) -> list[str]:
    errors = [error.message for error in _validator().iter_errors(record)]
    if errors:
        return errors
    if record["content_sha256"] != _hash(_content(record)):
        errors.append("Measurement content hash does not match its immutable content.")
    if not record["id"].endswith("-" + record["content_sha256"][:16]):
        errors.append("Measurement id does not match its content version.")
    if record["series_key"] != compatibility_key(record):
        errors.append("Measurement series key does not match its scope.")
    if len({item["source_id"] for item in record["source_bindings"]}) != len(record["source_bindings"]):
        errors.append("Source bindings must have distinct ledger source ids.")
    if record["record_kind"] in {"aggregate", "unidentified"} and record["cultivar_entity_id"] is not None:
        errors.append("Aggregate and unidentified observations cannot carry a cultivar entity.")
    resolution = record.get("identity_resolution")
    if resolution and (resolution["selected_entity_id"] != record["cultivar_entity_id"]
                       or record["cultivar_entity_id"] not in record["candidate_entity_ids"]):
        errors.append("Identity decision does not match one of the preserved candidates.")
    entity_id = record.get("cultivar_entity_id")
    if entity_id and entities_by_id is not None:
        entity = entities_by_id.get(entity_id)
        if entity is None or entity.get("entity_type") != "variety":
            errors.append("Selected cultivar entity does not resolve to a Variety.")
        elif record["berry_id"] not in _crop_ids(entity):
            errors.append("Selected cultivar entity does not belong to this crop.")
    return errors


def normalize_measurement(row: dict[str, Any], *, source_bindings: list[dict[str, Any]],
                          captured_at: str, import_batch_id: str,
                          berry_id: str | None = None,
                          entities_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Preserve one ledger row, including unresolved and qualitative research.

Entity candidates are suggestions. More than one candidate always stays on
hold, even if an earlier ledger field selected a preferred identifier.
"""
    source_row_id = str(row.get("id") or row.get("row_id") or "")
    if not source_row_id:
        raise CultivarMeasurementError("A stable source row id is required.")
    kind = str(row.get("record_kind") or "cultivar")
    if kind not in _KINDS:
        raise CultivarMeasurementError("Unknown source record kind.")
    candidates = list(dict.fromkeys([*(row.get("platform_candidate_ids") or []),
                                     *(row.get("platform_entity_ids") or [])]))
    entity_id = candidates[0] if len(candidates) == 1 and kind in {"cultivar", "accession"} else None
    status = ("not_applicable" if kind in {"aggregate", "unidentified"} else
              "ambiguous" if len(candidates) > 1 else "resolved" if entity_id else "unresolved")
    # Wrong-crop candidates remain visible holds, never an accidental link.
    berry_id = str(row.get("berry_id") or berry_id or "")
    if not berry_id:
        raise CultivarMeasurementError("An explicit crop context is required for cultivar research.")
    if entity_id and entities_by_id is not None:
        entity = entities_by_id.get(entity_id)
        if not entity or entity.get("entity_type") != "variety" or berry_id not in _crop_ids(entity):
            entity_id, status = None, "unresolved"
    bindings = []
    for binding in source_bindings:
        prepared = deepcopy(binding)
        prepared.setdefault("locator", str(row.get("locator") or ""))
        prepared.setdefault("evidence_id", None)
        prepared.setdefault("captured_sha256", None)
        prepared.setdefault("capture_hash_kind", "unknown")
        prepared.setdefault("source_dataset", str(binding.get("source_id") or ""))
        prepared.setdefault("access_status", "unverified source version")
        bindings.append(prepared)
    record = {
        "record_type": "cultivar_measurement", "schema_version": 1,
        "source_row_id": source_row_id, "import_batch_id": import_batch_id,
        "berry_id": berry_id, "record_kind": kind,
        "cultivar_label": str(row.get("cultivar") or row.get("cultivar_label") or "Unidentified"),
        "cultivar_entity_id": entity_id, "candidate_entity_ids": candidates, "identity_status": status,
        "region": str(row.get("region") or "Unspecified"), "subregion": str(row.get("subregion") or ""),
        "evidence_type": str(row.get("evidence_type") or "Unresolved"),
        "claim": str(row.get("claim") or "Unresolved source observation"),
        # Do not infer area share from plant sales, output or a percentage alone.
        "metric": str(row.get("metric") or row.get("evidence_type") or "Unresolved"),
        "value": row.get("value"), "unit": row.get("unit"),
        "denominator": str(row.get("denominator") or ""),
        "data_period": str(row.get("data_period") or ""),
        "cohort": row.get("cohort"), "production_system": row.get("production_system"),
        "source_bindings": bindings, "source_native": deepcopy(row), "captured_at": captured_at,
    }
    if row.get("supersedes"):
        record["supersedes"] = row["supersedes"]
    record["content_sha256"] = _hash(_content(record))
    slug = re.sub(r"[^a-z0-9]+", "-", source_row_id.lower()).strip("-")[:80] or "row"
    record["id"] = f"cm-{slug}-{record['content_sha256'][:16]}"
    record["series_key"] = compatibility_key(record)
    errors = validate_measurement(record, entities_by_id=entities_by_id)
    if errors:
        raise CultivarMeasurementError("; ".join(errors))
    return record


def _locks(inbox_dir: Path) -> DurableReviewRepository:
    return DurableReviewRepository(Path(inbox_dir) / "cultivar_measurement_review_state")


def stage_measurement(inbox_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    errors = validate_measurement(record)
    if errors:
        raise CultivarMeasurementError("; ".join(errors))
    record_id = _safe_id(record["id"])
    path = Path(inbox_dir) / FOLDER / f"{record_id}.json"
    with _locks(inbox_dir).lock_draft(record_id):
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if validate_measurement(existing) or _content(existing) != _content(record):
                raise CultivarMeasurementError("Existing measurement has different content; refusing overwrite.")
            return {"id": record_id, "outcome": "already_present_identical", "path": str(path)}
        atomic_write_json(path, record)
    return {"id": record_id, "outcome": "created", "path": str(path)}


def get_measurement(inbox_dir: Path, measurement_id: str) -> dict[str, Any] | None:
    path = Path(inbox_dir) / FOLDER / f"{_safe_id(measurement_id)}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_measurement(record)
    if errors:
        raise CultivarMeasurementError("; ".join(errors))
    return record


def review_origin(record: dict[str, Any]) -> str:
    return f"cultivar_measurement:{record['id']}:{record['content_sha256']}"


def _evidence_version_digest(evidence: dict[str, Any]) -> str:
    # Claim linkage/reviewer counters can change after each approval. Source
    # content cannot change invisibly underneath an already-reviewed number.
    return _hash({key: evidence.get(key) for key in (
        "source_url", "title", "published_date", "article", "artifact_sha256", "raw_sha256",
        "normalized_body_sha256", "attachments", "transcript_excerpt", "publisher_description",
    )} | {"retained_binary_sha256": (evidence.get("discovery_provenance") or {}).get("retained_binary_sha256"),
          "workspace_binary_sha256": (evidence.get("workspace_capture") or {}).get("binary_sha256")})


def load_evidence_dependencies(data_dir: Path, *, facts: Iterable[dict[str, Any]] = (),
                               evidence_ids: Iterable[str] | None = None,
                               inbox_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Body-free source metadata, hydrating only already-approved dependencies.

The ordinary Evidence repository scans and retains whole source records.
This read path instead reuses the existing streaming preview parser/cache.
Only an active, measurement-origin Fact requires a full source version for
the exact digest check. Pending/list views with no such Facts retain no
article bodies, including unrelated publications and transcript artifacts.
    An explicit source-id set also avoids opening unrelated source metadata;
    active reviewed measurement dependencies are always included independently.
"""
    from app.services.publication_sources import _current_preview
    from app.services.information_storage import (
        InformationStorageError, enabled, get_record, information_directory, safe_id,
    )
    from ijson.common import JSONError

    needed = {str(evidence_id) for fact in facts
              if fact.get("status") == "active"
              and re.fullmatch(r"cultivar_measurement:cm-[a-z0-9-]+-[a-f0-9]{16}:[a-f0-9]{64}",
                               str(fact.get("origin") or ""))
              for evidence_id in fact.get("evidence_ids") or []}
    # The storage adapter rejects incomplete/mismatched activation markers.
    # Never fall back to, or recreate, retired evidence directories.
    context = {"data_dir": Path(data_dir)}
    if inbox_dir is not None:
        context["inbox_dir"] = Path(inbox_dir)
    folder = information_directory(**context)
    shared = enabled(**context)
    if shared and inbox_dir is not None and information_directory(inbox_dir=inbox_dir) != folder:
        raise InformationStorageError("Data and inbox do not resolve the same active information store")
    folders = [(folder, context)]
    if inbox_dir is not None and not shared:
        folders.append((information_directory(inbox_dir=inbox_dir), {"inbox_dir": Path(inbox_dir)}))
    requested = None
    if evidence_ids is not None:
        requested = set()
        for value in [*evidence_ids, *needed]:
            try:
                requested.add(safe_id(str(value)))
            except InformationStorageError:
                continue
    result = {}
    for folder, location in folders:
        paths = (sorted(folder.glob("*.json")) if requested is None else
                 [folder / f"{source_id}.json" for source_id in sorted(requested)])
        for path in paths:
            if path.is_symlink() or path.stem in result:
                continue
            try:
                safe_id(path.stem)
                record = _current_preview(path)
                if record.get("id") != path.stem:
                    continue
                if path.stem in needed:
                    # Single-record adapter access, never repository.list().
                    record = get_record(path.stem, **location)
                if record is not None:
                    result[path.stem] = record
            except (OSError, ValueError, OverflowError, JSONError):
                # Missing/corrupt dependencies cannot satisfy the trust gate.
                continue
    return result


def candidate_statement(record: dict[str, Any], source_binding: dict[str, Any] | None = None) -> str:
    """A complete scoped attribution, not an unqualified popularity claim."""
    selected = source_binding
    source = (selected or {}).get("source_title") or "the cited source"
    place = record["region"] + (f" / {record['subregion']}" if record["subregion"] else "")
    parts = [f"According to {source}, {record['cultivar_label']} ({record['record_kind']})",
             f"in {place}, period {record['data_period'] or 'unspecified'}:", record["claim"].rstrip(".") + "."]
    if record["value"] is not None:
        parts.append(f"Reported value: {record['value']} {record['unit'] or '(unit unspecified)' }.")
    parts.append(f"Basis/population: {record['denominator'] or 'not specified by source'}.")
    parts.append(f"Evidence type: {record['evidence_type']}.")
    if record.get("cohort"):
        parts.append(f"Cohort: {record['cohort']}.")
    if record.get("production_system"):
        parts.append(f"Production system: {record['production_system']}.")
    limitation = record["source_native"].get("limitations")
    if limitation:
        parts.append(f"Limitations: {limitation}")
    if selected:
        parts.append(f"Source reference: {selected['source_id']}; {selected['source_url']}; "
                     f"{selected.get('locator') or 'reviewer-confirmed passage'}.")
    return " ".join(parts)


def _source_ready(binding: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> bool:
    from app.services.information_catalog import information_flags
    if binding.get("source_intake_role") == "acquisition_or_context_inventory":
        return False
    evidence = evidence_by_id.get(str(binding.get("evidence_id") or ""))
    metadata = evidence.get("information") if evidence and isinstance(evidence.get("information"), dict) else {}
    return bool(evidence and evidence.get("status") == "published"
                and information_flags(evidence)["review_status"] == "reviewed"
                and metadata.get("review_status") != "rejected"
                and _url(binding.get("source_url"))
                and _url(binding["source_url"]) == _url(evidence.get("source_url")))


def _capture_matches(binding: dict[str, Any], evidence: dict[str, Any]) -> bool:
    expected = binding.get("captured_sha256")
    kind = binding.get("capture_hash_kind")
    if not expected or kind not in {"artifact", "normalized_body"}:
        return False
    article = evidence.get("article") if isinstance(evidence.get("article"), dict) else {}
    if kind == "normalized_body":
        hashes = [article.get("content_sha256"), evidence.get("normalized_body_sha256")]
    else:
        hashes = [evidence.get("artifact_sha256"), evidence.get("raw_sha256")]
        hashes.append((evidence.get("discovery_provenance") or {}).get("retained_binary_sha256"))
        hashes.append((evidence.get("workspace_capture") or {}).get("binary_sha256"))
        hashes.extend(item.get("sha256") for item in evidence.get("attachments", []) if isinstance(item, dict))
    return expected in hashes


def _identity_blockers(record: dict[str, Any], entities_by_id: dict[str, dict[str, Any]] | None) -> list[str]:
    blockers = []
    if record["record_kind"] not in {"aggregate", "unidentified"}:
        if record["identity_status"] != "resolved" or not record.get("cultivar_entity_id"):
            blockers.append("Cultivar identity requires review; candidates are not canonical decisions.")
        elif entities_by_id is None:
            blockers.append("Live cultivar identity and crop scope have not been checked.")
        if len(record["candidate_entity_ids"]) > 1 and not record.get("identity_resolution"):
            blockers.append("Multiple catalog candidates require an explicit identity decision.")
    if entities_by_id is not None:
        blockers.extend(validate_measurement(record, entities_by_id=entities_by_id))
        if (entities_by_id.get(record["berry_id"]) or {}).get("entity_type") != "berry":
            blockers.append("Crop entity does not resolve in the current runtime.")
    if record["value"] is not None and (not record["unit"] or not record["denominator"] or not record["data_period"]):
        blockers.append("Numeric observations require an explicit unit, denominator and data period.")
    return list(dict.fromkeys(blockers))


def _project(record: dict[str, Any], *, facts_by_origin: dict[str, list[dict[str, Any]]],
             evidence_by_id: dict[str, dict[str, Any]], entities_by_id: dict[str, dict[str, Any]] | None,
             events: list[dict[str, Any]]) -> dict[str, Any]:
    result = deepcopy(record)
    blockers = _identity_blockers(record, entities_by_id)
    if record.get("identity_resolution") and not any(
        event.get("action") == "resolve_identity"
        and event.get("actor") == record["identity_resolution"]["reviewer"]
        and record["content_sha256"] in (event.get("supporting_ids") or [])
        and record.get("cultivar_entity_id") in (event.get("supporting_ids") or [])
        for event in events
    ):
        blockers.append("Identity decision audit event is missing; complete the identity review before claim review.")
    ready_sources = [item for item in record["source_bindings"] if _source_ready(item, evidence_by_id)]
    if not ready_sources:
        blockers.append("No exact-URL source Publication has been approved; source review is required first.")
    origin = review_origin(record)
    reviewed_fact = None
    approval_event = None
    scoped_ids = {record["berry_id"]}
    if record.get("cultivar_entity_id"):
        scoped_ids.add(record["cultivar_entity_id"])
    for event in reversed(events):
        if event.get("action") != "approve_measurement":
            continue
        for fact in facts_by_origin.get(origin, []):
            if fact.get("status") != "active" or fact.get("id") not in (event.get("supporting_ids") or []):
                continue
            for binding in ready_sources:
                if (binding.get("evidence_id") in (fact.get("evidence_ids") or [])
                        and binding["source_id"] == event.get("source_id")
                        and set(fact.get("entity_ids") or []) == scoped_ids
                        and "source-version:" + _evidence_version_digest(evidence_by_id[binding["evidence_id"]])
                            in (event.get("supporting_ids") or [])
                        and fact.get("statement") == candidate_statement(record, binding)):
                    reviewed_fact, approval_event = fact, event
                    break
            if reviewed_fact:
                break
        if reviewed_fact:
            break
    state = "reviewed" if reviewed_fact and not blockers else "blocked" if blockers else "pending"
    if not reviewed_fact and events and events[-1].get("action") in {"reject_measurement", "defer_measurement"}:
        state = "rejected" if events[-1]["action"] == "reject_measurement" else "deferred"
    result.update({
        "review_state": state,
        "review_label": {"reviewed": "Reviewed source-attributed claim", "blocked": "Pending — review hold",
                         "pending": "Pending human review", "rejected": "Rejected proposal",
                         "deferred": "Deferred proposal"}[state],
        "blockers": blockers, "can_approve": not blockers and not reviewed_fact,
        "fact_id": reviewed_fact.get("id") if reviewed_fact else None,
        "classification": reviewed_fact.get("classification") if reviewed_fact else None,
        "review_origin": origin, "candidate_statement": reviewed_fact["statement"] if reviewed_fact else candidate_statement(record),
        "approved_source_ids": [item["source_id"] for item in ready_sources],
        "requires_source_confirmation": True,
        "reviewed_at": approval_event.get("occurred_at") if approval_event else None,
        "reviewer": approval_event.get("actor") if approval_event else None,
        "review_events": deepcopy(events),
    })
    # An explicit public Fact authorization and a public source are both
    # required. Reviewing private research does not grant publication scope.
    from app.services.information_storage import is_public_record
    result["publication_scope"] = "public" if (reviewed_fact and reviewed_fact.get("publication_scope") == "public"
        and any(item.get("evidence_id") in reviewed_fact.get("evidence_ids", [])
                and is_public_record(evidence_by_id[item["evidence_id"]]) for item in ready_sources)) else "private"
    return result


def list_measurements(inbox_dir: Path, *, facts: Iterable[dict[str, Any]] = (),
                      evidence_by_id: dict[str, dict[str, Any]] | None = None,
                      entities_by_id: dict[str, dict[str, Any]] | None = None,
                      include_private: bool = True) -> list[dict[str, Any]]:
    """One bounded pass; public callers receive reviewed projections only.

Do not add this private store to static search/build inputs. A public view
must deliberately ask for include_private=False and provide current trust
dependencies; an empty/default dependency set exposes no pending research.
"""
    fact_rows = list(facts)
    facts_by_origin: dict[str, list[dict[str, Any]]] = {}
    for fact in fact_rows:
        facts_by_origin.setdefault(str(fact.get("origin") or ""), []).append(fact)
    events_by_id: dict[str, list[dict[str, Any]]] = {}
    for event in load_review_events(Path(inbox_dir), workflow=WORKFLOW):
        events_by_id.setdefault(str(event.get("object_id") or ""), []).append(event)
    rows = []
    for path in sorted((Path(inbox_dir) / FOLDER).glob("cm-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_measurement(record)
        if errors:
            raise CultivarMeasurementError(f"{path.name}: " + "; ".join(errors))
        projected = _project(record, facts_by_origin=facts_by_origin, evidence_by_id=evidence_by_id or {},
                             entities_by_id=entities_by_id, events=events_by_id.get(record["id"], []))
        rows.append(projected)
    # A human identity decision creates a new immutable version. Earlier
    # proposals remain available as history, never another current row.
    superseded = {row.get("supersedes") for row in rows if row.get("identity_resolution")}
    for row in rows:
        if row["id"] in superseded:
            row.update(review_state="superseded", review_label="Earlier proposal — identity resolved in a later version",
                       can_approve=False)
    if not include_private:
        rows = _public_measurements(rows, fact_rows, evidence_by_id or {}, entities_by_id or {})
        for row in rows:
            # Operational review notes and raw private provenance remain private.
            for field in ("source_native", "review_events", "candidate_entity_ids", "import_batch_id", "identity_resolution",
                          "supersedes", "review_origin"):
                row.pop(field, None)
            row["source_bindings"] = [{key: binding.get(key) for key in (
                "source_id", "source_url", "source_title", "locator", "source_dataset",
            )} for binding in row["source_bindings"]]
    return rows


def _public_measurements(rows: list[dict[str, Any]], facts: list[dict[str, Any]],
                         evidence: dict[str, dict[str, Any]], entities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Scope is independent of review; mixed/unknown context stays private.

Use the platform's public dependency projection over already-loaded records.
No additional repository scan or persisted trust/publication change occurs.
"""
    from app.services.publication_scope import public_repositories, ID_TOKEN

    class Snapshot:
        def __init__(self, records):
            self.records = list(records)

        def list(self):
            return self.records

    public = public_repositories(SimpleNamespace(
        facts=Snapshot(facts), evidence=Snapshot(evidence.values()), entities=Snapshot(entities.values())))
    public_facts = {row["id"]: row for row in public.facts.list()}
    public_sources = {row["id"] for row in public.evidence.list()}
    public_entities = {row["id"] for row in public.entities.list()
                       if (row.get("attributes") or {}).get("catalog_visibility") != "workspace"}
    known_ids = set(evidence) | set(entities) | {row["id"] for row in facts}
    public_ids = set(public_facts) | public_sources | public_entities
    reference_fields = {"references", "source_refs", "evidence_refs", "platform_import_refs", "href", "url", "uri", "path", "file"}

    def classified(value, *, key="", top=False, reference=False, allowed=None, urls=None):
        if isinstance(value, dict):
            for name, child in value.items():
                if top and name in {"id", "row_id"}:
                    continue  # The source-native ledger row's own identity.
                if name in known_ids and name not in public_ids:
                    return False
                is_reference = (name == "id" or name in reference_fields or
                    name.endswith(("_id", "_ids", "_url", "_href", "_uri", "_path", "_file", "_ref", "_refs")))
                if not classified(child, key=name, reference=reference or is_reference, allowed=allowed, urls=urls):
                    return False
            return True
        if isinstance(value, list):
            return all(classified(item, key=key, reference=reference, allowed=allowed, urls=urls) for item in value)
        if value is None or value == "":
            return True
        if not isinstance(value, str):
            return not reference
        if key in {"path", "file"} or key.endswith(("_path", "_file")) or value.startswith(("file:", "/app/", "/opt/", "/Users/")) or re.match(r"^[A-Za-z]:[\\/]", value):
            return False
        links = re.findall(r"https?://[^\s<>\"']+", value)
        if any(_url(link.rstrip(".,);]")) not in urls for link in links):
            return False
        tokens = {token.rstrip(".") for token in ID_TOKEN.findall(value)}
        tokens.update(token.rsplit(".", 1)[0] for token in list(tokens) if token.endswith((".json", ".html")))
        if (tokens & known_ids) - public_ids:
            return False
        if reference:
            return value in allowed or _url(value) in urls
        return True

    result = []
    for row in rows:
        fact = public_facts.get(row.get("fact_id"))
        if (row["review_state"] != "reviewed" or row.get("publication_scope") != "public"
                or fact is None or fact.get("publication_scope") != "public"):
            continue
        if any(source_id not in public_sources for source_id in fact.get("evidence_ids") or []):
            continue
        if any(entity_id not in public_entities for entity_id in fact.get("entity_ids") or []):
            continue
        bindings = row["source_bindings"]
        if not bindings or any(binding.get("evidence_id") not in public_sources
                or _url(binding.get("source_url")) != _url(evidence[binding["evidence_id"]].get("source_url"))
                for binding in bindings):
            continue
        allowed = public_ids | {binding["source_id"] for binding in bindings}
        urls = {_url(evidence[binding["evidence_id"]].get("source_url")) for binding in bindings}
        if not classified(row["source_native"], top=True, allowed=allowed, urls=urls):
            continue
        row["publication_scope"] = "public"
        result.append(row)
    return result


def _identity_revision(inbox_dir: Path, record_id: str) -> dict[str, Any] | None:
    for path in sorted((Path(inbox_dir) / FOLDER).glob("cm-*.json")):
        candidate = json.loads(path.read_text(encoding="utf-8"))
        if candidate.get("supersedes") == record_id and candidate.get("identity_resolution"):
            if validate_measurement(candidate):
                raise CultivarMeasurementError("Identity revision has invalid immutable content.")
            return candidate
    return None


def _append_identity_event(inbox_dir: Path, revised: dict[str, Any]) -> None:
    resolution = revised["identity_resolution"]
    append_review_event(
        Path(inbox_dir), workflow=WORKFLOW, object_id=revised["id"], object_type="cultivar_measurement",
        action="resolve_identity", prior_state="ambiguous", new_state="identity_resolved",
        actor=resolution["reviewer"], subject={"berry_ids": [revised["berry_id"]],
            "entity_ids": [resolution["selected_entity_id"]]}, notes=resolution["notes"],
        supporting_ids=[revised["supersedes"], revised["id"], revised["content_sha256"], resolution["selected_entity_id"]],
        origin_href=f"/variety-plantings/{revised['id']}", source_surface="variety_plantings",
        idempotency_key="identity:" + revised["content_sha256"],
        occurred_at=datetime.now(UTC).isoformat(timespec="microseconds"),
    )


def resolve_measurement_identity(inbox_dir: Path, measurement_id: str, *, selected_entity_id: str,
                                 reviewer: str, expected_content_sha256: str, notes: str,
                                 repos: Any) -> dict[str, Any]:
    """Explicit candidate choice creates a revision; no entity/alias is edited.

This does not approve the regional claim. It removes only an identity hold
after a reviewer has checked the cultivar code/name against the source.
"""
    if not reviewer.strip() or not notes.strip():
        return {"ok": False, "errors": ["An identity reviewer and source-backed identity note are required."]}
    record_id = _safe_id(measurement_id)
    with _locks(inbox_dir).lock_draft(record_id):
        record = get_measurement(inbox_dir, record_id)
        if record is None or record["content_sha256"] != expected_content_sha256:
            return {"ok": False, "errors": ["Proposal missing or changed; reload before resolving identity."]}
        existing_revision = _identity_revision(inbox_dir, record_id)
        if existing_revision:
            if existing_revision["cultivar_entity_id"] == selected_entity_id:
                _append_identity_event(inbox_dir, existing_revision)
                return {"ok": True, "id": existing_revision["id"], "record": existing_revision, "errors": []}
            return {"ok": False, "errors": ["Identity was already resolved; open the later proposal version."]}
        if record["record_kind"] in {"aggregate", "unidentified"}:
            return {"ok": False, "errors": ["An aggregate/unidentified observation cannot become one cultivar."]}
        if selected_entity_id not in record["candidate_entity_ids"]:
            return {"ok": False, "errors": ["Select an existing proposed candidate; other identities require catalog review first."]}
        entity = repos.entities.get(selected_entity_id)
        if not entity or entity.get("entity_type") != "variety" or record["berry_id"] not in _crop_ids(entity):
            return {"ok": False, "errors": ["Selected candidate is not an existing Variety in this crop."]}
        revised = deepcopy(record)
        revised["cultivar_entity_id"] = selected_entity_id
        revised["identity_status"] = "resolved"
        if revised["record_kind"] == "unresolved_identity":
            revised["record_kind"] = "cultivar"
        revised["supersedes"] = record_id
        revised["identity_resolution"] = {
            "selected_entity_id": selected_entity_id, "reviewer": reviewer.strip(),
            "reviewed_at": datetime.now(UTC).isoformat(timespec="seconds"), "notes": notes.strip(),
        }
        revised["content_sha256"] = _hash(_content(revised))
        slug = re.sub(r"[^a-z0-9]+", "-", record["source_row_id"].lower()).strip("-")[:80] or "row"
        revised["id"] = f"cm-{slug}-{revised['content_sha256'][:16]}"
        revised["series_key"] = compatibility_key(revised)
        errors = validate_measurement(revised, entities_by_id={selected_entity_id: entity})
        if errors:
            return {"ok": False, "errors": errors}
        stage_measurement(inbox_dir, revised)
        _append_identity_event(inbox_dir, revised)
        return {"ok": True, "id": revised["id"], "record": revised, "errors": []}


def review_measurement(inbox_dir: Path, measurement_id: str, *, action: str, reviewer: str,
                       review_publish_service: Any, repos: Any, expected_content_sha256: str,
                       classification: str = "claim", confidence: str = "medium", notes: str = "",
                       source_id: str | None = None, source_version_confirmed: bool = False,
                       source_confirmation_note: str = "") -> dict[str, Any]:
    """One human decision, using the existing source -> Fact/Claim gate.

The HTTP caller enforces authoring mode and authenticated human identity.
The immutable proposal digest protects against stale forms. A source-version
checkbox alone is insufficient: its explicit locator/passage note is retained.
"""
    if action not in {"approve", "reject", "defer"}:
        return {"ok": False, "errors": ["Unknown review action."]}
    if not reviewer.strip():
        return {"ok": False, "errors": ["A human reviewer is required."]}
    record_id = _safe_id(measurement_id)
    locks = _locks(inbox_dir)
    with locks.lock_draft(record_id):
        record = get_measurement(inbox_dir, record_id)
        if record is None:
            return {"ok": False, "errors": ["Measurement proposal not found."]}
        if expected_content_sha256 != record["content_sha256"]:
            return {"ok": False, "errors": ["Measurement changed; reload before reviewing."]}
        if _identity_revision(inbox_dir, record_id):
            return {"ok": False, "errors": ["A later identity-resolved version exists; review that version."]}
        entities = {item["id"]: item for item in repos.entities.list()}
        evidence = {item["id"]: item for item in repos.evidence.list()}
        facts = repos.facts.list()
        events = load_review_events(Path(inbox_dir), workflow=WORKFLOW, object_id=record_id)
        indexed: dict[str, list[dict[str, Any]]] = {}
        for fact in facts:
            indexed.setdefault(str(fact.get("origin") or ""), []).append(fact)
        current = _project(record, facts_by_origin=indexed, evidence_by_id=evidence,
                           entities_by_id=entities, events=events)
        if action != "approve" and any(fact.get("status") == "active" for fact in indexed.get(review_origin(record), [])):
            return {"ok": False, "errors": ["An approved claim must be changed through existing Fact governance."]}
        if current["review_state"] == "reviewed":
            if action == "approve":
                return {"ok": True, "fact_id": current["fact_id"], "errors": [], "review_state": "reviewed"}
            return {"ok": False, "errors": ["An approved claim must be changed through existing Fact governance."]}
        binding = next((item for item in record["source_bindings"] if item["source_id"] == source_id), None)
        fact_id = None
        if action == "approve":
            errors = list(current["blockers"])
            if binding is None:
                errors.append("Explicitly select the primary source for this proposition.")
            elif not _source_ready(binding, evidence):
                errors.append("Selected source is not an approved exact-URL Publication.")
            elif not _capture_matches(binding, evidence[binding["evidence_id"]]):
                if not source_version_confirmed or not source_confirmation_note.strip():
                    errors.append("Confirm the exact source version and record its page/passage before approval.")
            if binding is not None and not binding.get("locator", "").strip() and not source_confirmation_note.strip():
                errors.append("Identify the exact source locator/passage before approving this proposition.")
            if classification not in {"fact", "claim"} or confidence not in {"low", "medium", "high"}:
                errors.append("Choose an existing Fact/Claim classification and confidence.")
            if errors:
                return {"ok": False, "errors": list(dict.fromkeys(errors)), "review_state": current["review_state"]}
            statement = candidate_statement(record, binding)
            scoped_ids = [record["berry_id"]]
            if record.get("cultivar_entity_id"):
                scoped_ids.append(record["cultivar_entity_id"])
            # Serialize this adapter's claims on one source so the existing
            # Fact id numbering cannot race across different cultivar rows.
            with locks.lock_draft("source-" + binding["evidence_id"]):
                result = review_publish_service.approve_claim(ApproveClaimRequest(
                    evidence_id=binding["evidence_id"], statement=statement, proposed_statement=statement,
                    classification=classification, confidence=confidence, reviewer=reviewer.strip(),
                    origin=review_origin(record), entity_ids=scoped_ids,
                ))
            if not result.ok:
                return {"ok": False, "errors": result.schema_errors, "review_state": current["review_state"]}
            fact_id = result.fact_id
            approved_fact = repos.facts.get(fact_id)
            if not approved_fact or approved_fact.get("status") != "active":
                return {"ok": False, "errors": ["The existing claim is not active; use Fact governance to resolve it."]}
        event_notes = notes.strip()
        if action == "approve":
            version_note = ("Exact retained capture hash matched." if _capture_matches(binding, evidence[binding["evidence_id"]])
                            else "Human confirmed source version/passage: " + source_confirmation_note.strip())
            event_notes = "\n".join(value for value in (event_notes, version_note) if value)
        append_review_event(
            Path(inbox_dir), workflow=WORKFLOW, object_id=record_id, object_type="cultivar_measurement",
            action={"approve": "approve_measurement", "reject": "reject_measurement", "defer": "defer_measurement"}[action],
            prior_state=current["review_state"], new_state={"approve": "reviewed", "reject": "rejected", "defer": "deferred"}[action],
            actor=reviewer.strip(), subject={"source_id": source_id, "berry_ids": [record["berry_id"]],
                "entity_ids": [record["cultivar_entity_id"]] if record.get("cultivar_entity_id") else [],
                "created_at": record["captured_at"]}, notes=event_notes or None,
            supporting_ids=[record_id, record["content_sha256"],
                *([fact_id, binding["evidence_id"], "source-version:" + _evidence_version_digest(evidence[binding["evidence_id"]])]
                  if fact_id else [])],
            origin_href=f"/variety-plantings/{record_id}",
            idempotency_key=f"{action}:{record['content_sha256']}:{source_id or ''}:{reviewer.strip()}:" +
                _hash({"source_version": _evidence_version_digest(evidence[binding["evidence_id"]]) if fact_id else None,
                       "notes": event_notes}),
            source_surface="variety_plantings", review_blockers=current["blockers"],
            occurred_at=datetime.now(UTC).isoformat(timespec="microseconds"),
        )
        return {"ok": True, "fact_id": fact_id, "errors": [],
                "review_state": {"approve": "reviewed", "reject": "rejected", "defer": "deferred"}[action]}
