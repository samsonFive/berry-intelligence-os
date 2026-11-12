"""Code-owned simulated sensory fixture. Never part of a canonical domain index."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from app.runtime_config import resolve_data_dir

DEMO_PATH = Path(__file__).resolve().parents[1] / "demo_data/flavor/synthetic-overall-liking-v1.json"
METRIC_IDS = ("sweetness", "acidity", "aroma", "firmness", "overall_liking")
DEMO_ID = re.compile(r"demo-(?:specimen|brand)-[A-Za-z0-9_.-]+\Z")


def _score(value, *, simulated_brand=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            and (4 <= value <= 8 if simulated_brand else 1 <= value <= 9)
            and Decimal(str(value)).as_tuple().exponent >= -2)


def _public_url(value):
    if not isinstance(value, str) or re.search(r"[\x00-\x20\x7f]", value):
        return False
    try:
        url = urlsplit(value)
        return url.scheme in {"http", "https"} and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def validate_fixture(fixture, *, entities_dir=None):
    """Validate ratings separately from typed identity references; never qualify a claim."""
    error = ValueError("The isolated synthetic fixture is unavailable or incompatible.")
    if not isinstance(fixture, dict):
        raise error
    metric, specimens = fixture.get("metric", {}), fixture.get("specimens", [])
    if (not isinstance(metric, dict) or fixture.get("synthetic") is not True or fixture.get("namespace") != "synthetic-sensory-v1"
            or metric.get("id") != "overall_liking" or metric.get("minimum") != 1 or metric.get("maximum") != 9
            or not isinstance(specimens, list) or not specimens
            or any(not isinstance(row, dict) or not re.fullmatch(r"demo-specimen-[A-Za-z0-9_.-]+", str(row.get("id", "")))
                   or not isinstance(row.get("label"), str) or not _score(row.get("value")) for row in specimens)):
        raise error
    profiles = fixture.get("brand_profiles", [])
    if not isinstance(profiles, list):
        raise error
    if profiles:
        metrics = fixture.get("metrics")
        if (not isinstance(metrics, list) or len(metrics) != len(METRIC_IDS) or not all(isinstance(row, dict) for row in metrics)
                or [row.get("id") for row in metrics] != list(METRIC_IDS)):
            raise error
        for row in metrics:
            hedonic = row["id"] == "overall_liking"
            if (row.get("minimum") != 1 or row.get("maximum") != 9
                    or row.get("scale_type") != ("hedonic" if hedonic else "intensity")
                    or row.get("minimum_label") != ("Dislike extremely" if hedonic else "Very low")
                    or row.get("maximum_label") != ("Like extremely" if hedonic else "Very high")):
                raise error
        directory = Path(entities_dir) if entities_dir is not None else resolve_data_dir() / "entities"
        identities = set()
        for profile in profiles:
            if not isinstance(profile, dict):
                raise error
            key, name = profile.get("id"), profile.get("brand_label")
            ref, basis, values = profile.get("canonical_entity", {}), profile.get("identity_basis", {}), profile.get("values", {})
            if (not isinstance(key, str) or not re.fullmatch(r"demo-brand-[A-Za-z0-9_.-]+", key)
                    or profile.get("synthetic") is not True or not isinstance(name, str) or not name.strip()
                    or profile.get("label") != "SIMULATED · " + name or not isinstance(ref, dict)
                    or ref.get("type") not in {"company", "brand"} or not isinstance(ref.get("id"), str)
                    or not re.fullmatch(ref["type"] + r"-[A-Za-z0-9_.-]+", ref["id"])
                    or not isinstance(values, dict) or set(values) != set(METRIC_IDS)
                    or not all(_score(value, simulated_brand=True) for value in values.values())
                    or not isinstance(basis, dict) or not isinstance(basis.get("note"), str) or not basis["note"].strip()
                    or not isinstance(basis.get("urls"), list) or not basis["urls"] or not all(_public_url(url) for url in basis["urls"])):
                raise error
            identity = (ref["type"], ref["id"])
            if identity in identities:
                raise error
            identities.add(identity)
            # Six tiny selected files, never a corpus load, search insertion or canonical write.
            folder = "companies" if ref["type"] == "company" else "brands"
            try:
                record = json.loads((directory / folder / (ref["id"] + ".json")).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise error from exc
            if record.get("id") != ref["id"] or record.get("entity_type") != ref["type"]:
                raise error
    all_rows = specimens + profiles
    if len({row["id"] for row in all_rows}) != len(all_rows):
        raise error
    return fixture


def load_fixture(path=DEMO_PATH, *, entities_dir=None):
    return validate_fixture(json.loads(Path(path).read_text(encoding="utf-8")), entities_dir=entities_dir)


def selected_fixture(fixture, requested):
    """Empty means complete fixture; unknown membership never silently becomes all."""
    available = {row["id"] for row in fixture["specimens"] + fixture.get("brand_profiles", [])}
    if any(not isinstance(key, str) or not DEMO_ID.fullmatch(key) for key in requested) or set(requested) - available:
        raise ValueError("Some selected demo specimens are unavailable. Choose available specimens or explicitly select all before exporting the synthetic annex.")
    selected = deepcopy(fixture)
    for key in ("specimens", "brand_profiles"):
        if key in selected:
            selected[key] = [row for row in selected[key] if not requested or row["id"] in requested]
    return selected
