"""Publisher-authored headings, bound to exact normalized article passages.

Presentation only: no generated titles, rewritten prose, or evidence decisions.
"""
from collections import Counter
from typing import Any

from lxml import etree, html as html_parser


def _key(text: str) -> str:
    return " ".join(text.split())


def publisher_heading_levels(html: str, passages: list[str]) -> dict[int, int]:
    """Match unique h2–h6 text already retained in the extracted body.

    Ambiguous duplicate text stays ordinary prose. Navigation and hidden/active
    elements cannot supply article headings. No additional text is introduced.
    """
    try:
        tree = html_parser.fromstring(html)
    except (etree.ParserError, ValueError, TypeError):
        return {}
    headings: dict[str, list[int]] = {}
    roots = tree.xpath("//article") or tree.xpath("//main") or [tree]
    for node in (node for root in roots for node in root.iter() if str(node.tag).lower() in {"h2", "h3", "h4", "h5", "h6"}):
        lineage = [node, *node.iterancestors()]
        if any(str(parent.tag).lower() in {"nav", "aside", "footer", "script", "style", "template"}
               or "hidden" in parent.attrib or parent.get("aria-hidden") == "true" for parent in lineage):
            continue
        text = _key(node.text_content())
        if text and len(text) <= 500:
            headings.setdefault(text, []).append(int(node.tag[1]))
    counts = Counter(_key(text) for text in passages)
    return {index: headings[key][0] for index, text in enumerate(passages)
            if (key := _key(text)) in headings and len(headings[key]) == 1 and counts[key] == 1}


def display_article_blocks(record: dict[str, Any], passages: list[str]) -> list[dict[str, Any]]:
    """Apply stored heading hints only to unchanged, unambiguous passages."""
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    rows = article.get("paragraphs") if isinstance(article.get("paragraphs"), list) else []
    hints: dict[str, list[int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        level = row.get("heading_level")
        if type(level) is int and 2 <= level <= 6:
            hints.setdefault(_key(str(row.get("text") or "")), []).append(level)
    counts = Counter(_key(text) for text in passages)
    return [{"text": text, "heading": len(hints.get(_key(text), [])) == 1 and counts[_key(text)] == 1,
             "source_level": hints.get(_key(text), [None])[0],
             "level": 3 if hints.get(_key(text), [6])[0] <= 3 else 4} for text in passages]
