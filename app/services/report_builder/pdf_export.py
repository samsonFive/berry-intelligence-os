"""AI-Assisted Report Builder V1 -- PDF export.

Server-side rendering only, via reportlab (no external SaaS upload, no
browser binary). Produces a professional, internally-circulable PDF:
title, generation date, an explicit intelligence/data cutoff date,
scope summary, every report section (structured and AI-drafted alike),
a source/citation appendix, page numbers, a configurable
"Internal / Confidential" label, and an "AI-assisted; analyst-reviewed"
provenance marker on every page footer -- never presented as if a human
wrote it unassisted, and never presented as if it were canonical
intelligence.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

CONFIDENTIALITY_DEFAULT = "Internal / Confidential"
PROVENANCE_MARKER = "AI-assisted; analyst-reviewed"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontSize=22, spaceAfter=6),
        "meta": ParagraphStyle("ReportMeta", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#555555")),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], spaceBefore=16, spaceAfter=6),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=10, leading=14, spaceAfter=8),
        "unsupported": ParagraphStyle(
            "ReportUnsupported", parent=base["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#8a6d00"), spaceAfter=8
        ),
        "footer": ParagraphStyle("ReportFooter", parent=base["Normal"], fontSize=7.5, textColor=colors.HexColor("#777777")),
        "source": ParagraphStyle("ReportSource", parent=base["Normal"], fontSize=8.5, leading=11, spaceAfter=3),
    }


def _footer(canvas, doc, *, confidentiality: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(0.75 * inch, 0.5 * inch, f"{confidentiality} • {PROVENANCE_MARKER}")
    canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _cutoff_date(packet: dict[str, Any]) -> str:
    """The newest date actually present among the packet's own dated
    items -- never "today" (that would falsely imply live freshness of
    every fact in the report, not just of the export action itself)."""
    dates: list[str] = []
    for row in packet.get("recent_developments") or []:
        if row.get("date"):
            dates.append(row["date"])
    for row in (packet.get("strategic_question") or {}).get("recent_evidence") or []:
        if row.get("date"):
            dates.append(str(row["date"]))
    return max(dates) if dates else "Unknown (no dated Evidence in packet)"


def render_report_pdf(
    report: dict[str, Any],
    packet: dict[str, Any],
    coverage: dict[str, Any],
    *,
    confidentiality: str = CONFIDENTIALITY_DEFAULT,
) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=LETTER, topMargin=0.9 * inch, bottomMargin=0.85 * inch, leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    template = PageTemplate(id="report", frames=[frame], onPage=lambda c, d: _footer(c, d, confidentiality=confidentiality))
    doc.addPageTemplates([template])

    story: list[Any] = [NextPageTemplate("report")]
    story.append(Paragraph(report.get("title") or "Untitled report", styles["title"]))
    story.append(Paragraph(f"Generated {date.today().isoformat()} — Intelligence/data cutoff: {_cutoff_date(packet)}", styles["meta"]))
    story.append(Paragraph(f"{confidentiality} — {PROVENANCE_MARKER}", styles["meta"]))
    story.append(Spacer(1, 14))

    scope = report.get("scope") or {}
    scope_lines = [f"Report type: {report.get('report_type', '')}"]
    if scope.get("berry_id"):
        scope_lines.append(f"Berry: {scope['berry_id']}")
    if scope.get("geography_ids"):
        scope_lines.append(f"Geographies: {', '.join(scope['geography_ids'])}")
    if scope.get("company_ids"):
        scope_lines.append(f"Companies: {', '.join(scope['company_ids'])}")
    if scope.get("variety_ids"):
        scope_lines.append(f"Varieties: {', '.join(scope['variety_ids'])}")
    story.append(Paragraph("Scope", styles["h2"]))
    for line in scope_lines:
        story.append(Paragraph(line, styles["body"]))

    counts = coverage.get("counts") or {}
    if counts:
        story.append(Paragraph("Intelligence Coverage", styles["h2"]))
        rows = [[key.replace("_", " ").title(), str(value)] for key, value in counts.items()]
        table = Table([["Category", "Count"], *rows], colWidths=[3.2 * inch, 1.2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 6))

    gaps = coverage.get("gaps") or []
    if gaps:
        story.append(Paragraph("Known Gaps", styles["h2"]))
        for gap in gaps:
            story.append(Paragraph(f"• {gap}", styles["body"]))

    for section in report.get("sections") or []:
        story.append(Paragraph(section.get("title") or section.get("section_id") or "", styles["h2"]))
        text = section.get("edited_prose") or section.get("generated_prose") or ""
        status = section.get("status") or ""
        if not text:
            story.append(Paragraph("(No content.)", styles["unsupported"]))
            continue
        style = styles["unsupported"] if status in ("unsupported", "unavailable") else styles["body"]
        for paragraph in text.split("\n\n"):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), style))
        citation_ids = section.get("citation_ids") or []
        if citation_ids:
            story.append(Paragraph(f"Sources: {', '.join(citation_ids)}", styles["source"]))

    source_trace = packet.get("source_trace") or (packet.get("strategic_question") or {}).get("source_trace") or []
    if source_trace:
        story.append(Paragraph("Sources / Appendix", styles["h2"]))
        for row in source_trace:
            label = row.get("title") or row.get("id") or ""
            date_text = row.get("date") or row.get("published_date") or ""
            source_name = row.get("source_name") or ""
            story.append(Paragraph(f"[{row.get('id')}] {label} — {source_name} ({date_text or 'date unknown'})", styles["source"]))

    included = [row for row in (report.get("external_research_appendix") or []) if row.get("included_in_report")]
    if included:
        story.append(Paragraph("External Public Research — Unreviewed", styles["h2"]))
        story.append(
            Paragraph(
                "These findings were NOT sourced from this system's trusted intelligence, were not "
                "reviewed for accuracy, and are not canonical Evidence. An analyst selected them for "
                "inclusion as external context only.",
                styles["unsupported"],
            )
        )
        for row in included:
            gap = f" [{row['gap_label']}]" if row.get("gap_label") else ""
            retrieved = f", retrieved {row['retrieved_at']}" if row.get("retrieved_at") else ""
            provider = f" via {row['provider']}" if row.get("provider") else ""
            story.append(
                Paragraph(
                    f"• {row.get('title') or row.get('url') or ''}{gap} — {row.get('url') or ''}{provider}{retrieved}",
                    styles["source"],
                )
            )

    doc.build(story)
    return buffer.getvalue()
