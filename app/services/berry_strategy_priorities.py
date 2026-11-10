"""Load analyst-authored opportunities from the private runtime."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

CRITERIA = {
    "market": "Market attractiveness",
    "fit": "Strategic fit",
    "access": "Access and feasibility",
    "timing": "Timing",
}
OPPORTUNITIES_PATH = Path("berry_strategy/opportunities.json")
LOGGER = logging.getLogger(__name__)


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    crop: str
    region: str
    geography: str
    target: str
    entity_ids: list[str]
    title: str
    horizon: str
    roles: list[str]
    benefit: str
    risk: str
    confidence: str
    next_step: str
    scores: dict[str, tuple[Annotated[int, Field(ge=1, le=5)], str]]
    frameworks: list[str]
    tension: str
    sources: list[tuple[str, str, str, str, str, list[str]]]
    contrary_source_ids: list[str] = Field(default_factory=list)

    @field_validator("scores")
    @classmethod
    def check_criteria(cls, scores):
        if scores.keys() != CRITERIA.keys():
            raise ValueError("Each opportunity needs all four scoring criteria.")
        return scores


_OPPORTUNITIES = TypeAdapter(list[Opportunity])


def load_opportunities(inbox_dir: Path) -> tuple[dict, ...]:
    """An unconfigured workspace can still generate a cited evidence review."""
    try:
        raw = (inbox_dir / OPPORTUNITIES_PATH).read_bytes()
        rows = _OPPORTUNITIES.validate_json(raw)
    except FileNotFoundError:
        return ()
    except (OSError, ValidationError):
        LOGGER.warning("Private Berry Strategy opportunities could not be loaded.")
        return ()
    return tuple(row.model_dump(mode="json") for row in rows)
