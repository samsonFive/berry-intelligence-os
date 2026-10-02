"""Local report display formatting. Stored prose and references are untouched."""
from __future__ import annotations

import re
from typing import Any


def section_text(section: dict[str, Any], packet: dict[str, Any]) -> str:
    if section.get("edited_prose") is not None:
        return str(section["edited_prose"])
    text = str(section.get("generated_prose") or "")
    if section.get("status") != "structured":
        return text
    if section.get("section_id") in {"scope_method", "comparison_scope"}:
        labels = packet.get("display_names") or {}
        berry = packet.get("berry_id")
        return f"Report type: {str(packet.get('report_type') or '').replace('_', ' ').title()}. Berry: {labels.get(berry) or str(berry or 'All berries').removeprefix('berry-').replace('-', ' ').title()}."
    known = set(packet.get("known_ids") or [])
    for owner in (packet, packet.get("strategic_question") or {}):
        for bucket in ("signals", "assessments", "facts", "source_trace"):
            known.update(row["id"] for row in owner.get(bucket) or [] if row.get("id"))
    # Only a generated record prefix is hidden; unknown brackets and all
    # analyst-written text remain literal. Stable IDs stay in the stored report.
    return "\n".join(re.sub(r"^\[([^\]]+)\]\s*", lambda match: "" if match[1] in known else match[0], line) for line in text.splitlines())
