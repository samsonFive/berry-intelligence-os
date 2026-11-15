"""Read-only public projection, independent of review/confidence.

Snapshot raw families once, derive private support transitively, and expose
projected get/list methods only. Public source/entity records keep their own
content while private backlinks are removed; mixed-support derived conclusions
are withheld rather than silently changing their evidential basis.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from app.repositories.base import StorageError
from app.services.information_storage import is_public_record

FAMILIES = ("entities", "evidence", "facts", "relationships", "signals", "assessments",
            "recommendations", "strategic_questions", "sources", "market_observations")
DERIVED_FAMILIES = frozenset(FAMILIES) - {"entities", "evidence", "sources"}
ID_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_DROP = object()
_LINK_IDENTITY_FIELDS = frozenset({"id", "url", "href", "uri", "path"})


def _explicitly_private(record):
    return "publication_scope" in record and record["publication_scope"] != "public"


def _id_tokens(value):
    for token in ID_TOKEN.findall(value):
        yield token
        yield token.rstrip(".")
        if token.endswith((".json", ".html")):
            yield token.rsplit(".", 1)[0]


def _references(value, known_ids, *, top=True):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if top and key == "id":
                continue
            if key in known_ids:
                found.add(key)
            found.update(_references(child, known_ids, top=False))
    elif isinstance(value, list):
        for child in value:
            found.update(_references(child, known_ids, top=False))
    elif isinstance(value, str):
        found.update(token for token in _id_tokens(value) if token in known_ids)
    return found


def _private_link(value, blocked, field):
    return isinstance(value, str) and (value in blocked or
        any(token in blocked for token in _id_tokens(value)))


def _scrub(value, blocked, *, field="", top=False, in_list=False):
    if isinstance(value, dict):
        # A link entry's label/notes belong to its private target. A general
        # attribute map may also have public siblings that must be retained.
        if not top and any(
            (in_list or key in _LINK_IDENTITY_FIELDS or key.endswith(("_id", "_url", "_href", "_uri")))
            and _private_link(child, blocked, key) for key, child in value.items()
        ):
            return _DROP
        cleaned = {}
        for key, child in value.items():
            if key in blocked or _private_link(child, blocked, key):
                continue
            projected = _scrub(child, blocked, field=key)
            if projected is not _DROP:
                cleaned[key] = projected
        return cleaned
    if isinstance(value, list):
        return [projected for child in value if (projected := _scrub(child, blocked, field=field, in_list=True)) is not _DROP]
    return _DROP if _private_link(value, blocked, field) else deepcopy(value)


class PublicRepositoryView:
    def __init__(self, raw, rows):
        self._raw = raw
        self._rows = rows
        self._by_id = {row["id"]: row for row in rows if row.get("id")}

    def get(self, record_id):
        row = self._by_id.get(record_id)
        return deepcopy(row) if row is not None else None

    def list(self, **filters):
        return deepcopy([row for row in self._rows if all(row.get(key) == value for key, value in filters.items())])

    def latest_by_key(self, **filters):
        latest = {}
        for row in self.list(**filters):
            key = tuple(row.get(field) for field in ("metric", "source_commodity_code", "form", "geography", "period"))
            if key not in latest or row.get("captured_at", "") >= latest[key].get("captured_at", ""):
                latest[key] = row
        return sorted(latest.values(), key=lambda row: row.get("period", ""))

    def _readonly(self, *args, **kwargs):
        raise StorageError("Public repository projections are read-only")

    create = create_many = update = delete = upsert = save = _readonly

    def __getattr__(self, name):
        if name in {"data_dir", "schemas_dir", "information_store_enabled"}:
            return getattr(self._raw, name)
        raise AttributeError(name)


class PublicRepositories:
    public_view = True

    def __init__(self, raw):
        self._query_services = None
        self._domain_services = None
        snapshots = {}
        repositories = {}
        for family in FAMILIES:
            repository = getattr(raw, family, None)
            if repository is not None:
                repositories[family] = repository
                snapshots[family] = repository.list()
        known_ids = {row["id"] for rows in snapshots.values() for row in rows if row.get("id")}
        blocked = {row["id"] for family, rows in snapshots.items() for row in rows
                   if row.get("id") and (_explicitly_private(row) or family == "evidence" and not is_public_record(row))}
        dependencies = {row["id"]: _references(row, known_ids) for family, rows in snapshots.items()
                        if family in DERIVED_FAMILIES for row in rows if row.get("id")}
        changed = True
        while changed:
            changed = False
            for key, refs in dependencies.items():
                if key not in blocked and refs.intersection(blocked):
                    blocked.add(key)
                    changed = True
        self._views = {}
        for family, rows in snapshots.items():
            projected = [_scrub(row, blocked, top=True) for row in rows if row.get("id") not in blocked]
            self._views[family] = PublicRepositoryView(repositories[family], projected)

    def __getattr__(self, name):
        if name in self._views:
            return self._views[name]
        raise AttributeError(name)


def public_repositories(repositories):
    return repositories if getattr(repositories, "public_view", False) else PublicRepositories(repositories)
