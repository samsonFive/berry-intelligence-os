"""Bounded plain-text sections from public Google Patents HTML.

This is a private reader projection, not patent/variety evidence extraction.
Never render publisher HTML or infer identity, legal status or reviewed facts.
"""
from __future__ import annotations

from urllib.parse import urlparse

from lxml import etree, html as html_parser

MAX_BLOCKS = 240
MAX_TEXT = 40_000
MAX_BLOCK_TEXT = 4_000


def _span(value):
    try:
        return max(1, min(24, int(value)))
    except (ValueError, TypeError):
        return 1


def patent_document(html: str, url: str) -> dict | None:
    parsed = urlparse(url)
    if parsed.hostname != "patents.google.com" or not parsed.path.startswith("/patent/"):
        return None
    try:
        root = html_parser.fromstring(html)
    except (etree.ParserError, ValueError):
        return None
    # Active content and site chrome never become document passages.
    for node in root.xpath("//script | //style | //noscript | //iframe | //form"):
        node.drop_tree()
    sections = root.xpath('//section[@itemprop="abstract" or @itemprop="description" or @itemprop="claims"]')
    if not sections:
        return None
    blocks: list[dict] = []
    size = 0
    limited = False

    def text(node):
        return " ".join(node.text_content().split())

    def add(kind, value, **extra):
        nonlocal size, limited
        if not value:
            return
        remaining = MAX_TEXT - size
        if len(blocks) >= MAX_BLOCKS or remaining <= 0:
            limited = True
            return
        bound = min(remaining, MAX_BLOCK_TEXT)
        if len(value) > bound:
            value = value[:bound]
            limited = True
        blocks.append({"kind": kind, "text": value, **extra})
        size += len(value)

    def walk(node):
        nonlocal limited
        if len(blocks) >= MAX_BLOCKS or size >= MAX_TEXT:
            limited = True
            return
        tag = str(node.tag).lower()
        classes = set(str(node.get("class") or "").split())
        if tag in {"heading", "h2", "h3", "h4", "h5", "h6"}:
            add("heading", text(node), level=4)
        elif tag == "table":
            for row in node.xpath(".//tr"):
                nodes = row.xpath("./th | ./td")
                cells = [text(cell) for cell in nodes]
                if cells:
                    budget = min(MAX_BLOCK_TEXT, MAX_TEXT - size)
                    bounded = []
                    for cell in cells[:24]:
                        if budget <= 0:
                            limited = True
                            break
                        bounded.append(cell[:budget])
                        if len(cell) > budget:
                            limited = True
                        budget -= len(bounded[-1]) + 3
                    if len(cells) > 24:
                        limited = True
                    add("table_row", " | ".join(bounded), cells=bounded,
                        spans=[{"colspan": _span(cell.get("colspan")), "rowspan": _span(cell.get("rowspan"))} for cell in nodes[:len(bounded)]])
        elif tag == "li":
            nested = node.xpath("./ul | ./ol")
            if not nested:
                add("list_item", text(node))
            else:
                pieces = [node.text or ""]
                for child in node:
                    if str(child.tag).lower() not in {"ul", "ol"}:
                        pieces.append(child.text_content())
                    pieces.append(child.tail or "")
                add("list_item", " ".join(" ".join(pieces).split()))
                for child in nested:
                    walk(child)
        elif (tag == "p" or classes & {"description-paragraph", "claim-text", "claim-statement", "abstract"}) and not node.xpath(".//table"):
            add("paragraph", text(node))
        else:
            add("paragraph", " ".join((node.text or "").split()))
            for child in node:
                walk(child)
                add("paragraph", " ".join((child.tail or "").split()))

    seen = set()
    for section in sections:
        key = section.get("itemprop")
        if key in seen:
            continue
        seen.add(key)
        content = section.xpath('./*[@itemprop="content"]')
        if not content or not text(content[0]):
            continue
        title = section.xpath("./h2")
        add("heading", text(title[0]) if title else key.capitalize(), level=3, section=key)
        walk(content[0])
    if not any(row["kind"] != "heading" for row in blocks):
        return None
    return {"blocks": blocks, "truncated": limited}


def display_document_blocks(value: object) -> list[dict]:
    """Only bounded text and known roles cross the template boundary."""
    if not isinstance(value, list):
        return []
    output, size = [], 0
    for row in value[:MAX_BLOCKS]:
        if not isinstance(row, dict) or row.get("kind") not in {"heading", "paragraph", "list_item", "table_row"}:
            continue
        text = str(row.get("text") or "")[:min(MAX_BLOCK_TEXT, MAX_TEXT - size)]
        if not text:
            continue
        block = {"kind": row["kind"], "text": text}
        if row["kind"] == "heading":
            block["level"] = 3 if row.get("level") == 3 else 4
            if row.get("section") in {"abstract", "description", "claims"}:
                block["section"] = row["section"]
        if row["kind"] == "table_row":
            # Reconstruct a bounded display projection even for old/malformed caches.
            cells, budget = [], len(text)
            raw_cells = row.get("cells") if isinstance(row.get("cells"), list) else []
            for cell in raw_cells[:24]:
                value = str(cell)[:max(0, budget)]
                cells.append(value)
                budget -= len(value) + 3
                if budget <= 0:
                    break
            block["cells"] = cells or [text]
            raw_spans = row.get("spans") if isinstance(row.get("spans"), list) else []
            block["spans"] = []
            for index in range(len(block["cells"])):
                span = raw_spans[index] if index < len(raw_spans) and isinstance(raw_spans[index], dict) else {}
                block["spans"].append({key: _span(span.get(key)) for key in ("colspan", "rowspan")})
        output.append(block)
        size += len(text)
        if size >= MAX_TEXT:
            break
    return output
