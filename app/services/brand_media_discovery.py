"""Bounded, offline discovery from an already verified official page's JSON-LD.

This module never fetches a page/image, follows a JSON-LD context, resolves DNS,
or grants display rights. A schema Product image is a packaging *candidate*, not
proof that the image depicts a pack. Subject names and brands remain separate.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from app.services.feed_first_reader import is_public_http_url
from app.services.social_intelligence.model import safe_url

VERSION = "brand-media-jsonld-1"
MAX_HTML_BYTES = 800_000
MAX_SCRIPTS = 50
MAX_NODES = 2_000
MAX_DEPTH = 20
MAX_CANDIDATES = 120


def public_reference(value: str, *, base_url: str = "") -> str:
    """Reuse shared URL guards for references; not a network/DNS safety grant."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError("A bounded public HTTPS reference is required")
    if value != value.strip() or re.search(r"[\x00-\x20\x7f\\]", value):
        raise ValueError("Control characters, whitespace and backslashes are forbidden")
    resolved = urljoin(base_url, value)
    if not is_public_http_url(resolved):
        raise ValueError("Private or malformed references are forbidden")
    safe_url(resolved)
    host = urlsplit(resolved).hostname or ""
    try:
        ascii_host = host.encode("idna").decode("ascii").rstrip(".")
    except UnicodeError:
        raise ValueError("Invalid reference hostname") from None
    # IPv6 literals have already passed shared global-address validation.
    if ":" not in ascii_host and any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                                      for label in ascii_host.split(".")):
        raise ValueError("Invalid reference hostname")
    return resolved


class _JsonLdScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            media_type = (dict(attrs).get("type") or "").split(";", 1)[0].strip().lower()
            self.current = [] if media_type == "application/ld+json" and len(self.scripts) < MAX_SCRIPTS else None

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            self.scripts.append("".join(self.current))
            self.current = None


def _types(node):
    values = node.get("@type", [])
    values = values if isinstance(values, list) else [values]
    return {value.removeprefix("https://schema.org/").removeprefix("http://schema.org/")
            for value in values if isinstance(value, str)}


def _text(value, limit=500):
    return value[:limit] if isinstance(value, str) and value.strip() else None


def _name_key(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def extract_candidates(html: str, *, verified_page_url: str,
                       expected_entity_name: str | None = None) -> list[dict]:
    """Extract inspectable schema references; caller establishes page authority.

    Name comparison uses the declared schema subject only. An exact name is
    recorded as a comparison result, never entity selection or use permission.
    Product.brand does not make a Product.name match a company or parent brand.
    Invalid scripts and references are skipped; oversized input fails explicitly.
    """
    page = public_reference(verified_page_url)
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("HTML exceeds the bounded discovery input")
    if expected_entity_name is not None and (not isinstance(expected_entity_name, str)
                                            or not expected_entity_name.strip()
                                            or len(expected_entity_name) > 500):
        raise ValueError("Expected entity name must be a bounded nonempty string")
    parser = _JsonLdScripts()
    parser.feed(html)
    nodes = []

    def walk(value, locator, depth=0):
        if depth > MAX_DEPTH or len(nodes) >= MAX_NODES:
            return
        if isinstance(value, dict):
            nodes.append((value, locator))
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    walk(child, locator + "/" + str(key).replace("~", "~0").replace("/", "~1"), depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if len(nodes) >= MAX_NODES:
                    break
                walk(child, locator + "/" + str(index), depth + 1)

    for index, raw in enumerate(parser.scripts):
        try:
            value = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        walk(value, f"jsonld[{index}]")
    # Duplicate @id declarations are ambiguous and must not resolve silently.
    references = {}
    for node, locator in nodes:
        if isinstance(node.get("@id"), str) and set(node) != {"@id"}:
            references.setdefault(urljoin(page, node["@id"]), []).append((node, locator))

    def dereference(value):
        if isinstance(value, dict) and set(value) == {"@id"}:
            found = references.get(urljoin(page, str(value["@id"])), [])
            if len(found) == 1:
                return found[0][0]
        return value

    def image_refs(value, locator, seen=()):
        if len(seen) > MAX_DEPTH:
            return
        if isinstance(value, list):
            for index, item in enumerate(value[:MAX_CANDIDATES]):
                yield from image_refs(item, locator + "/" + str(index), seen)
        elif isinstance(value, str):
            try:
                yield public_reference(value, base_url=page), locator, None, None
            except ValueError:
                return
        elif isinstance(value, dict):
            target = dereference(value)
            if target is not value:
                locator = references[urljoin(page, value["@id"])][0][1]
            if id(target) in seen:
                return
            for field in ("contentUrl", "url"):
                raw = target.get(field)
                if isinstance(raw, str):
                    try:
                        url = public_reference(raw, base_url=page)
                    except ValueError:
                        continue
                    dimensions = [target.get(key) if type(target.get(key)) is int and target[key] > 0 else None
                                  for key in ("width", "height")]
                    yield url, locator + "/" + field, *dimensions
                    # contentUrl is the full media reference when both are given.
                    return

    candidates = []
    seen = set()
    for node, locator in nodes:
        types = _types(node)
        kind = "logo" if types.intersection({"Organization", "Brand"}) else "packaging_candidate" if "Product" in types else None
        if not kind:
            continue
        field = "logo" if kind == "logo" else "image"
        name = _text(node.get("name"))
        subject = _text(node.get("@id"), 2048) or locator
        brand = dereference(node.get("brand"))
        brand_name = _text(brand if isinstance(brand, str) else brand.get("name") if isinstance(brand, dict) else None)
        match = "not_requested" if expected_entity_name is None else "exact" if name and _name_key(name) == _name_key(expected_entity_name) else "mismatch"
        for image_url, image_locator, width, height in image_refs(node.get(field), locator + "/" + field):
            identity = (subject, name, kind, image_url)
            if identity in seen:
                continue
            seen.add(identity)
            digest = hashlib.sha256(json.dumps([page, *identity], ensure_ascii=False).encode()).hexdigest()[:24]
            candidates.append({
                "candidate_id": "brand-media-discovery-" + digest,
                "discovery_version": VERSION,
                "asset_type": kind,
                "source_page_url": page,
                "original_image_url": image_url,
                "source_locator": image_locator,
                "schema_field_locator": locator + "/" + field,
                "declared_subject_id": _text(node.get("@id"), 2048),
                "declared_subject_types": sorted(types),
                "declared_subject_name": name,
                "declared_brand_name": brand_name,
                "declared_sku": _text(node.get("sku")),
                "declared_gtin": next((_text(node[key]) for key in ("gtin", "gtin8", "gtin12", "gtin13", "gtin14") if _text(node.get(key))), None),
                "width": width, "height": height,
                "identity_status": "unverified",
                "entity_name_match": match,
                "selection_reason": f"Declared schema {field}; identity, image content and usage basis require validation",
                "display_allowed": False, "cache_allowed": False, "export_allowed": False,
                "policy_status": "unresolved", "policy_source_url": None,
            })
            if len(candidates) >= MAX_CANDIDATES:
                return candidates
    return candidates
