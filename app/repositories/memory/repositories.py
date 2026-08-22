from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from app.repositories.base import DuplicateRecord, InvalidRecord, RecordNotFound
from app.repositories.paths import SCHEMAS_DIR


class MemoryRecordRepository:
    """Logical record repository with no filesystem persistence.

    Records crossing the boundary are deep-copied so callers cannot mutate
    stored state through objects returned by create/get/list/update.
    """

    def __init__(self, schema_path: Path | None = None, *, order_key: Callable[[dict[str, Any]], Any] | None = None) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._validator = None
        if schema_path is not None:
            self._validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")), format_checker=FormatChecker())
        self._order_key = order_key or (lambda record: record["id"])

    def _validate(self, record: dict[str, Any]) -> None:
        errors = [error.message for error in self._validator.iter_errors(record)] if self._validator else []
        if errors:
            raise InvalidRecord(record.get("id"), errors)

    def get(self, record_id: str) -> dict[str, Any] | None:
        record = self._records.get(record_id)
        return deepcopy(record) if record is not None else None

    def list(self, **filters: Any) -> list[dict[str, Any]]:
        records = [record for record in self._records.values() if all(record.get(k) == v for k, v in filters.items())]
        return deepcopy(sorted(records, key=self._order_key))

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        record_id = record.get("id")
        if not record_id:
            raise InvalidRecord(None, ["record has no 'id' field"])
        if record_id in self._records:
            raise DuplicateRecord(record_id)
        self._validate(record)
        self._records[record_id] = deepcopy(record)
        return deepcopy(record)

    def create_many(self, records: list[dict[str, Any]]) -> None:
        incoming = [record.get("id") for record in records]
        if any(record_id is None for record_id in incoming):
            raise InvalidRecord(None, ["record has no 'id' field"])
        if self._records.keys() & set(incoming) or len(incoming) != len(set(incoming)):
            duplicate = next(record_id for record_id in incoming if record_id in self._records or incoming.count(record_id) > 1)
            raise DuplicateRecord(duplicate)
        for record in records:
            self._validate(record)
        for record in records:
            self._records[record["id"]] = deepcopy(record)

    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        if record_id not in self._records:
            raise RecordNotFound(record_id)
        if record.get("id") != record_id:
            raise InvalidRecord(record_id, ["update() record's 'id' does not match record_id argument"])
        self._validate(record)
        self._records[record_id] = deepcopy(record)
        return deepcopy(record)

    def delete(self, record_id: str) -> None:
        if record_id not in self._records:
            raise RecordNotFound(record_id)
        del self._records[record_id]


def _evidence_order(record: dict[str, Any]) -> tuple[str, str]:
    return (record.get("published_date") or record.get("captured_date") or "", record["id"])


def get_memory_repositories(schemas_dir: Path = SCHEMAS_DIR) -> SimpleNamespace:
    schema = lambda name: schemas_dir / f"{name}.schema.json"
    repos = SimpleNamespace(
        entities=MemoryRecordRepository(schema("entity")),
        evidence=MemoryRecordRepository(schema("evidence"), order_key=_evidence_order),
        facts=MemoryRecordRepository(schema("fact")),
        relationships=MemoryRecordRepository(schema("relationship")),
        signals=MemoryRecordRepository(schema("signal")),
        assessments=MemoryRecordRepository(schema("assessment")),
        recommendations=MemoryRecordRepository(schema("recommendation")),
        strategic_questions=MemoryRecordRepository(schema("strategic-question")),
        sources=MemoryRecordRepository(),
    )
    # JSON Evidence ordering is descending.
    original_list = repos.evidence.list
    repos.evidence.list = lambda **filters: list(reversed(original_list(**filters)))
    return repos
