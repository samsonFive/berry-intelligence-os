"""Strategic Question repository (V2 Phase 2B.1).

Exercised by the live application today: get, list
(`load_strategic_questions()`/`strategic_question_by_id()`) only. **No
route in the current application creates, edits, or removes a Strategic
Question at all** -- all 9 live records were seeded once from the Berries
Domain Pack (Phase 1B) and the application only ever reads them. create/
update/delete are provided as uniform base-class mechanics, not as
currently-used application capability, more so here than for any other
repository in this set."""

from __future__ import annotations

from pathlib import Path

from app.repositories.json.base import JsonRecordRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR


class StrategicQuestionRepository(JsonRecordRepository):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> None:
        super().__init__(
            folder=data_dir / "strategic-questions", schema_path=schemas_dir / "strategic-question.schema.json"
        )
