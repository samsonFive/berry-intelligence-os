"""Private, body-free presentation of source-bound cultivar research."""
from __future__ import annotations

import hashlib
import json
from math import ceil
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from app.services.cultivar_measurements import CultivarMeasurementError
from app.services.information_storage import SAFE_ID

IMPORTS_FOLDER = "cultivar_measurement_imports"
STATES = {"pending", "blocked", "deferred", "rejected", "reviewed", "superseded"}
_BATCH = re.compile(r"[a-z0-9][a-z0-9-]{0,159}\Z")


def import_packets(inbox_dir: Path) -> list[dict[str, Any]]:
    """Read metadata only; source binaries never hydrate list/profile views."""
    root = Path(inbox_dir) / IMPORTS_FOLDER
    packets = []
    for file in sorted(root.glob("*/import-index.json")):
        if file.is_symlink() or file.parent.is_symlink() or not _BATCH.fullmatch(file.parent.name):
            continue
        value = json.loads(file.read_text(encoding="utf-8"))
        if value.get("batch_id") != file.parent.name:
            continue
        value["_batch_id"] = file.parent.name
        packets.append(value)
    return packets


def _original_link(value: Any) -> str | None:
    url = str(value or "")
    parts = urlsplit(url)
    return url if parts.scheme in {"http", "https"} and parts.netloc else None


def source_dependency_ids(inbox_dir: Path, packets: list[dict[str, Any]]) -> set[str] | None:
    """Read compact runtime bindings, never thousands of unrelated sources.

    Hand-staged fixtures/older records without an import index retain the
    generic loader fallback. Reconciliation can append another binding snapshot.
    """
    found = False
    ids: set[str] = set()
    for packet in packets:
        root = Path(inbox_dir) / IMPORTS_FOLDER / packet["_batch_id"]
        for file in root.glob("source-bindings-*.json"):
            if file.is_symlink():
                continue
            values = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                continue
            found = True
            for item in values:
                evidence_id = item.get("evidence_id") if isinstance(item, dict) else None
                if isinstance(evidence_id, str) and SAFE_ID.fullmatch(evidence_id):
                    ids.add(evidence_id)
    return ids if found else None


def present_measurement(record: dict[str, Any], *,
                        entities: dict[str, dict[str, Any]],
                        evidence: dict[str, dict[str, Any]],
                        packets: list[dict[str, Any]]) -> dict[str, Any]:
    row = dict(record)
    native = record.get("source_native") or {}
    row["limitations"] = native.get("limitations") or native.get("limitation") or ""
    row["unit_and_basis"] = native.get("unit_and_basis") or "; ".join(
        str(v) for v in (record.get("unit"), record.get("denominator")) if v
    )
    row["href"] = "/variety-plantings/" + record["id"]
    ids = list(dict.fromkeys([record.get("cultivar_entity_id"), *(record.get("candidate_entity_ids") or [])]))
    row["entity_links"] = [{"id": entity_id, "name": entities[entity_id].get("name") or entity_id,
                            "href": "/entities/variety/" + entity_id,
                            "edit_href": "/varieties/catalog/" + entity_id + "/edit"}
                           for entity_id in ids if entity_id in entities]
    row["source_cards"] = []
    for binding in record.get("source_bindings") or []:
        source = dict(binding)
        stored = evidence.get(binding.get("evidence_id")) or {}
        source["url"] = _original_link(binding.get("source_url"))
        source["title"] = binding.get("source_title") or binding["source_id"]
        from app.services.information_catalog import information_flags
        source["information"] = information_flags(stored)
        source["published"] = bool(stored and source["information"]["review_status"] == "reviewed")
        evidence_id = binding.get("evidence_id")
        source["source_href"] = "/intelligence/" + evidence_id if isinstance(evidence_id, str) and SAFE_ID.fullmatch(evidence_id) else None
        source["review_href"] = ("/review/" + evidence_id + "?" + urlencode({"return_to": row["href"]})
                                 if source["source_href"] and not source["published"] else None)
        source["artifacts"] = []
        for packet in packets:
            if packet["_batch_id"] != record.get("import_batch_id"):
                continue
            for asset in packet.get("artifacts") or []:
                if binding["source_id"] not in asset.get("source_ids", []):
                    continue
                digest = asset.get("sha256", "")
                if re.fullmatch(r"[a-f0-9]{64}", digest):
                    source["artifacts"].append({
                        "label": asset.get("original_filename") or asset.get("path") or digest[:12],
                        "href": f"/variety-plantings/imports/{packet['_batch_id']}/artifacts/{digest}",
                        "sha256": digest,
                    })
        row["source_cards"].append(source)
    return row


