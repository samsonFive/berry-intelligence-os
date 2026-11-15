"""Portable, hash-bound research intake. Never publishes or approves a claim.

The authored ledger is retained verbatim. Document aliases share a versioned
source binding; original files remain private, content-addressed artifacts.
Publication drafts are created only for substantive row-supporting documents.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from app.services.article_dedup import normalize_canonical_url
from app.services.map_regions import public_source_url

VERSION = "strawberry-research-intake-v1"
PRIVATE_FOLDER = "cultivar_measurement_imports"
MAX_ARTIFACT_BYTES = 80_000_000
SUPPORTING_FILES = ("acquisition-backlog.json", "regional-closure-outcomes.json",
                    "live-audit-summary.json", "coverage-controls.json",
                    "live-platform-inventory.json", "source-material/capture-manifest.json")


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _inside(root, value):
    root = Path(root).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError("Research artifact path leaves the declared capture root")
    return candidate


def _install(path, raw):
    """Additive and process-safe: never replace another writer's bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError(f"Conflicting existing import artifact: {path.name}")
        return "already_present_identical"
    fd, temporary = tempfile.mkstemp(prefix="research-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if os.name == "nt":
                # Windows rename fails if the target already exists; hard links
                # are unavailable in the desktop app's filesystem sandbox.
                os.rename(temporary, path)
            else:
                os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError(f"Conflicting existing import artifact: {path.name}")
            return "already_present_identical"
        return "created"
    finally:
        temporary.unlink(missing_ok=True)


def _source_capture(source, capture_root, packet_dir):
    capture = source.get("capture") or {}
    raw_path = (capture.get("path") or source.get("local_capture")
                or source.get("captured_artifact"))
    if not raw_path:
        return None
    path = _inside(capture_root, raw_path)
    if not path.exists():
        return {"state": "declared_capture_missing", "original_relative_path":
                str(path.relative_to(Path(capture_root).resolve())).replace("\\", "/")}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("Unsafe or oversized research capture")
    raw = path.read_bytes()
    checksum = sha256(raw).hexdigest()
    expected = capture.get("sha256") or source.get("sha256")
    if expected and checksum != expected:
        raise ValueError(f"Research source capture hash mismatch: {source['id']}")
    suffix = path.suffix.casefold()
    if suffix not in {".pdf", ".html", ".htm", ".txt", ".png", ".jpg", ".xlsm", ".xlsx"}:
        suffix = ".bin"
    relative = f"artifacts/{checksum}{suffix}"
    _install(Path(packet_dir) / relative, raw)
    return {"state": "retained_original", "path": relative,
            "sha256": checksum, "bytes": len(raw), "original_filename": path.name,
            "original_relative_path": str(path.relative_to(Path(capture_root).resolve())).replace("\\", "/"),
            "hash_kind": "binary_sha256"}


def _substantive(source, referenced, allowlist):
    if not referenced or source["id"] not in allowlist:
        return False
    source_type = str(source.get("type") or "").casefold()
    return not any(term in source_type for term in
                   ("blank_administrative", "indexed_only", "access inventory", "access check"))


def build_packet(combined_path, packet_dir, *, capture_root, batch_id,
                 captured_at, berry_id, publication_source_ids=(), extract_bodies=False):
    """Build a portable private package from immutable authored research.

    capture_root is explicit; absolute ledger paths may only resolve beneath it.
    Duplicate URL entries enrich one current document, but different binary
    versions remain different documents. No web requests or entity writes occur.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", batch_id):
        raise ValueError("batch_id must be a lowercase slug")
    if not re.fullmatch(r"berry-[a-z0-9-]+", berry_id):
        raise ValueError("Explicit crop entity ID is required")
    if datetime.fromisoformat(captured_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("captured_at requires an explicit timezone")
    raw = Path(combined_path).read_bytes()
    ledger = json.loads(raw)
    rows, sources = ledger["rows"], ledger["sources"]
    if len({r["id"] for r in rows}) != len(rows) or len({s["id"] for s in sources}) != len(sources):
        raise ValueError("Research ledger IDs must be unique")
    source_index = {s["id"]: s for s in sources}
    referenced = {key for row in rows for key in row.get("source_ids", [])}
    if referenced - source_index.keys():
        raise ValueError("Observation references an unavailable source")
    allowlist = set(publication_source_ids)
    if allowlist - referenced:
        raise ValueError("Publication allowlist must contain only explicitly cited source IDs")
    if any(not _substantive(source_index[key], True, allowlist) for key in allowlist):
        raise ValueError("Access-only or indexed-only source cannot enter publication review")
    packet_dir = Path(packet_dir)
    capture_by_id = {s["id"]: _source_capture(s, capture_root, packet_dir) for s in sources}
    url_groups = defaultdict(list)
    for source in sources:
        url = public_source_url(source.get("url"))
        if not url:
            raise ValueError(f"Unsafe source URL: {source['id']}")
        url_groups[normalize_canonical_url(url)].append(source)
    documents = []
    for canonical_url, aliases in sorted(url_groups.items()):
        captures = {c["sha256"]: c for s in aliases
                    if (c := capture_by_id[s["id"]]) and c.get("sha256")}
        # Missing captures can inherit only an unambiguous same-URL capture.
        for checksum in sorted(captures) or [None]:
            members = [s for s in aliases if not capture_by_id[s["id"]]
                       or not capture_by_id[s["id"]].get("sha256")
                       or capture_by_id[s["id"]]["sha256"] == checksum]
            doc = {"id": "srd-" + digest([canonical_url, checksum])[:24],
                   "canonical_url": canonical_url, "source_url": members[0]["url"],
                   "source_ids": sorted(s["id"] for s in members),
                   "source_entries": deepcopy(members),
                   "capture": captures.get(checksum),
                   "source_family_id": "srf-" + digest(canonical_url)[:24],
                   "source_family_basis": "Exact canonical document URL; no claim of independent corroboration",
                   "publication_eligible": any(_substantive(s, s["id"] in referenced, allowlist) for s in members),
                   "source_roles": {s["id"]: "substantive_row_support" if s["id"] in allowlist
                                    else "acquisition_or_context_inventory" for s in members},
                   "version_ambiguous": len(captures) > 1,
                   "prior_capture_hashes": sorted({(s.get("capture") or {}).get("platform_prior_sha256")
                                                    or s.get("prior_sha256") for s in members} - {None, ""})}
            if extract_bodies and doc["capture"] and doc["publication_eligible"]:
                doc["article"] = _extract_article(packet_dir / doc["capture"]["path"],
                                                   doc["source_url"], captured_at)
            documents.append(doc)
    artifacts = {}
    for doc in documents:
        if capture := doc.get("capture"):
            item = artifacts.setdefault(capture["sha256"], {**capture, "role": "source_original",
                                         "linked_document_ids": [], "source_ids": []})
            item["linked_document_ids"].append(doc["id"])
            item["source_ids"].extend(doc["source_ids"])
    for source in sources:
        if visual := (source.get("capture") or {}).get("visual_check"):
            capture = _source_capture({"id": source["id"], "local_capture": visual}, capture_root, packet_dir)
            if capture and capture.get("sha256"):
                artifacts.setdefault(capture["sha256"], {**capture, "role": "visual_verification",
                    "linked_document_ids": [doc["id"] for doc in documents if source["id"] in doc["source_ids"]],
                    "source_ids": [source["id"]]})
    capture_manifest_path = Path(combined_path).parent / "source-material/capture-manifest.json"
    if capture_manifest_path.is_file():
        for item in json.loads(capture_manifest_path.read_text(encoding="utf-8")):
            path = _inside(capture_manifest_path.parent, item["filename"])
            capture = _source_capture({"id": "retained-capture-manifest", "local_capture": str(path),
                                       "sha256": item["sha256"]}, capture_root, packet_dir)
            if capture and capture.get("sha256"):
                artifacts.setdefault(capture["sha256"], {**capture, "role": "visual_verification" if path.suffix == ".png"
                                                         else "retained_source_context",
                    "linked_document_ids": [], "source_ids": []})
    supporting = []
    for name in SUPPORTING_FILES:
        path = Path(combined_path).parent / name
        if path.is_file():
            body = path.read_bytes()
            relative = "supporting/" + path.name
            _install(packet_dir / relative, body)
            supporting.append({"path": relative, "sha256": sha256(body).hexdigest(), "bytes": len(body),
                               "original_filename": path.name, "role": "audit_or_acquisition_metadata"})
    manifest = {"version": VERSION, "batch_id": batch_id, "captured_at": captured_at, "berry_id": berry_id,
                "ledger_path": "combined-research.json", "ledger_sha256": sha256(raw).hexdigest(),
                "documents": documents, "artifacts": list(artifacts.values()), "supporting_files": supporting,
                "publication_source_ids": sorted(allowlist),
                "counts": {"observations": len(rows), "source_entries": len(sources),
                    "documents": len(documents), "publication_eligible_documents": sum(d["publication_eligible"] for d in documents),
                    "retained_capture_documents": sum(bool(d["capture"]) for d in documents),
                    "numeric_observations": sum(r.get("value") is not None for r in rows),
                    "artifacts": len(artifacts), "artifact_bytes": sum(a["bytes"] for a in artifacts.values()),
                    "selectable_text_documents": sum(bool(d.get("article")) for d in documents)},
                "trust_effect": "Private pending research only; no publication, identity, source-version or claim approval"}
    manifest["packet_sha256"] = digest(manifest)
    _install(packet_dir / "combined-research.json", raw)
    _install(packet_dir / "packet.json", _json_bytes(manifest))
    return manifest


def _extract_article(path, source_url, captured_at):
    """Offline selectable text only; figures/scans keep an explicit partial label."""
    paragraphs = []
    if path.suffix.casefold() == ".pdf":
        from pypdf import PdfReader, __version__
        reader = PdfReader(path)
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                paragraphs.append({"index": len(paragraphs), "text": text, "locator": f"pdf:page:{number}"})
        kind, extractor, extractor_version = "pdf", "pypdf-offline-retained-original", __version__
        page_count = len(reader.pages)
    elif path.suffix.casefold() in {".html", ".htm"}:
        import trafilatura
        text = trafilatura.extract(path.read_text(encoding="utf-8", errors="replace")) or ""
        paragraphs = [{"index": i, "text": p} for i, p in enumerate(text.split("\n\n")) if p.strip()]
        kind, extractor, extractor_version = "html", "trafilatura-offline-retained-original", trafilatura.__version__
        page_count = None
    else:
        return None
    if not paragraphs:
        return None
    text = "\n\n".join(p["text"] for p in paragraphs)
    return {"paragraphs": paragraphs, "word_count": len(text.split()), "content_kind": kind,
            "availability": "excerpt_only", "pdf_page_count": page_count,
            "content_sha256": sha256(text.encode()).hexdigest(), "published_date": None,
            "final_url": source_url, "acquisition": {"method": "readable_text_extraction",
                "extractor": extractor, "extractor_version": extractor_version, "fetched_at": captured_at}}


def _read_packet(packet_path):
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    checksum = packet.pop("packet_sha256", None)
    if packet.get("version") != VERSION or digest(packet) != checksum:
        raise ValueError("Research packet manifest hash mismatch")
    packet["packet_sha256"] = checksum
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", str(packet.get("batch_id") or "")):
        raise ValueError("Invalid research batch ID")
    if not re.fullmatch(r"berry-[a-z0-9-]+", str(packet.get("berry_id") or "")):
        raise ValueError("Research packet requires an explicit crop entity ID")
    raw = _inside(packet_path.parent, packet["ledger_path"]).read_bytes()
    if sha256(raw).hexdigest() != packet["ledger_sha256"]:
        raise ValueError("Authored research ledger hash mismatch")
    for capture in [*packet["artifacts"], *packet["supporting_files"]]:
        path = _inside(packet_path.parent, capture["path"])
        if path.is_symlink() or path.stat().st_size > MAX_ARTIFACT_BYTES or sha256(path.read_bytes()).hexdigest() != capture["sha256"]:
            raise ValueError("Retained research capture hash mismatch")
    return packet, json.loads(raw), raw


def _records(folder, recursive=False):
    result = {}
    for path in (Path(folder).rglob("*.json") if recursive else Path(folder).glob("*.json")):
        if path.is_symlink():
            continue
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(record, dict) and record.get("id"):
            result[record["id"]] = record
    return result


def _known_capture_hash(record):
    provenance = record.get("discovery_provenance") or {}
    workspace = record.get("workspace_capture") or {}
    return provenance.get("retained_binary_sha256") or workspace.get("binary_sha256")


def _binding(doc, records):
    matches = [r for r in records.values() if normalize_canonical_url(r.get("source_url")) == doc["canonical_url"]]
    checksum = (doc.get("capture") or {}).get("sha256")
    usable = [r for r in matches if not (checksum and _known_capture_hash(r) and _known_capture_hash(r) != checksum)
              and not (checksum and doc["prior_capture_hashes"] and not _known_capture_hash(r))]
    published = [r for r in usable if r.get("status") == "published"]
    choices = published or usable
    if len(choices) == 1:
        return choices[0]["id"], "reuse_existing", None
    if len(choices) > 1 or doc["version_ambiguous"]:
        return None, "source_identity_or_version_hold", None
    if not doc["publication_eligible"]:
        return None, "acquisition_backlog", None
    evidence_id = "ev-strawberry-source-" + doc["id"][4:]
    first = doc["source_entries"][0]
    full_date = str(first.get("publication_date") or first.get("date") or "")
    try:
        published_date = date.fromisoformat(full_date).isoformat()
    except ValueError:
        published_date = None
    draft = {"id": evidence_id, "record_type": "evidence", "status": "draft", "review_state": "in_review",
             "evidence_role": "publication_artifact", "source_type": "web_article",
             "source_name": urlsplit(doc["source_url"]).hostname or "Source publisher", "source_url": doc["source_url"],
             "title": first["title"], "published_date": published_date,
             "summary": "Source document retained for strawberry cultivar research. Publication and individual claims await human review.",
             "why_it_matters": "Review the original document and its stated geography, data period, metric and denominator before approving any cultivar claim.",
             "submitted_by": "strawberry-research-intake", "berry_ids": [],
             "entity_ids": [], "geography_ids": [], "fact_ids": [], "relationship_ids": [], "tags": ["strawberry-regional-varieties"],
             "priority": {key: {"level": "none", "rationale": ""} for key in
                          ("reading", "testing", "commercial_position", "monitoring")},
             "verification_state": "unverified",
             "does_not_prove": ["Source retention does not approve any research claim or resolve cultivar identity.",
                                "Trial, availability, plant-sales, production and planted-area measures are not interchangeable."],
             "discovery_provenance": {"pipeline": VERSION, "source_document_id": doc["id"],
                 "source_ledger_ids": doc["source_ids"], "source_publication_date_native": full_date,
                 "retained_binary_sha256": checksum, "source_family_id": doc["source_family_id"],
                 "capture_hash_kind": "binary_sha256" if checksum else None,
                 "source_body_status": "selectable_text_partial" if doc.get("article") else
                                       "retained_binary_only" if checksum else "body_unavailable"}}
    if checksum:
        draft["workspace_capture"] = {"binary_sha256": checksum, "source_document_id": doc["id"],
                                      "source_url": doc["source_url"]}
    if doc.get("article"):
        draft["article"] = deepcopy(doc["article"])
    return evidence_id, "new_pending_publication", draft


def import_packet(packet_path, *, data_dir, inbox_dir, apply=False):
    """Dry-run by default; apply only additive private inbox records and blobs."""
    from app.services.cultivar_measurements import normalize_measurement, stage_measurement, validate_measurement
    packet, ledger, raw = _read_packet(packet_path)
    inbox_dir, data_dir = Path(inbox_dir), Path(data_dir)
    if inbox_dir.resolve().is_relative_to(data_dir.resolve()) or data_dir.resolve().is_relative_to(inbox_dir.resolve()):
        raise ValueError("Private intake inbox and canonical data root must be disjoint")
    entities = _records(data_dir / "entities", recursive=True)
    records = _records(inbox_dir / "evidence")
    records.update(_records(data_dir / "evidence"))
    bindings, publications, statuses = {}, [], Counter()
    for doc in packet["documents"]:
        evidence_id, disposition, draft = _binding(doc, records)
        statuses[disposition] += 1
        if draft:
            draft["captured_date"] = packet["captured_at"][:10]
            draft["berry_ids"] = [packet["berry_id"]]
            publications.append(draft)
            records[draft["id"]] = draft
        for source in doc["source_entries"]:
            binding = {"source_id": source["id"], "source_url": source["url"], "source_title": source["title"],
                       "locator": source.get("locator") or "", "evidence_id": evidence_id,
                       "captured_sha256": (doc.get("capture") or {}).get("sha256"),
                       "capture_hash_kind": "artifact" if doc.get("capture") else "unknown",
                       "access_status": "source_identity_or_version_hold" if disposition == "source_identity_or_version_hold"
                                        else "acquisition_backlog" if disposition == "acquisition_backlog"
                                        else "body_partial" if doc.get("article") else
                                        "binary_only" if doc.get("capture") else "body_unavailable",
                       "source_dataset": doc["canonical_url"],
                       "source_family_id": doc["source_family_id"], "source_document_id": doc["id"],
                       "capture_path": (doc.get("capture") or {}).get("path"),
                       "capture_import_batch_id": packet["batch_id"],
                       "source_intake_role": doc["source_roles"][source["id"]],
                       "body_state": "body_partial" if doc.get("article") else
                                     "binary_only" if doc.get("capture") else "body_unavailable",
                       "source_publication_date": source.get("publication_date") or source.get("date")}
            if source["id"] in bindings:
                binding["access_status"] = "source_identity_or_version_hold"
                binding["evidence_id"] = None
            bindings[source["id"]] = binding
    measurements = [normalize_measurement(row, source_bindings=[bindings[key] for key in row["source_ids"]],
                     captured_at=packet["captured_at"], import_batch_id=packet["batch_id"], entities_by_id=entities,
                     berry_id=packet["berry_id"])
                    for row in ledger["rows"]]
    existing_rows = defaultdict(list)
    for record in _records(inbox_dir / "cultivar_measurements").values():
        if record.get("import_batch_id") == packet["batch_id"]:
            existing_rows[record.get("source_row_id")].append(record)
    for i, proposed in enumerate(measurements):
        matches = existing_rows.get(proposed["source_row_id"], [])
        bases = [record for record in matches if not record.get("identity_resolution")]
        if matches and len(bases) != 1:
            raise ValueError("Competing imported base versions require explicit row reconciliation")
        if matches:
            existing = bases[0]
            if (validate_measurement(existing) or existing["source_native"] != proposed["source_native"]
                    or existing["source_bindings"] != proposed["source_bindings"]
                    or existing["berry_id"] != proposed["berry_id"]):
                raise ValueError("Staged research row or source binding changed; explicit reconciliation is required")
            versions = {record["id"]: record for record in matches}
            for revision in matches:
                if revision is existing:
                    continue
                if (validate_measurement(revision) or revision["source_native"] != existing["source_native"]
                        or revision["source_bindings"] != existing["source_bindings"]
                        or revision["berry_id"] != existing["berry_id"]):
                    raise ValueError("Identity revision does not preserve the imported source row")
                seen, cursor = set(), revision
                while cursor["id"] != existing["id"]:
                    if cursor["id"] in seen or not cursor.get("identity_resolution") or cursor.get("supersedes") not in versions:
                        raise ValueError("Identity revision does not descend from the imported base")
                    seen.add(cursor["id"])
                    cursor = versions[cursor["supersedes"]]
            # Runtime catalog changes must not silently create a new proposal or
            # rewrite the original identity suggestion. The review projection
            # checks the current dependency and displays any resulting hold.
            measurements[i] = existing
    from app.repositories.paths import SCHEMAS_DIR
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8")),
                                    format_checker=FormatChecker())
    for draft in publications:
        errors = [e.message for e in validator.iter_errors(draft)]
        if errors:
            raise ValueError("Pending source Publication is invalid: " + "; ".join(errors))
    plan = {"version": VERSION, "batch_id": packet["batch_id"], "packet_sha256": packet["packet_sha256"],
            "mode": "apply_private_pending" if apply else "dry_run", "counts": {**packet["counts"],
                "new_publication_drafts": len(publications), "numeric_observations": sum(r.get("value") is not None for r in ledger["rows"]),
                "source_dispositions": dict(statuses),
                "identity_statuses": dict(Counter(m["identity_status"] for m in measurements))},
            "trust_effect": packet["trust_effect"], "source_bindings": list(bindings.values())}
    if not apply:
        return plan
    from app.services.pipeline_lock import pipeline_lock
    with pipeline_lock(inbox_dir, "strawberry-research-import"):
        import_root = inbox_dir / PRIVATE_FOLDER / packet["batch_id"]
        _install(import_root / "packet.json", _json_bytes(packet))
        _install(import_root / "combined-research.json", raw)
        for capture in [*packet["artifacts"], *packet["supporting_files"]]:
            _install(import_root / capture["path"], _inside(Path(packet_path).resolve().parent, capture["path"]).read_bytes())
        for draft in publications:
            _install(inbox_dir / "evidence" / (draft["id"] + ".json"), _json_bytes(draft))
        outcomes = Counter(stage_measurement(inbox_dir, record)["outcome"] for record in measurements)
        # Runtime binding decisions are append-only snapshots, not a replacement for edits.
        binding_digest = digest(plan["source_bindings"])
        _install(import_root / f"source-bindings-{binding_digest[:16]}.json", _json_bytes(plan["source_bindings"]))
        index = {key: packet[key] for key in ("version", "batch_id", "captured_at", "berry_id", "packet_sha256", "ledger_sha256",
                                               "counts", "artifacts", "supporting_files", "trust_effect")}
        _install(import_root / "import-index.json", _json_bytes(index))
        plan["counts"]["measurement_outcomes"] = dict(outcomes)
    return plan


def load_import_batches(inbox_dir):
    """Small private metadata projection; never hydrate the research/article body."""
    result = []
    for path in sorted((Path(inbox_dir) / PRIVATE_FOLDER).glob("*/import-index.json")):
        if path.is_symlink():
            continue
        index = json.loads(path.read_text(encoding="utf-8"))
        if index.get("version") != VERSION or index.get("batch_id") != path.parent.name:
            continue
        index["acquisition_backlog"] = []
        for item in index.get("supporting_files", []):
            if item["original_filename"] == "acquisition-backlog.json":
                body = _inside(path.parent, item["path"]).read_bytes()
                if sha256(body).hexdigest() == item["sha256"]:
                    index["acquisition_backlog"] = json.loads(body)
        result.append(index)
    return result
