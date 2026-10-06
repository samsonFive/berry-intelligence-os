"""Local report display formatting. Stored prose and references are untouched."""
from __future__ import annotations

import re
from typing import Any


def report_sources(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Stable source numbering across editor and independently generated PDF."""
    rows = packet.get("source_trace") or (packet.get("strategic_question") or {}).get("source_trace") or []
    return sorted(rows, key=lambda row: (str(row.get("title") or "").casefold(), str(row.get("id") or "")))


def section_title(section: dict[str, Any]) -> str:
    """Translate stock workflow labels; keep custom section titles literal."""
    title = str(section.get("title") or section.get("section_id") or "Report section")
    return {
        "Signals": "Emerging patterns",
        "Assessments": "What it could mean",
        "Assessments / Strategic Implications": "What it could mean",
        "Scope & Method": "Scope and approach",
        "Intelligence Gaps": "Questions still open",
    }.get(title, title)


def display_sections(report: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Takeaways and readable findings precede supporting/editing disclosures."""
    def priority(section: dict[str, Any]) -> int:
        if section.get("section_id") in {"executive_summary", "executive_takeaway"}:
            return 0
        if ((section.get("status") in {"unavailable", "unsupported"} and section.get("edited_prose") is None)
                or section.get("section_id") in {"sources", "evidence_appendix", "scope_method", "known_gaps"}):
            return 2
        return 1
    return [{**section, "display_text": section_text(section, packet), "display_title": section_title(section)}
            for section in sorted(report.get("sections") or [], key=priority)]


def section_text(section: dict[str, Any], packet: dict[str, Any]) -> str:
    if section.get("edited_prose") is not None:
        return str(section["edited_prose"])
    if section.get("status") == "unavailable":
        return "Not drafted yet. Add commentary and check the supporting sources before sharing."
    text = str(section.get("generated_prose") or "")
    if section.get("section_id") in {"scope_method", "comparison_scope"}:
        labels = packet.get("display_names") or {}
        berry = packet.get("berry_id")
        return f"Report type: {str(packet.get('report_type') or '').replace('_', ' ').title()}. Berry: {labels.get(berry) or str(berry or 'All berries').removeprefix('berry-').replace('-', ' ').title()}."
    known = set(packet.get("known_ids") or [])
    for owner in (packet, packet.get("strategic_question") or {}):
        for bucket in ("signals", "assessments", "facts", "source_trace"):
            known.update(row["id"] for row in owner.get(bucket) or [] if row.get("id"))
    references = {row["id"]: f"Source {index + 1}" for index, row in enumerate(report_sources(packet)) if row.get("id")}
    # Only technical references in generated prose are projected. Source links
    # remain in the appendix; ordinary bracketed qualifiers and edits are literal.
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\[([^\]]+)\]\s*", lambda match: "" if match[1] in known else match[0], line)
        line = re.sub(r"\[([^\]]+)\]", lambda match: references.get(match[1], match[0]), line)
        line = re.sub(r"\[(?:web:\d+|(?:ev|fact|sig|assessment)-[a-z0-9-]+)\]", "(reference unavailable)", line)
        lines.append(line)
    return "\n".join(lines)
