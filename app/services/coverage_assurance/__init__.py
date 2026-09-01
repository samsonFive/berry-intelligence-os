"""Public Intelligence Coverage Assurance V1.

Distinguishes known publishers from actively collected Sources, technical
health from intelligence yield, and independent benchmark misses from
trusted Evidence. GET never writes Sources or Evidence. There is no
completeness score. Miss classification is app.services.recall_audit.classify's
9-class taxonomy, reused here rather than reimplemented.
"""

from app.services.coverage_assurance.reconcile import (
    COLLECTED,
    INTENTIONALLY_EXCLUDED,
    KNOWN_NOT_COLLECTED,
    UNKNOWN_SOURCE_IDENTITY,
)
from app.services.coverage_assurance.report import (
    FORBIDDEN_COMPLETENESS_CLAIMS,
    build_coverage_report,
    coverage_attention_count,
    variety_coverage_slice,
)
from app.services.recall_audit.classify import (
    DATE_CHRONOLOGY_FAILURE,
    ENTITY_FOUND_IDENTITY_UNRESOLVED,
    FULLY_REPRESENTED,
    GEOGRAPHY_LINKAGE_FAILURE,
    ITEM_COLLECTED_ENTITY_MISSED,
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_UNKNOWN,
    UNSUPPORTED_NOT_QUALIFYING,
    classify_result,
)

__all__ = [
    "FORBIDDEN_COMPLETENESS_CLAIMS",
    "COLLECTED",
    "KNOWN_NOT_COLLECTED",
    "UNKNOWN_SOURCE_IDENTITY",
    "INTENTIONALLY_EXCLUDED",
    "SOURCE_UNKNOWN",
    "SOURCE_KNOWN_NOT_COLLECTED",
    "SOURCE_COLLECTED_ITEM_MISSED",
    "ITEM_COLLECTED_ENTITY_MISSED",
    "ENTITY_FOUND_IDENTITY_UNRESOLVED",
    "DATE_CHRONOLOGY_FAILURE",
    "GEOGRAPHY_LINKAGE_FAILURE",
    "FULLY_REPRESENTED",
    "UNSUPPORTED_NOT_QUALIFYING",
    "build_coverage_report",
    "coverage_attention_count",
    "classify_result",
    "variety_coverage_slice",
]
