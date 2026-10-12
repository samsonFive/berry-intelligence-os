"""Small locator using existing map boundaries and explicit registry ISO tags.

Never computes growing footprints, production statistics or territorial facts.
"""
from functools import lru_cache
from html import escape
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _paths():
    file = Path(__file__).resolve().parents[1] / "static" / "countries.geojson"
    rows = []
    for feature in json.loads(file.read_text(encoding="utf-8"))["features"]:
        geometry = feature.get("geometry") or {}
        polygons = geometry.get("coordinates", [])
        if geometry.get("type") == "Polygon":
            polygons = [polygons]
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        parts = []
        for polygon in polygons:
            for ring in polygon:
                stride = max(1, len(ring) // 90)
                points = [f"{(float(point[0])+180)*1000/360:.1f},{(90-float(point[1]))*500/180:.1f}" for point in ring[::stride]]
                if points:
                    parts.append("M" + " L".join(points) + " Z")
        properties = feature["properties"]
        rows.append((properties.get("ISO3166-1-Alpha-2", ""), properties.get("name", ""), " ".join(parts)))
    return rows


def overview(bundle):
    selected = {lane["iso"] for lane in bundle["lanes"] if lane["iso"]}
    return '<svg viewBox="0 0 1000 500" role="img" aria-label="Selected countries; locator only, not growing presence">' + "".join(
        f'<path d="{path}" class="{"selected" if iso in selected else "boundary"}"><title>{escape(name)}</title></path>' for iso, name, path in _paths()) + '</svg>'
