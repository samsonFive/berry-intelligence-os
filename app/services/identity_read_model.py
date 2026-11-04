"""Optional lookup preparation for a read-only identity-heavy page.

The original matcher makes every decision. This index supplies only a superset
of relevant rows in their original order. It lives within one explicit scope;
matching inputs are checked on every call and results are never cached.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
from typing import Any


_active_scope: ContextVar["IdentityReadModelScope | None"] = ContextVar(
    "identity_read_model_scope", default=None
)
_MAX_CATALOGS = 64
_SMALL_CATALOG = 3


class _Catalog:
    def __init__(self, varieties, identity):
        # Hold original references as well as the owned snapshot: object IDs
        # cannot be recycled while this catalog remains in the request scope.
        self.references = tuple(varieties)
        # Validate supported matching inputs once, before copying/coercing any
        # opaque values. Freshness below compares the complete owned records.
        for record in varieties:
            identity._catalog_record_signature(record)
        self.records = deepcopy(list(varieties))
        self.names: dict[str, set[int]] = {}
        self.registrations: dict[str, set[int]] = {}
        self.tokens: dict[str, set[int]] = {}
        self.berries: dict[int, set[str]] = {}
        self.valid: set[int] = set()
        for index, record in enumerate(self.records):
            if record.get("entity_type") not in (None, "variety") or not str(record.get("id") or ""):
                continue
            self.valid.add(index)
            self.berries[index] = identity._berries(record)
            for value in identity._registration_ids(record):
                self.registrations.setdefault(value, set()).add(index)
            for text, _role in identity._identity_strings(record):
                folded = identity.fold_identity(text)
                if len(folded) >= identity._MIN_FOLD:
                    self.names.setdefault(folded, set()).add(index)
                for token in folded.split():
                    self.tokens.setdefault(token, set()).add(index)

    def relevant_rows(self, candidate, identity):
        berries = identity._berries(candidate)
        folds = [identity.fold_identity(text) for text, _role in identity.candidate_query_names(candidate)]
        folds = [value for value in folds if len(value) >= identity._MIN_FOLD]
        exact: set[int] = set()
        for value in identity.candidate_registration_ids(candidate):
            exact.update(self.registrations.get(value, ()))
        for value in folds:
            exact.update(self.names.get(value, ()))
        # The name/registration maps contain only valid catalog rows. Apply
        # crop compatibility to that shortlist instead of scanning the full
        # catalog for every query. An incompatible exact name must still
        # allow the original matcher's compatible token-overlap fallback.
        exact = {
            index for index in exact
            if not berries or not self.berries[index] or berries & self.berries[index]
        }
        if exact:
            selected = exact
        else:
            # A contiguous overlap necessarily shares a token. This is a
            # conservative superset; the matcher still checks contiguity.
            selected: set[int] = set()
            for value in folds:
                for token in value.split():
                    selected.update(self.tokens.get(token, ()))
            selected = {
                index for index in selected
                if not berries or not self.berries[index] or berries & self.berries[index]
            }
        return [self.records[index] for index in sorted(selected)]


class IdentityReadModelScope:
    def __init__(self):
        self._catalogs: dict[tuple[int, ...], _Catalog] = {}

    @property
    def catalog_count(self):
        return len(self._catalogs)

    def resolve(self, matcher, candidate, varieties):
        if not isinstance(varieties, (list, tuple)) or len(varieties) <= _SMALL_CATALOG:
            return matcher(candidate, varieties)
        from app.services.variety_universe import identity
        if not identity._index_candidate_supported(candidate):
            return matcher(candidate, varieties)

        try:
            key = tuple(id(row) for row in varieties)
            catalog = self._catalogs.get(key)
            # Dict/list equality runs in C and checks all current fields,
            # including in-place nested edits. Rebuilding Python signatures for
            # every row on every lookup was measured slower than the matcher.
            if catalog is None or list(varieties) != catalog.records:
                if catalog is None and len(self._catalogs) >= _MAX_CATALOGS:
                    return matcher(candidate, varieties)
                catalog = _Catalog(varieties, identity)
                if list(varieties) != catalog.records:
                    return matcher(candidate, varieties)
                self._catalogs[key] = catalog
            rows = catalog.relevant_rows(candidate, identity)
        except (AttributeError, TypeError, ValueError):
            # Unsupported/non-JSON-like inputs retain the original behavior,
            # including any error the original matcher would itself raise.
            return matcher(candidate, varieties)
        return matcher(candidate, rows)


def resolve_identity_batch(candidates, varieties):
    """Match one owned batch with the unchanged resolver and catalog index.

    Unlike independent lookups, this explicit pure calculation snapshots its
    complete inputs once. It never retains that catalog across calls: edits in
    the next batch are reloaded. Unsupported inputs use the original matcher
    without extra coercion or iterator consumption during preparation.
    """
    from app.services.variety_universe import identity
    matcher = identity.resolve_identity.__wrapped__
    if (type(candidates) not in (list, tuple)
            or type(varieties) not in (list, tuple)
            or len(varieties) <= _SMALL_CATALOG
            or not all(identity._index_candidate_supported(row) for row in candidates)):
        return [matcher(row, varieties) for row in candidates]
    try:
        catalog = _Catalog(varieties, identity)
        queries = deepcopy(candidates)
        if list(varieties) != catalog.records:
            return [matcher(row, varieties) for row in candidates]
    except (AttributeError, TypeError, ValueError):
        return [matcher(row, varieties) for row in candidates]
    return [matcher(row, catalog.relevant_rows(row, identity)) for row in queries]


@contextmanager
def identity_read_model_scope():
    """Opt in for one read-only render; never retain state across requests."""
    current = _active_scope.get()
    if current is not None:
        yield current
        return
    scope = IdentityReadModelScope()
    token = _active_scope.set(scope)
    try:
        yield scope
    finally:
        _active_scope.reset(token)


def with_identity_catalog_index(matcher):
    @wraps(matcher)
    def wrapped(candidate: dict[str, Any], varieties: list[dict[str, Any]]) -> dict[str, Any]:
        scope = _active_scope.get()
        return matcher(candidate, varieties) if scope is None else scope.resolve(matcher, candidate, varieties)
    return wrapped
