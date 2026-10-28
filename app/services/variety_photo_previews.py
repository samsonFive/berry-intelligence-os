"""Read-only larger originals; retain photo identity and every user override."""
from copy import deepcopy
from datetime import date
import re

from app.services.map_regions import public_source_url


def preview_url(value):
    if not isinstance(value, str) or len(value) > 2000 or not public_source_url(value):
        raise ValueError("A larger photo needs its complete public image URL")
    return value


def read_preview_overlays(payload):
    rows = payload.get("photo_preview_overlays", [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Photo previews need a bounded list")
    keys = {"source_id", "source_fingerprint", "candidate_name", "berry_id",
            "image_url", "preview_image_url", "checked_on"}
    result = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != keys
                or any(not isinstance(row[k], str) or not row[k].strip() for k in keys)
                or not re.fullmatch(r"[0-9a-f]{64}", row["source_fingerprint"])
                or row["berry_id"] not in {"berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"}):
            raise ValueError("Photo previews need an exact source, name, crop and capture fingerprint")
        preview_url(row["image_url"])
        preview_url(row["preview_image_url"])
        if row["image_url"] == row["preview_image_url"] or date.fromisoformat(row["checked_on"]) > date.today():
            raise ValueError("Record a distinct larger original and its actual check date")
        key = (row["source_id"], row["candidate_name"], row["berry_id"], row["image_url"])
        if key in result:
            raise ValueError("A source photo can have only one preview per snapshot")
        result[key] = row
    return result


def apply_preview_overlays(latest, overlays, fingerprints):
    for row in overlays.values():
        source_id = row["source_id"]
        if source_id not in latest:
            raise ValueError("Photo preview refers to an unavailable source")
        if fingerprints[source_id] != row["source_fingerprint"]:
            # An operator edit or newer capture wins, including permission edits.
            continue
        source = deepcopy(latest[source_id])
        matches = [photo for name in source["names"]
                   if name["candidate_name"] == row["candidate_name"] and name["berry_id"] == row["berry_id"]
                   for photo in name.get("photos", []) if photo["image_url"] == row["image_url"]]
        if len(matches) != 1 or matches[0]["reuse"] != "unknown":
            raise ValueError("A larger preview must match one held source photo; reuse remains unconfirmed")
        matches[0]["preview_image_url"] = row["preview_image_url"]
        latest[source_id] = source
