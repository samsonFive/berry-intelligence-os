"""Discussion questions for a War Room session.

Always returns real, honestly-labeled questions -- never fabricated
content dressed up as intelligence. A deterministic template pass over
the session's own real Moves/Market Reality data always runs first and is
the only thing shown when no completer is available. When a completer
*is* available, it may sharpen the phrasing, but every generated question
is validated to actually mention one of the real names in this session's
own scope before it's kept -- an ungrounded question is dropped, not
silently shown. Labeled "AI-generated discussion questions" only when the
completer genuinely ran; otherwise "Suggested discussion questions" --
never claim AI involvement that didn't happen.
"""

from __future__ import annotations

from typing import Any, Callable

_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 6,
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

_INSTRUCTIONS = (
    "You are drafting discussion prompts for a berry-industry strategy team meeting, grounded ONLY in the "
    "named companies, moves, and market figures listed below. Phrase each as an open interpretive question a "
    "strategy team would discuss -- never a factual claim, never invented figures, never invented company "
    "names beyond the ones listed. Use cautious framing (is/does/where/which...). Return 3-5 questions."
)


def _deterministic_questions(
    *,
    moves: list[dict[str, Any]],
    market_changes: list[dict[str, Any]],
    company_labels: list[str],
    geography_labels: list[str],
    berry_label: str,
) -> list[str]:
    questions: list[str] = []
    seen_companies: set[str] = set()
    for move in moves:
        name = str(move.get("company_name") or "")
        if not name or name in seen_companies:
            continue
        seen_companies.add(name)
        label = str(move.get("move_label") or move.get("move_type") or "activity")
        geo = ", ".join(move.get("geography_labels") or []) or (geography_labels[0] if geography_labels else "this market")
        questions.append(f"Is {name}'s {label.lower()} activity changing the competitive structure in {geo}?")
        if len(questions) >= 2:
            break
    company_move_counts: dict[str, int] = {}
    for move in moves:
        name = str(move.get("company_name") or "")
        if name:
            company_move_counts[name] = company_move_counts.get(name, 0) + 1
    repeated = [name for name, count in company_move_counts.items() if count >= 2]
    if repeated:
        questions.append(f"Does {repeated[0]}'s pattern of repeated moves indicate broader regional expansion, or several unrelated actions?")
    for change in market_changes[:2]:
        geo = str(change.get("geography_label") or (geography_labels[0] if geography_labels else berry_label))
        metric = str(change.get("metric") or "").replace("_", " ").title()
        questions.append(f"Which internal data would confirm or challenge the {metric.lower()} shift observed in {geo}?")
    if company_labels:
        gap_company = company_labels[-1]
        questions.append(f"Where does {gap_company}'s publicly visible activity differ from what internal knowledge already expects?")
    if not questions:
        subject = berry_label or (geography_labels[0] if geography_labels else "this scope")
        questions.append(f"What would need to be true for the current {subject} developments to represent a real strategic shift, not routine industry noise?")
    return questions[:5]


def generate_discussion_questions(
    *,
    moves: list[dict[str, Any]],
    market_changes: list[dict[str, Any]],
    company_labels: list[str],
    geography_labels: list[str],
    berry_label: str,
    completer: Callable[..., Any] | None = None,
    model: str = "anthropic/claude-haiku-4-5",
) -> dict[str, Any]:
    fallback = _deterministic_questions(
        moves=moves, market_changes=market_changes, company_labels=company_labels,
        geography_labels=geography_labels, berry_label=berry_label,
    )
    if completer is None:
        return {"questions": fallback, "source": "deterministic"}

    known_names = {str(n).lower() for n in company_labels}
    known_names |= {str(n).lower() for n in geography_labels}
    if berry_label:
        known_names.add(berry_label.lower())
    for move in moves[:10]:
        if move.get("company_name"):
            known_names.add(str(move["company_name"]).lower())

    digest_lines = [f"MOVE | {m.get('company_name')} | {m.get('move_label')} | {', '.join(m.get('geography_labels') or [])}" for m in moves[:10]]
    digest_lines += [f"MARKET | {c.get('geography_label')} | {c.get('metric')} | {c.get('pct_change')}%" for c in market_changes[:6]]
    if not digest_lines:
        return {"questions": fallback, "source": "deterministic"}

    prompt = _INSTRUCTIONS + "\n\nReal session data:\n- " + "\n- ".join(digest_lines)
    try:
        result = completer(prompt, schema=_QUESTION_SCHEMA, model=model, max_output_tokens=500)
        raw_questions = [str(q).strip() for q in (result.parsed.get("questions") or []) if str(q).strip()]
    except Exception:
        return {"questions": fallback, "source": "deterministic"}

    grounded = [q for q in raw_questions if any(name in q.lower() for name in known_names)]
    if not grounded:
        return {"questions": fallback, "source": "deterministic"}
    return {"questions": grounded[:5], "source": "ai"}
