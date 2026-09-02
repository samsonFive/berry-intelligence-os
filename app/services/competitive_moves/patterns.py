"""Repeated-move patterns across a company's Competitive Moves.

Do not label a pattern as a 'strategy' unless the wording is already
supported by the underlying Developments. We surface REPEATED MOVE PATTERN.
"""

from __future__ import annotations

from app.services.competitive_moves.models import (
    MOVE_LABELS,
    PATTERN_THEMES,
    CompanyPattern,
    CompetitiveMove,
)


def detect_patterns(moves: list[CompetitiveMove]) -> list[CompanyPattern]:
    by_company: dict[str, list[CompetitiveMove]] = {}
    for move in moves:
        by_company.setdefault(move.company_id, []).append(move)

    patterns: list[CompanyPattern] = []
    for company_id, rows in by_company.items():
        types = {row.move_type for row in rows}
        name = rows[0].company_name
        latest = max((row.latest_update for row in rows), default="")
        if len(rows) < 2:
            continue
        matched = False
        for theme, allowed in PATTERN_THEMES:
            hit_types = tuple(sorted(types & allowed))
            supporting = [row for row in rows if row.move_type in allowed]
            if len(supporting) < 2:
                continue
            if len(hit_types) < 2 and not any(sum(1 for row in rows if row.move_type == item) >= 2 for item in hit_types):
                continue
            if theme == "LEADERSHIP + GEOGRAPHY":
                if not ("LEADERSHIP" in types and types & {"MARKET_ENTRY", "EXPANSION"}):
                    continue
            labels = [MOVE_LABELS.get(item, item) for item in (hit_types or sorted({row.move_type for row in supporting}))]
            why = (
                f"{name} has {len(supporting)} supporting moves across "
                + ", ".join(labels)
                + ". This is a repeated move pattern, not a proven strategy."
            )
            patterns.append(
                CompanyPattern(
                    company_id=company_id,
                    company_name=name,
                    theme=theme,
                    label="REPEATED MOVE PATTERN",
                    supporting_move_types=hit_types or tuple(sorted({row.move_type for row in supporting})),
                    supporting_move_ids=tuple(row.id for row in supporting),
                    why=why,
                    latest_update=latest,
                    move_count=len(supporting),
                )
            )
            matched = True
        if not matched and len(types) >= 2:
            patterns.append(
                CompanyPattern(
                    company_id=company_id,
                    company_name=name,
                    theme="MULTI-TYPE ACTIVITY",
                    label="REPEATED MOVE PATTERN",
                    supporting_move_types=tuple(sorted(types)),
                    supporting_move_ids=tuple(row.id for row in rows),
                    why=(
                        f"{name} has {len(rows)} moves across "
                        + ", ".join(MOVE_LABELS.get(item, item) for item in sorted(types))
                        + ". This is a repeated move pattern, not a proven strategy."
                    ),
                    latest_update=latest,
                    move_count=len(rows),
                )
            )
        type_counts: dict[str, int] = {}
        for row in rows:
            type_counts[row.move_type] = type_counts.get(row.move_type, 0) + 1
        repeats = [move_type for move_type, count in type_counts.items() if count >= 2]
        if repeats and not any(pattern.company_id == company_id for pattern in patterns):
            supporting = [row for row in rows if row.move_type in repeats]
            patterns.append(
                CompanyPattern(
                    company_id=company_id,
                    company_name=name,
                    theme="REPEATED " + " / ".join(repeats[:3]),
                    label="REPEATED MOVE PATTERN",
                    supporting_move_types=tuple(repeats),
                    supporting_move_ids=tuple(row.id for row in supporting),
                    why=f"{name} repeated {', '.join(MOVE_LABELS.get(item, item) for item in repeats)} across {len(supporting)} moves. Not labelled a strategy.",
                    latest_update=latest,
                    move_count=len(supporting),
                )
            )
    patterns.sort(key=lambda row: (row.move_count, row.latest_update), reverse=True)
    return patterns
