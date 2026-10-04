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
from app.services.report_builder.presentation import section_text, section_title, report_sources
from app.services.map_regions import public_source_url

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
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], alignment=0, fontName="Helvetica-Bold", fontSize=29, leading=33, textColor=colors.HexColor("#183e2b"), spaceAfter=12),
        "meta": ParagraphStyle("ReportMeta", parent=base["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#526459"), spaceAfter=5),
        "kicker": ParagraphStyle("ReportKicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.HexColor("#347147"), spaceAfter=13),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], fontSize=16, leading=20, textColor=colors.HexColor("#214c35"), spaceBefore=19, spaceAfter=9, keepWithNext=True),
        "section_meta": ParagraphStyle("ReportSectionMeta", parent=base["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#526459"), spaceAfter=5, keepWithNext=True),
        "item": ParagraphStyle("ReportItem", parent=base["BodyText"], fontSize=10.5, leading=15.5, textColor=colors.HexColor("#273c30"), spaceAfter=0),
        "number": ParagraphStyle("FindingNumber", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=colors.HexColor("#367247")),
        "h3": ParagraphStyle("ReportH3", parent=base["Heading3"], fontSize=12, leading=16, textColor=colors.HexColor("#41624b"), spaceBefore=13, spaceAfter=7, keepWithNext=True),
        "source_title": ParagraphStyle("SourceTitle", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=colors.HexColor("#214c35"), spaceAfter=5),
        "market_group": ParagraphStyle("MarketGroup", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#214c35"), spaceBefore=10, spaceAfter=7),
        "location_value": ParagraphStyle("LocationValue", parent=base["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#273c30"), spaceAfter=0),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=10, leading=15, textColor=colors.HexColor("#273c30"), spaceAfter=9),
        "takeaway": ParagraphStyle("ReportTakeaway", parent=base["BodyText"], fontSize=13, leading=19, textColor=colors.HexColor("#173c26"), spaceAfter=0),
        "unsupported": ParagraphStyle(
            "ReportUnsupported", parent=base["BodyText"], fontSize=10, leading=15, textColor=colors.HexColor("#75601e"), spaceAfter=9
        ),
        "footer": ParagraphStyle("ReportFooter", parent=base["Normal"], fontSize=7.5, textColor=colors.HexColor("#777777")),
        "source": ParagraphStyle("ReportSource", parent=base["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#526459"), spaceAfter=5),
    }


