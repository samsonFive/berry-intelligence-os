"""AI-Assisted Report Builder V1 -- PDF export.

Server-side rendering only, via reportlab (no external SaaS upload, no
browser binary). Produces a professional, internally-circulable PDF:
title, generation date, an explicit intelligence/data cutoff date,
scope summary, every report section (structured and AI-drafted alike),
a source/citation appendix, page numbers, a configurable
"Internal / Confidential" label, and a working-report marker requiring
analyst review on every page footer. Generation does not certify review
and report prose is not canonical intelligence.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from app.services.report_builder.presentation import section_text

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

CONFIDENTIALITY_DEFAULT = "Internal / Confidential"
PROVENANCE_MARKER = "Working report; analyst review required"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], alignment=0, fontSize=27, leading=31, textColor=colors.HexColor("#183e2b"), spaceAfter=12),
        "meta": ParagraphStyle("ReportMeta", parent=base["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#526459"), spaceAfter=5),
        "kicker": ParagraphStyle("ReportKicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#347147"), spaceAfter=13),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], fontSize=16, leading=20, textColor=colors.HexColor("#214c35"), spaceBefore=19, spaceAfter=9),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=10, leading=15, textColor=colors.HexColor("#273c30"), spaceAfter=9),
        "takeaway": ParagraphStyle("ReportTakeaway", parent=base["BodyText"], fontSize=12, leading=18, textColor=colors.HexColor("#21432e"), backColor=colors.HexColor("#edf5e6"), borderPadding=12, spaceBefore=8, spaceAfter=15),
        "unsupported": ParagraphStyle(
            "ReportUnsupported", parent=base["BodyText"], fontSize=10, leading=15, textColor=colors.HexColor("#75601e"), spaceAfter=9
        ),
        "footer": ParagraphStyle("ReportFooter", parent=base["Normal"], fontSize=7.5, textColor=colors.HexColor("#777777")),
        "source": ParagraphStyle("ReportSource", parent=base["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#526459"), spaceAfter=5),
    }


def _footer(canvas, doc, *, confidentiality: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#aac29e"))
    canvas.line(0.75 * inch, 0.69 * inch, LETTER[0] - 0.75 * inch, 0.69 * inch)
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
    story.append(Paragraph("BERRY INTELLIGENCE  /  RESEARCH BRIEF", styles["kicker"]))
    story.append(Paragraph(escape(report.get("title") or "Untitled report"), styles["title"]))
    story.append(Paragraph(f"Exported {date.today().isoformat()}  |  Latest dated source in scope: {_cutoff_date(packet)}", styles["meta"]))
    story.append(Paragraph(f"{escape(confidentiality)}  |  {PROVENANCE_MARKER}", styles["meta"]))
    source_trace = packet.get("source_trace") or (packet.get("strategic_question") or {}).get("source_trace") or []
    reference_names = {row["id"]: f"Source {index + 1}" for index, row in enumerate(source_trace) if row.get("id")}

    def render_section(section: dict[str, Any], *, takeaway: bool = False) -> None:
        story.append(Paragraph(escape(section.get("title") or section.get("section_id") or ""), styles["h2"]))
        edited = section.get("edited_prose") is not None
        status = section.get("status") or ""
        label = "Analyst edited - review before sharing" if edited else {"ai_draft": "AI draft - analyst review required", "structured": "From stored records - classifications retained", "unavailable": "Drafting unavailable", "unsupported": "Insufficient sourced information"}.get(status, "Working draft")
        if status != "structured" or edited:
            story.append(Paragraph(label, styles["meta"]))
        text = section_text(section, packet)
        if not edited and status == "unavailable":
            text = "This section has not been drafted. Add analyst commentary before sharing."
        if not text:
            story.append(Paragraph("No content in this section.", styles["unsupported"]))
            return
        style = styles["unsupported"] if not edited and status in ("unsupported", "unavailable") else styles["takeaway"] if takeaway else styles["body"]
        paragraphs = text.splitlines() if status == "structured" and not edited and section.get("section_id") in {"signals", "assessments", "what_we_know", "implications", "comparison_table"} else text.split("\n\n")
        for paragraph in paragraphs:
            if paragraph.strip():
                story.append(Paragraph(escape(paragraph.strip()).replace("\n", "<br/>"), style))
        citations = [reference_names.get(cid, "Supporting record") for cid in section.get("citation_ids") or []]
        if citations:
            story.append(Paragraph("References: " + ", ".join(dict.fromkeys(citations)), styles["source"]))

    takeaways = [section for section in report.get("sections") or [] if section.get("section_id") in {"executive_summary", "executive_takeaway"}]
    for section in takeaways:
        render_section(section, takeaway=True)

    scope = report.get("scope") or {}
    names = packet.get("display_names") or {}
    scope_lines = [f"Report type: {report.get('report_type', '').replace('_', ' ').title()}"]
    if len(scope.get("berry_ids") or []) > 1:
        scope_lines.append(f"Berries: {', '.join(value.removeprefix('berry-').replace('-', ' ').title() for value in scope['berry_ids'])}")
    if scope.get("berry_id"):
        scope_lines.append(f"Berry: {scope['berry_id'].removeprefix('berry-').replace('-', ' ').title()}")
    if scope.get("geography_ids"):
        scope_lines.append(f"Countries and regions: {', '.join(names.get(id, id.removeprefix('geography-').replace('-', ' ').title()) for id in scope['geography_ids'])}")
    if scope.get("country_codes"):
        scope_lines.append(f"Countries without canonical geography records (ISO): {', '.join(scope['country_codes'])}")
    if scope.get("company_ids"):
        company_names = {r["id"]: r.get("name") or r["id"] for r in packet.get("companies") or [] if r.get("id")}
        scope_lines.append(f"Companies: {', '.join(company_names.get(cid, cid) for cid in scope['company_ids'])}")
    if packet.get("source_window"):
        scope_lines.append(f"Publication window: {packet['source_window']['start']} through {packet['source_window']['end']}")
    if scope.get("variety_ids"):
        varieties = {r['id']: r.get('name') or r['id'] for r in packet.get('varieties') or [] if r.get('id')}
        scope_lines.append(f"Varieties: {', '.join(names.get(id) or varieties.get(id) or id.removeprefix('variety-').replace('-', ' ').title() for id in scope['variety_ids'])}")
    story.append(Paragraph("What this report covers", styles["h2"]))
    for line in scope_lines:
        story.append(Paragraph(escape(line), styles["meta"]))

    coverage_story: list[Any] = []
    counts = coverage.get("counts") or {}
    if counts:
        coverage_story.append(Paragraph("Coverage notes", styles["h2"]))
        coverage_story.append(Paragraph("Record counts describe captured material, not market size or complete coverage.", styles["meta"]))
        rows = [[key.removesuffix("_count").replace("_", " ").title(), str(value)] for key, value in counts.items()]
        table = Table([["Category", "Count"], *rows], colWidths=[3.2 * inch, 1.2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5efdc")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#294b35")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f9ef"), colors.white]),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        coverage_story.append(table)
        coverage_story.append(Spacer(1, 6))

    gaps = coverage.get("gaps") or []
    if gaps:
        coverage_story.append(Paragraph("Known Gaps", styles["h2"]))
        for gap in gaps:
            coverage_story.append(Paragraph(escape(str(gap)), styles["body"]))

    for section in report.get("sections") or []:
        if section in takeaways:
            continue
        if section.get("section_id") in {"sources", "evidence_appendix"} and section.get("edited_prose") is None and source_trace:
            continue  # One readable appendix replaces duplicate generated source dumps.
        if section.get("section_id") in {"scope_method", "comparison_scope"} and section.get("edited_prose") is None:
            continue  # The named scope is already presented beneath the takeaway.
        render_section(section)

    if packet.get("source_window"):
        window = packet["source_window"]
        story.append(Paragraph("Captured company reporting", styles["h2"]))
        story.append(Paragraph(f"Published {window['start']} through {window['end']}. Pending sources are excluded from trusted synthesis.", styles["meta"]))
        for row in packet.get("source_inventory") or []:
            story.append(Paragraph(escape(row["title"]), styles["h2"]))
            story.append(Paragraph(escape(f"{row['published_date']} | {row['source_name']} | {row['trust_label']}"), styles["meta"]))
            text = row.get("excerpt") or row.get("summary") or ""
            if text:
                label = "Source excerpt: " if row.get("excerpt") else "Stored source summary: "
                story.append(Paragraph(escape(label + text), styles["body"]))
            if row.get("notice"):
                story.append(Paragraph(escape(row["notice"]), styles["unsupported"]))
            story.append(Paragraph(escape(row.get("source_url") or "Original source URL not recorded"), styles["source"]))
        if not packet.get("source_inventory"):
            story.append(Paragraph("No captured articles with confirmed publication dates in this window.", styles["unsupported"]))
        undated = packet.get("undated_source_inventory") or []
        if undated:
            story.append(Paragraph(f"{len(undated)} additional sources need date verification and are excluded from current coverage.", styles["meta"]))

    story.extend(coverage_story)
    if source_trace:
        story.append(Paragraph("Source appendix", styles["h2"]))
        for index, row in enumerate(source_trace):
            label = row.get("title") or "Source title not recorded"
            date_text = row.get("date") or row.get("published_date") or ""
            source_name = row.get("source_name") or ""
            entry = [Paragraph(f"<b>{index + 1}. {escape(label)}</b>", styles["body"]),
                     Paragraph(escape(f"{source_name} | {date_text or 'Date not recorded'}"), styles["source"])]
            url = str(row.get("source_url") or "")
            if url.startswith(("https://", "http://")):
                safe_url = escape(url, {'"': '&quot;'})
                entry.append(Paragraph(f'<link href="{safe_url}" color="#286643">Open original source</link>', styles["source"]))
            else:
                entry.append(Paragraph("Original URL not recorded; consult the linked record in the app.", styles["source"]))
            story.append(KeepTogether(entry))

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
