"""Portable, hash-bound research intake. Never publishes or approves a claim.

The authored ledger is retained verbatim. Document aliases share a versioned
source binding; original files remain private, content-addressed artifacts.
Publication drafts are created only for substantive row-supporting documents.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import nullcontext
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
from app.services import information_storage
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
        if (path.is_symlink() or path.stat().st_size > MAX_ARTIFACT_BYTES or path.stat().st_size != capture["bytes"]
                or sha256(path.read_bytes()).hexdigest() != capture["sha256"]):
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


def _active_source_store(data_dir, inbox_dir):
    active = information_storage.enabled(data_dir=data_dir, inbox_dir=inbox_dir)
    if active and (information_storage.information_directory(inbox_dir=inbox_dir)
                   != information_storage.information_directory(data_dir=data_dir, inbox_dir=inbox_dir)):
        raise information_storage.InformationStorageError("Active information store requires its paired inbox binding")
    return active


def _source_records(data_dir, inbox_dir, documents):
    """Keep only matching source metadata, never the inventory's article bodies.

    The shared streaming reader bounds both individual previews and its cache.
    A workspace-capture marker omits the saved binary hash, so only a matching
    record with that marker may require a full read, immediately reduced again.
    Stored capture metadata selects a source version; it does not revalidate an
    old binary or confer source/claim approval.
    """
    from app.services.publication_sources import _current_preview

    wanted_urls = {doc["canonical_url"] for doc in documents}
    wanted_ids = {"ev-strawberry-source-" + doc["id"][4:] for doc in documents}
    if _active_source_store(data_dir, inbox_dir):
        layouts = [{"data_dir": data_dir, "inbox_dir": inbox_dir}]
    else:
        # Canonical legacy IDs take precedence even when their current URL no
        # longer matches. A stale intake copy must not resurrect the older URL.
        layouts = [{"data_dir": data_dir}, {"inbox_dir": inbox_dir}]
    records, seen = {}, set()
    for layout in layouts:
        folder = information_storage.information_directory(**layout)
        for path in sorted(folder.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Unsafe source information record")
            information_storage.safe_id(path.stem)
            if path.stem in seen:
                continue
            preview = _current_preview(path)
            if preview.get("id") != path.stem:
                raise ValueError("Source information record ID does not match its filename")
            seen.add(path.stem)
            if (path.stem not in wanted_ids
                    and normalize_canonical_url(preview.get("source_url")) not in wanted_urls):
                continue
            if preview.get("workspace_capture") and not _known_capture_hash(preview):
                preview = information_storage.get_record(path.stem, **layout)
                if preview is None:
                    raise ValueError("Matching source record changed during import planning")
            record = {key: preview.get(key) for key in ("id", "status", "source_url", "publication_scope")}
            record["discovery_provenance"] = {"retained_binary_sha256": _known_capture_hash(preview)}
            records[record["id"]] = record
    return records


def _write_new_private_source(draft, *, data_dir, inbox_dir, source_lease_held=False):
    """Create only the planned private source; never use intake to edit it."""
    if _active_source_store(data_dir, inbox_dir):
        # Every source writer honors this lease, including writers outside the
        # import pipeline. Never merge over an item created after planning.
        lease = nullcontext() if source_lease_held else information_storage.storage_lock(data_dir=data_dir, inbox_dir=inbox_dir)
        with lease:
            if information_storage.get_record(draft["id"], data_dir=data_dir, inbox_dir=inbox_dir) is not None:
                raise ValueError("Source record appeared after planning; reload before importing")
            path = information_storage.record_path(draft["id"], data_dir=data_dir, inbox_dir=inbox_dir)
            prepared = draft if source_lease_held else information_storage.prepare_record(draft, origin="intake", preserve_existing=True)
            _install(path, _json_bytes(prepared))
            return path
    # Naming only the inbox retains the legacy private-draft location.
    path = information_storage.record_path(draft["id"], inbox_dir=inbox_dir)
    _install(path, _json_bytes(draft))
    return path


def _known_capture_hash(record):
    provenance = record.get("discovery_provenance")
    workspace = record.get("workspace_capture")
    provenance = provenance if isinstance(provenance, dict) else {}
    workspace = workspace if isinstance(workspace, dict) else {}
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
             "publication_scope": "private",
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


def _plan_source_bindings(packet, records):
    """Plan immutable source-native bindings without changing current Sources."""
    records = dict(records)
    bindings, publications, statuses = {}, [], Counter()
    for doc in packet["documents"]:
        evidence_id, disposition, draft = _binding(doc, records)
        statuses[disposition] += 1
        if draft:
            if draft["id"] in records:
                raise ValueError("Deterministic source ID conflicts with an existing source record")
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
    return bindings, publications, statuses


def _check_asset_target(path, capture, *, require_existing=False):
    """Validate an additive destination without creating directories or bytes."""
    path = Path(path)
    for ancestor in path.parents:
        if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
            raise ValueError("Research asset parent must be an ordinary directory")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Research asset must be a regular file")
    if not path.exists():
        if require_existing:
            raise ValueError("Previously registered public source asset is missing; private bytes cannot be created there")
        return
    checksum = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    if path.stat().st_size != capture["bytes"] or checksum.hexdigest() != capture["sha256"]:
        raise ValueError("Conflicting existing research asset bytes")


def resolve_information_assets(packet, *, data_dir, inbox_dir, bindings, records, publications):
    """Read-only shared-original plan and exact new private source payloads.

    Registry absence means the artifact stays at its immutable private batch
    path. Only source originals with a bound private owner can receive a new
    shared path. Existing registrations never move on replay; a now-public
    owner may retain only a complete, already identical registered original.
    Callers must replan under the source lease before installing any bytes.
    """
    shared_store = _active_source_store(data_dir, inbox_dir)
    import_root = Path(inbox_dir) / PRIVATE_FOLDER / packet["batch_id"]
    index_path = import_root / "import-index.json"
    if index_path.is_symlink():
        raise ValueError("Research import registration cannot be a symbolic link")
    previous_index = None
    if index_path.exists():
        if not index_path.is_file() or index_path.stat().st_size > 16_000_000:
            raise ValueError("Unsafe research import registration")
        previous_index = json.loads(index_path.read_text(encoding="utf-8"))
        if (previous_index.get("batch_id") != packet["batch_id"]
                or previous_index.get("packet_sha256") != packet["packet_sha256"]):
            raise ValueError("Research import registration differs from the immutable packet")
    previous_assets = (previous_index or {}).get("information_assets", {})
    if not isinstance(previous_assets, dict):
        raise ValueError("Invalid registered research asset map")
    planned_sources = {draft["id"]: deepcopy(draft) for draft in publications}
    owners_by_id = {**records, **planned_sources}
    references = {}
    for capture in [*packet["artifacts"], *packet["supporting_files"]]:
        previous = previous_assets.get(capture["sha256"])
        bound_ids = {bindings[source_id]["evidence_id"] for source_id in capture.get("source_ids", [])
                     if bindings.get(source_id, {}).get("evidence_id")}
        owners = sorted(key for key in bound_ids
                        if owners_by_id.get(key, {}).get("publication_scope") == "private")
        if previous_index is not None and previous is None:
            # A pre-cutover ledger without this shared registration keeps its
            # batch original forever; replay does not introduce a second copy.
            owners = []
        if previous is not None:
            if (not shared_store or capture.get("role") != "source_original" or not isinstance(previous, dict)
                    or previous.get("evidence_id") not in bound_ids
                    or previous.get("evidence_id") not in owners_by_id
                    or previous.get("filename") != Path(capture["path"]).name
                    or previous.get("sha256") != capture["sha256"] or previous.get("bytes") != capture["bytes"]):
                raise ValueError("Stored research asset binding changed; explicit reconciliation is required")
            owners = [previous["evidence_id"]]
        if shared_store and capture.get("role") == "source_original" and owners:
            owner = information_storage.safe_id(owners[0])
            filename = Path(capture["path"]).name
            reference = {"evidence_id": owner, "filename": filename,
                         "sha256": capture["sha256"], "bytes": capture["bytes"]}
            target = information_storage.assets_dir(data_dir=data_dir, inbox_dir=inbox_dir) / owner / filename
            _check_asset_target(target, capture, require_existing=owners_by_id[owner].get("publication_scope") != "private")
            references[capture["sha256"]] = reference
            if owner in planned_sources:
                planned_sources[owner].setdefault("attachments", []).append({"filename": filename,
                    "original_filename": capture["original_filename"], "sha256": capture["sha256"],
                    "content_type": "application/pdf" if filename.endswith(".pdf") else "application/octet-stream",
                    "url": f"/intake/{owner}/attachments/{filename}"})
        else:
            _check_asset_target(_inside(import_root, capture["path"]), capture)
    if set(previous_assets) - set(references):
        raise ValueError("Registered research asset is not represented by this packet")
    prepared = [information_storage.prepare_record(row, origin="intake", preserve_existing=True)
                if shared_store else row for row in planned_sources.values()]
    return references, prepared


def _new_source_metadata(publications):
    return {row["id"]: {"source_url": row["source_url"],
                "source_document_id": row["discovery_provenance"]["source_document_id"],
                "publication_scope": row.get("publication_scope"),
                "status": row.get("status"), "review_state": row.get("review_state"),
                "storage_origin": row.get("storage_origin"), "submitted_by": row.get("submitted_by"),
                "review_status": (row.get("information") or {}).get("review_status", "unreviewed"),
                "attachments": deepcopy(row.get("attachments", [])),
                "record_sha256": sha256(_json_bytes(row)).hexdigest(), "record_bytes": len(_json_bytes(row))}
            for row in publications}


def import_packet(packet_path, *, data_dir, inbox_dir, apply=False):
    """Stage private source information and inbox proposals; never Facts.

    An activated unified store owns source rows under data/information/records.
    Entities/Facts stay untouched; an inactive installation uses legacy intake.
    """
    from app.services.cultivar_measurements import normalize_measurement, stage_measurement, validate_measurement
    packet, ledger, raw = _read_packet(packet_path)
    inbox_dir, data_dir = Path(inbox_dir), Path(data_dir)
    if inbox_dir.resolve().is_relative_to(data_dir.resolve()) or data_dir.resolve().is_relative_to(inbox_dir.resolve()):
        raise ValueError("Private intake inbox and canonical data root must be disjoint")
    entities = _records(data_dir / "entities", recursive=True)
    shared_store = _active_source_store(data_dir, inbox_dir)
    records = _source_records(data_dir, inbox_dir, packet["documents"])
    bindings, publications, statuses = _plan_source_bindings(packet, records)
    asset_references, publications = resolve_information_assets(packet, data_dir=data_dir, inbox_dir=inbox_dir,
        bindings=bindings, records=records, publications=publications)
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
            "trust_effect": packet["trust_effect"], "source_bindings": list(bindings.values()),
            "information_assets": asset_references, "new_sources": _new_source_metadata(publications)}
    if not apply:
        return plan
    from app.services.pipeline_lock import pipeline_lock
    with pipeline_lock(inbox_dir, "strawberry-research-import"):
        source_lease = information_storage.storage_lock(data_dir=data_dir, inbox_dir=inbox_dir) if shared_store else nullcontext()
        with source_lease:
            # Re-resolve current source identity, version and privacy before any
            # private original or source row is installed. The same lease spans
            # all asset writes and every create-only Source operation.
            if _active_source_store(data_dir, inbox_dir) != shared_store:
                raise ValueError("Source storage layout changed during import planning")
            fresh_records = _source_records(data_dir, inbox_dir, packet["documents"])
            fresh_bindings, fresh_publications, _ = _plan_source_bindings(packet, fresh_records)
            fresh_assets, fresh_publications = resolve_information_assets(packet, data_dir=data_dir, inbox_dir=inbox_dir,
                bindings=fresh_bindings, records=fresh_records, publications=fresh_publications)
            fresh_plan = {"source_bindings": list(fresh_bindings.values()), "information_assets": fresh_assets,
                          "new_sources": _new_source_metadata(fresh_publications)}
            if digest(fresh_plan) != digest({key: plan[key] for key in fresh_plan}):
                raise ValueError("Source record appeared after planning or its identity/privacy changed; reload before importing")
            if shared_store:
                for draft in publications:
                    if information_storage.get_record(draft["id"], data_dir=data_dir, inbox_dir=inbox_dir) is not None:
                        raise ValueError("Source record appeared after planning; reload before importing")
            import_root = inbox_dir / PRIVATE_FOLDER / packet["batch_id"]
            _install(import_root / "packet.json", _json_bytes(packet))
            _install(import_root / "combined-research.json", raw)
            owners_by_id = {**fresh_records, **{row["id"]: row for row in fresh_publications}}
            for capture in [*packet["artifacts"], *packet["supporting_files"]]:
                if reference := asset_references.get(capture["sha256"]):
                    owner = reference["evidence_id"]
                    target = information_storage.assets_dir(data_dir=data_dir, inbox_dir=inbox_dir) / owner / reference["filename"]
                    if owners_by_id[owner].get("publication_scope") != "private":
                        # A previously registered original can outlive a later
                        # explicit public authorization. Never repair/recreate
                        # private input bytes under that now-public owner.
                        _check_asset_target(target, capture, require_existing=True)
                        continue
                else:
                    target = _inside(import_root, capture["path"])
                _install(target, _inside(Path(packet_path).resolve().parent, capture["path"]).read_bytes())
            for draft in publications:
                _write_new_private_source(draft, data_dir=data_dir, inbox_dir=inbox_dir, source_lease_held=shared_store)
            outcomes = Counter(stage_measurement(inbox_dir, record)["outcome"] for record in measurements)
            # Runtime binding decisions are append-only snapshots, not a replacement for edits.
            binding_digest = digest(plan["source_bindings"])
            _install(import_root / f"source-bindings-{binding_digest[:16]}.json", _json_bytes(plan["source_bindings"]))
            index = {key: packet[key] for key in ("version", "batch_id", "captured_at", "berry_id", "packet_sha256", "ledger_sha256",
                                                   "counts", "artifacts", "supporting_files", "trust_effect")}
            if asset_references:
                index["information_assets"] = asset_references
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