def _footer(canvas, doc, *, confidentiality: str) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#388144"))
    canvas.rect(0.75 * inch, LETTER[1] - .55 * inch, 42, 4, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#dce8d5"))
    canvas.rect(0.75 * inch + 42, LETTER[1] - .55 * inch, LETTER[0] - 1.5 * inch - 42, 4, fill=1, stroke=0)
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
    for row in report_sources(packet):
        if row.get("published_date"):
            dates.append(str(row["published_date"]))
    return max(dates) if dates else "Unknown (no dated Evidence in packet)"


def _readable_date(value: Any) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%b %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return "Date not recorded"


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
    story.append(Paragraph("BERRY INTELLIGENCE  /  " + ("MARKET SNAPSHOT" if report.get("report_type") == "market_snapshot" else "RESEARCH BRIEF"), styles["kicker"]))
    story.append(Paragraph(escape(report.get("title") or "Untitled report"), styles["title"]))
    story.append(Paragraph(f"Exported {_readable_date(date.today())}  |  Latest dated source in scope: {_readable_date(_cutoff_date(packet))}", styles["meta"]))
    story.append(Paragraph(f"{escape(confidentiality)}  |  {PROVENANCE_MARKER}", styles["meta"]))
    source_trace = report_sources(packet)
    reference_names = {row["id"]: f"Source {index + 1}" for index, row in enumerate(source_trace) if row.get("id")}
    pending_sections = [section for section in report.get("sections") or [] if section.get("edited_prose") is None and section.get("status") in {"unavailable", "unsupported"}]
    if pending_sections:
        story.append(Paragraph(f"Incomplete working report: {len(pending_sections)} sections still to prepare.", styles["unsupported"]))

    def render_section(section: dict[str, Any], *, takeaway: bool = False) -> None:
        if section in pending_sections:
            return  # Retain these together in the preparation checklist below.
        story.append(Paragraph(escape(section_title(section)), styles["h2"]))
        edited = section.get("edited_prose") is not None
        status = section.get("status") or ""
        label = "Analyst edited - review before sharing" if edited else {"ai_draft": "AI draft - review required", "structured": "From saved records", "unavailable": "Not drafted yet", "unsupported": "Needs more sources"}.get(status, "Working draft")
        if status != "structured" or edited:
            story.append(Paragraph(label, styles["section_meta"]))
        if not edited and section.get("section_id") == "locations" and section.get("location_rows"):
            story.append(Paragraph("Recorded entries, not acreage or precise farm boundaries. User annotations remain unreviewed; source links do not confirm growing or operations.", styles["body"]))
            for row in section["location_rows"]:
                block = []
                heading = Paragraph(escape(row["name"] + " / " + row["kind"].title()), styles["h3"])
                place = row["country"] + (" / " + row["locality"] if row.get("locality") else "")
                values = [("Place / activity", place + "\n" + row["activity"]),
                          ("Status / observed", row["status"].title() + "\nObserved / effective: " + (row.get("observed_on") or "Unknown")),
                          ("Basis / source date", row["basis"] + "\nSource published: " + (row.get("source_date") or "Unknown"))]
                cells = [[Paragraph(escape(label), styles["source"]), Paragraph(escape(value).replace("\n", "<br/>"), styles["location_value"])] for label, value in values]
                table = Table(cells, colWidths=[doc.width * .28, doc.width * .72], splitInRow=1)
                table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf5e6")),
                    ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#ceddc7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
                block.extend([heading, table, Spacer(1, 6)])
                if row.get("scope_note"):
                    block.append(Paragraph(escape(row["scope_note"]), styles["unsupported"]))
                if row.get("notes"):
                    block.append(Paragraph("Saved notes and limitations", styles["source_title"]))
                    block.append(Paragraph(escape(row["notes"]).replace("\n", "<br/>"), styles["body"]))
                url = public_source_url(row.get("source_url"))
                block.append(Paragraph('<a href="' + escape(url, {'"': '&quot;'}) + '">Supporting source: ' + escape(url) + '</a>' if url else "No supporting source link recorded.", styles["source"]))
                story.append(KeepTogether(block))
            return
        if not edited and section.get("section_id") == "statistics" and section.get("statistics_groups"):
            story.append(Paragraph("Public reference figures; separate from reviewed statements. Countries, categories and source units are not added together.", styles["body"]))
            for group in section["statistics_groups"]:
                heading = Paragraph(escape(f"{group['country']} / {group['commodity']} / {group['period']}"), styles["market_group"])
                cells = [[Paragraph(escape(str(v)), styles["source"]) for v in ("Measure", "Value", "Unit / status")]]
                cells += [[Paragraph(escape(str(v)), styles["body"]) for v in
                           (m["label"], f"{m['value']:,}", m["unit"] + (" / " + m["status_label"] if m.get("source_flag") else ""))] for m in group["metrics"]]
                table = Table(cells, colWidths=[doc.width * .38, doc.width * .20, doc.width * .42], repeatRows=1)
                table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf5e6")),
                                          ("LINEBELOW", (0, 0), (-1, 0), .7, colors.HexColor("#90aa8f")), ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#d8e4d3")),
                                          ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
                story.append(KeepTogether([heading, table]))
                story.append(Paragraph(escape(group["basis"]), styles["source"]))
                if all("source_flag" in m and not m["source_flag"] for m in group["metrics"]):
                    story.append(Paragraph("No estimate/provisional flags supplied; figures remain subject to source revisions.", styles["source"]))
                timing = "Source updated " + group["source_updated_at"][:10] if group.get("source_updated_at") else "Published " + group["published_date"]
                story.append(Paragraph(escape(f"{group['source']} / {group['locator']} / {timing} / checked {group['accessed_date']} / " + reference_names.get(group["id"], "Supporting source")), styles["source"]))
            return
        text = section_text(section, packet)
        if not edited and status == "unavailable":
            text = "This section has not been drafted. Add analyst commentary before sharing."
        if not text:
            story.append(Paragraph("No content in this section.", styles["unsupported"]))
            return
        style = styles["unsupported"] if not edited and status in ("unsupported", "unavailable") else styles["takeaway"] if takeaway else styles["body"]
        line_items = section.get("section_id") in {"signals", "assessments", "what_we_know", "implications", "comparison_table", "sources", "evidence_appendix"}
        paragraphs = text.splitlines() if line_items else text.split("\n\n")
        item_number = 0
        for paragraph in paragraphs:
            if paragraph.strip():
                if line_items:
                    item_style = styles["source"] if section.get("section_id") in {"sources", "evidence_appendix"} else styles["item"]
                    content = Paragraph(escape(paragraph.strip()), item_style)
                    if item_style is styles["item"]:
                        item_number += 1
                        card = Table([[Paragraph(f"{item_number:02d}", styles["number"]), content]], colWidths=[36, doc.width - 36], splitInRow=1)
                        card.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e7f1df")),
                            ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f6f9f3")),
                            ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#ceddc7")),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
                        story.extend([card, Spacer(1, 6)])
                    else:
                        story.append(content)
                else:
                    content = Paragraph(escape(paragraph.strip()).replace("\n", "<br/>"), style)
                    if takeaway:
                        card = Table([[content]], colWidths=[doc.width], splitInRow=1)
                        card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e7f1df")),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#388144")),
                            ("LEFTPADDING", (0, 0), (-1, -1), 13), ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                            ("TOPPADDING", (0, 0), (-1, -1), 13), ("BOTTOMPADDING", (0, 0), (-1, -1), 13)]))
                        story.extend([card, Spacer(1, 9)])
                    else:
                        story.append(content)
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
    story.append(Paragraph("What this report covers", styles["h3"]))
    scope_cells = [Paragraph(escape(line), styles["meta"]) for line in scope_lines]
    if len(scope_cells) % 2:
        scope_cells.append("")
    scope_table = Table([scope_cells[index:index + 2] for index in range(0, len(scope_cells), 2)], colWidths=[doc.width * .5] * 2, splitInRow=1)
    scope_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6ef")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(scope_table)

    coverage_story: list[Any] = []
    counts = coverage.get("counts") or {}
    if counts:
        coverage_story.append(Paragraph("Coverage notes", styles["h2"]))
        coverage_story.append(Paragraph("Record counts describe captured material, not market size or complete coverage.", styles["meta"]))
        rows = [[key.removesuffix("_count").replace("_", " ").title(), str(value)] for key, value in counts.items()]
        table = Table([["Category", "Count"], *rows], colWidths=[3.2 * inch, 1.2 * inch], repeatRows=1)
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

    if counts and len(counts) <= 12 and not gaps:
        story.append(KeepTogether(coverage_story))
    else:
        story.extend(coverage_story)
    if pending_sections:
        story.append(Paragraph("Still to prepare", styles["h2"]))
        story.append(Paragraph("These sections are retained in your working report. Add commentary or supporting material before sharing.", styles["meta"]))
        rows = [[Paragraph("<b>Section</b>", styles["source"]), Paragraph("<b>What is needed</b>", styles["source"])]]
        for section in pending_sections:
            need = "Not drafted" if section.get("status") == "unavailable" else section_text(section, packet) or "More sourced information"
            rows.append([Paragraph(escape(section.get("title") or "Untitled section"), styles["body"]), Paragraph(escape(need), styles["source"])])
        table = Table(rows, colWidths=[doc.width * .54, doc.width * .46], repeatRows=1, splitInRow=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3ecd9")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#faf8ef"), colors.white]), ("LINEBELOW", (0, 0), (-1, -1), .4, colors.HexColor("#d6d4c1")), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(table)
    if source_trace:
        for index, row in enumerate(source_trace):
            label = row.get("title") or "Source title not recorded"
            date_text = _readable_date(row.get("date") or row.get("published_date"))
            source_name = row.get("source_name") or ""
            entry = [Paragraph(f"{index + 1:02d} / {escape(label)}", styles["source_title"]),
                     Paragraph(escape(f"{source_name} | {row.get('date_label') or date_text or 'Date not recorded'}"), styles["source"])]
            if index == 0:
                entry.insert(0, Paragraph("Source appendix", styles["h2"]))
            url = public_source_url(row.get("source_url"))
            if url:
                safe_url = escape(url, {'"': '&quot;'})
                entry.append(Paragraph(f'<link href="{safe_url}" color="#286643">Open original source</link>', styles["source"]))
            else:
                entry.append(Paragraph("Original URL not recorded; consult the linked record in the app.", styles["source"]))
            story.append(KeepTogether(entry))

    included = [row for row in (report.get("external_research_appendix") or []) if row.get("included_in_report")]
    if included:
        story.append(Paragraph("External public research", styles["h2"]))
        story.append(
            Paragraph(
                "An analyst selected these findings as external context. Their review status is shown "
                "below. They remain separate from reviewed evidence and do not confirm this report's conclusions.",
                styles["unsupported"],
            )
        )
        for row in included:
            story.append(Paragraph(escape(str(row.get("title") or "External research finding")), styles["body"]))
            story.append(Paragraph("Analyst marked reviewed - external context only" if row.get("reviewed") else "Unreviewed external finding", styles["source"]))
            if row.get("gap_label"):
                story.append(Paragraph("Research topic: " + escape(str(row["gap_label"])), styles["source"]))
            metadata = []
            if row.get("retrieved_at"):
                metadata.append("Retrieved " + _readable_date(row["retrieved_at"]))
            if row.get("provider"):
                metadata.append("Research provider: " + str(row["provider"]))
            if metadata:
                story.append(Paragraph(escape(" | ".join(metadata)), styles["source"]))
            url = public_source_url(row.get("url"))
            if url:
                safe_url = escape(url, {'"': '&quot;'})
                story.append(Paragraph(f'<link href="{safe_url}" color="#286643">Open original source</link>', styles["source"]))
            else:
                story.append(Paragraph("Original URL unavailable", styles["source"]))

    doc.build(story)
    return buffer.getvalue()
