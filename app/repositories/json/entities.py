"""Entity repository (V2 Phase 2B.1).

Entities are the one object type split across multiple folders by
`entity_type` (`data/entities/companies/`, `data/entities/varieties/`, ...)
rather than kept in one flat folder -- mirrors app/main.py's
`ENTITY_FOLDER_OVERRIDES`/`entity_folder()` exactly. Reads need no special
handling: `JsonRecordRepository`'s recursive `rglob("*.json")` over
`data/entities/` already finds every entity regardless of which subfolder
it lives in (the same traversal `all_entities()`'s
`load_json_files(DATA_DIR / "entities")` performs today). Only placing a
*new* entity into the correct subfolder needs entity-type awareness, so
only `_new_record_path()` is overridden; `get`/`list`/`update`/`delete`
are inherited unchanged and always rewrite a record in whatever subfolder
it already lives in, never relocating it.

Exercised by the live application today: get, list, create (only via
review/publish's implicit entity-creation path,
`unique_entity_id()`/`save_entity()` in app/main.py -- not migrated onto
this repository by this task). update/delete are not exercised by any
current route (no route edits or removes an entity record) -- provided as
uniform base-class mechanics, not as a currently-used application
capability. See this task's final report for the full per-repository
usage mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.repositories.base import InvalidRecord
from app.repositories.json.base import JsonRecordRepository, safe_record_id
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR

ENTITY_FOLDER_OVERRIDES = {
    "company": "companies",
    "variety": "varieties",
    "geography": "geographies",
    "person": "people",
    "berry": "berries",
}


def entity_folder(entity_type: str) -> str:
    return ENTITY_FOLDER_OVERRIDES.get(entity_type, f"{entity_type}s")


class EntityRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(folder=data_dir / "entities", schema_path=schemas_dir / "entity.schema.json")

    def _new_record_path(self, record: dict[str, Any]) -> Path:
        entity_type = record.get("entity_type")
        if not entity_type:
            raise InvalidRecord(record.get("id"), ["entity record has no 'entity_type' field"])
        return self._folder / entity_folder(entity_type) / f"{safe_record_id(record['id'])}.json"