def workspace(rows: list[dict[str, Any]], *, q: str = "", region: str = "", state: str = "",
              cultivar_id: str = "", berry: str = "global", page: int = 1) -> dict[str, Any]:
    """Filter without ranking unlike metrics or treating candidates as adoption."""
    if state and state not in STATES:
        raise CultivarMeasurementError("Unknown review state.")
    scoped = [r for r in rows if berry == "global" or r.get("berry_id") == berry]
    regions = sorted({r["region"] for r in scoped}, key=str.casefold)
    query = q.strip().casefold()
    matching = [r for r in scoped
                if (not region or r["region"] == region)
                and (not state or r["review_state"] == state)
                and (not cultivar_id or cultivar_id == r.get("cultivar_entity_id") or cultivar_id in r.get("candidate_entity_ids", []))
                and (not query or query in " ".join(str(r.get(k) or "") for k in
                     ("cultivar_label", "region", "subregion", "claim", "data_period", "evidence_type")).casefold())]
    matching.sort(key=lambda r: (r["region"].casefold(), r["cultivar_label"].casefold(),
                                  str(r.get("data_period") or ""), r["id"]))
    pages = max(1, ceil(len(matching) / 40)); page = max(1, min(page, pages))
    filters = {"q": q.strip(), "region": region, "state": state, "cultivar_id": cultivar_id, "berry": berry}
    def page_href(value: int) -> str:
        return "/variety-plantings?" + urlencode({k: v for k, v in {**filters, "page": value}.items() if v})
    return {"rows": matching[(page - 1) * 40:page * 40], "total": len(scoped), "matching": len(matching),
            "regions": regions, "filters": filters, "page": page, "pages": pages,
            "previous_href": page_href(page - 1) if page > 1 else None,
            "next_href": page_href(page + 1) if page < pages else None}


def acquisition_backlog(inbox_dir: Path, packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use only the named supporting file; never follow a packet-supplied path."""
    result = []
    for packet in packets:
        file = Path(inbox_dir) / IMPORTS_FOLDER / packet["_batch_id"] / "supporting" / "acquisition-backlog.json"
        if file.is_file() and not file.is_symlink():
            rows = json.loads(file.read_text(encoding="utf-8"))
            if isinstance(rows, list):
                result.extend(row for row in rows if isinstance(row, dict))
    return result


def source_artifact(inbox_dir: Path, batch_id: str, digest: str) -> tuple[Path, str]:
    """Resolve a registered immutable private capture, with confinement + hash."""
    if not _BATCH.fullmatch(batch_id) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise CultivarMeasurementError("Invalid source capture identity.")
    root = Path(inbox_dir) / IMPORTS_FOLDER / batch_id
    if root.is_symlink() or root.parent.is_symlink():
        raise CultivarMeasurementError("Invalid source capture directory.")
    manifest = root / "packet.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise CultivarMeasurementError("Source capture manifest not found.")
    packet = json.loads(manifest.read_text(encoding="utf-8"))
    matches = [a for a in packet.get("artifacts", []) if a.get("sha256") == digest]
    if not matches:
        raise CultivarMeasurementError("Source capture is not registered.")
    asset = matches[0]; relative = str(asset.get("path") or "")
    if "\\" in relative or ":" in relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise CultivarMeasurementError("Invalid source capture path.")
    asset_root = root
    from app.services import information_storage as storage
    index = root / "import-index.json"
    if storage.enabled(inbox_dir=inbox_dir) and index.is_file():
        if index.is_symlink():
            raise CultivarMeasurementError("Invalid source capture index.")
        registration = json.loads(index.read_text(encoding="utf-8"))
        reference = registration.get("information_assets", {}).get(digest)
        if reference:
            evidence_id, filename = reference.get("evidence_id"), reference.get("filename")
            if (registration.get("packet_sha256") != packet.get("packet_sha256")
                    or not isinstance(evidence_id, str) or not SAFE_ID.fullmatch(evidence_id)
                    or not isinstance(filename, str) or not re.fullmatch(r"[a-f0-9]{64}\.[a-z0-9]+", filename)
                    or filename != Path(relative).name or reference.get("sha256") != digest
                    or reference.get("bytes") != asset.get("bytes")
                    or storage.get_record(evidence_id, inbox_dir=inbox_dir) is None):
                raise CultivarMeasurementError("Invalid shared source capture binding.")
            asset_root = storage.assets_dir(inbox_dir=inbox_dir) / evidence_id
            relative = filename
    path = asset_root / relative
    try:
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(asset_root)):
            raise CultivarMeasurementError("Source capture links are not allowed.")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(asset_root.resolve(strict=True)) or not resolved.is_file():
            raise CultivarMeasurementError("Source capture escapes its import.")
        if resolved.stat().st_size != asset.get("bytes") or hashlib.sha256(resolved.read_bytes()).hexdigest() != digest:
            raise CultivarMeasurementError("Source capture no longer matches its registered version.")
    except OSError as exc:
        raise CultivarMeasurementError("Source capture is unavailable.") from exc
    name = Path(str(asset.get("original_filename") or path.name)).name
    return resolved, name
