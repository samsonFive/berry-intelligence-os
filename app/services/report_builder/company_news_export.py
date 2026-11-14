"""Saved Company news review views and portable, provider-free exports.

These functions read one retained review snapshot. They never retrieve sources,
refresh a company, or write canonical intelligence. Analyst entry edits are
resolved by the research service's shared ``effective_entry`` function.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from hashlib import sha256
from io import BytesIO
import math
import re
from typing import Any
from xml.sax.saxutils import escape
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.services.map_regions import public_source_url


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
MAX_EXPORT_COMPANIES = 100
MAX_XLSX_ENTRIES = 5000
MAX_XLSX_SOURCES = 10000
MAX_PDF_INCLUDED_ENTRIES = 1000
MAX_PDF_SOURCES = 5000
_LABELS = {
    "pending": "Not researched yet",
    "has_findings": "Findings captured",
    "no_qualifying_findings": "No qualifying findings captured",
    "leads_only": "Reporting leads only",
    "identity_unresolved": "Identity unresolved",
    "identity_ambiguous": "Identity needs clarification",
    "incomplete": "Research incomplete",
    "blocked": "Research blocked",
    "complete": "Complete",
    "partial": "Partial",
    "failed": "Failed",
    "not_requested": "Not requested",
    "resolved": "Resolved",
    "unresolved": "Unresolved",
    "ambiguous": "Ambiguous",
    "unreviewed": "Unreviewed",
    "reviewed": "Analyst reviewed",
    "archive": "Platform archive",
    "web": "Public web",
    "body_supported": "Source text captured",
    "metadata_only": "Metadata only",
    "dated_finding": "Dated finding",
    "undated": "Publication date unavailable",
    "background": "Background context",
    "scope_unverified": "Scope unverified",
    "date_outside_window": "Outside publication window",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(_text(item) for item in value if item is not None)
    return str(value)


def _label(value: Any) -> str:
    text = _text(value)
    return _LABELS.get(text, text.replace("_", " ").capitalize())


def _date(value: Any) -> date | None:
    text = _text(value)
    if not _ISO_DATE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _url(value: Any) -> str:
    text = _text(value).strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return ""
    return public_source_url(text)


def _rows(snapshot: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        raise ValueError("Saved review must be a record")
    rows = snapshot.get(key, [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Saved review {key} must be a list of records")
    return rows


def _indexed(rows: list[dict[str, Any]], key: str, kind: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = _text(row.get(key))
        if not identity or identity in indexed:
            raise ValueError(f"Saved review has a missing or duplicate {kind} ID")
        indexed[identity] = row
    return indexed


def company_news_view(snapshot: dict[str, Any], *, title: str = "Company news review") -> dict[str, Any]:
    """Resolve one saved ledger for HTML, narrative, PDF and workbook consumers.

    All requested companies and all entry decisions remain in ``entries``.
    ``included_entries`` is the sole narrative selection. A missing source
    reference is visible rather than relinked to an unrelated source.
    """
    from app.services.report_builder.company_news import effective_entry

    if not isinstance(snapshot, dict):
        raise ValueError("Saved review must be a record")
    review = deepcopy(snapshot)
    start, end, as_of = (_date(review.get(key)) for key in ("from_date", "through_date", "as_of"))
    if review.get("schema_version") != 1 or not start or not end or not as_of or start > end:
        raise ValueError("Saved review has an unsupported version or invalid date window")
    companies = _rows(review, "companies")
    sources = _rows(review, "sources")
    company_lookup = _indexed(companies, "key", "company")
    source_lookup = _indexed(sources, "id", "source")
    _indexed(_rows(review, "entries"), "id", "entry")

    for index, source in enumerate(sources, 1):
        source["reference"] = f"S{index:02d}"
        source["url"] = _url(source.get("url"))
        source["published_date"] = _text(source.get("published_date"))
        source["title"] = _text(source.get("title")) or "Untitled source"

    entries = []
    for raw in _rows(review, "entries"):
        entry = effective_entry(raw)
        company_key = _text(entry.get("company_key"))
        if company_key not in company_lookup:
            raise ValueError("Saved entry refers to a company outside the requested roster")
        ids = entry.get("source_ids") or []
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise ValueError("Saved entry source references must be IDs")
        entry["source_ids"] = list(dict.fromkeys(ids))
        entry["sources"] = [source_lookup[value] for value in entry["source_ids"] if value in source_lookup]
        entry["missing_source_ids"] = [value for value in entry["source_ids"] if value not in source_lookup]
        entry["included"] = entry.get("included") is True
        entry["entry_type"] = _text(entry.get("entry_type")) or "development"
        entry["headline"] = _text(entry.get("headline")) or "Untitled finding"
        entry["published_date"] = _text(entry.get("published_date"))
        entry["event_date"] = _text(entry.get("event_date"))
        published = _date(entry["published_date"])
        start, end = _date(review.get("from_date")), _date(review.get("through_date"))
        entry["outside_window"] = bool(published and ((start and published < start) or (end and published > end)))
        company = company_lookup[company_key]
        entry["company_name"] = _text(company.get("canonical_name") or company.get("requested_name") or company_key)
        entries.append(entry)

    grouped_entries: dict[str, list[dict[str, Any]]] = {key: [] for key in company_lookup}
    grouped_sources: dict[str, set[str]] = {key: set() for key in company_lookup}
    for source in sources:
        for key in source.get("company_keys") or []:
            if key in grouped_sources:
                grouped_sources[key].add(source["id"])
    for entry in entries:
        grouped_entries[entry["company_key"]].append(entry)
        grouped_sources[entry["company_key"]].update(value for value in entry["source_ids"] if value in source_lookup)

    for company in companies:
        key = _text(company["key"])
        company["name"] = _text(company.get("canonical_name") or company.get("requested_name") or key)
        company["outcome"] = _label(company.get("disposition") or "pending")
        company["entries"] = grouped_entries[key]
        company["included_entries"] = [entry for entry in company["entries"] if entry["included"]]
        company["included_count"] = len(company["included_entries"])
        company["excluded_count"] = len(company["entries"]) - company["included_count"]
        company["source_count"] = len(grouped_sources[key])

    included = [entry for entry in entries if entry["included"]]
    # Chronological highlights make a visible, reproducible selection; they are
    # not an invented importance ranking or a cap on the full report below.
    latest = sorted((entry for entry in included if _date(entry.get("published_date"))),
                    key=lambda row: row["published_date"], reverse=True)[:3]
    return {
        **review,
        "title": _text(title).strip() or "Company news review",
        "companies": companies,
        "sources": sources,
        "entries": entries,
        "included_entries": included,
        "latest_findings": latest,
        "company_lookup": company_lookup,
        "source_lookup": source_lookup,
        "counts": {"companies": len(companies), "entries": len(entries), "included": len(included),
                   "excluded": len(entries) - len(included), "sources": len(sources),
                   "included_leads": sum(entry["entry_type"] == "lead" for entry in included)},
    }


def _excel_text(value: Any) -> str:
    text = _text(value)
    if _BAD_XML.search(text):
        raise ValueError("A saved field contains characters Excel cannot preserve")
    if len(text) > 32767:
        raise ValueError("A saved field exceeds Excel's cell limit")
    return text


def _require_included_sources(view: dict[str, Any]) -> None:
    if any(entry["missing_source_ids"] or not entry["sources"] for entry in view["included_entries"]):
        raise ValueError("An included item has missing source references; repair its saved source links or exclude it before exporting")


def render_company_news_xlsx(snapshot: dict[str, Any], *, title: str = "Company news review") -> bytes:
    """Export the saved review, including excluded candidates and search outcomes.

    openpyxl is an existing pinned web-runtime dependency. Text is explicitly
    stored as text, including values beginning with spreadsheet formula prefixes.
    Source citations live once in Scope, one clickable public URL per source.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.hyperlink import Hyperlink

    if (len(_rows(snapshot, "companies")) > MAX_EXPORT_COMPANIES
            or len(_rows(snapshot, "entries")) > MAX_XLSX_ENTRIES
            or len(_rows(snapshot, "sources")) > MAX_XLSX_SOURCES):
        raise ValueError("This saved review exceeds the workbook export limit; split the company roster into smaller reviews")
    view = company_news_view(snapshot, title=title)
    _require_included_sources(view)
    workbook = Workbook()
    workbook.remove(workbook.active)
    stamp = str(snapshot.get("created_at") or snapshot.get("as_of") or "1980-01-01")
    try:
        created = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if created.tzinfo is not None:
            created = created.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        created = datetime(1980, 1, 1)
    workbook.properties.creator = "Berry Intelligence OS"
    workbook.properties.title = _excel_text(view["title"])
    workbook.properties.created = workbook.properties.modified = created

    border = Border(*(Side(style="thin", color="D7E2D2") for _ in range(4)))
    dark = "214C35"
    fill_header = PatternFill("solid", fgColor=dark)
    fill_identity = PatternFill("solid", fgColor="EDF5E6")
    fill_alternate = PatternFill("solid", fgColor="F7FAF4")
    white = PatternFill("solid", fgColor="FFFFFF")

    def cell(sheet, row, column, value, *, date_value=False, header=False, identity=False, link="", location=""):
        target = sheet.cell(row, column)
        parsed = _date(value) if date_value else None
        if parsed is not None and parsed.year >= 1900:
            target.value = parsed
            target.number_format = "yyyy-mm-dd"
        elif isinstance(value, (bool, int, float)):
            target.value = value
        else:
            target.value = _excel_text(value)
            target.data_type = "s"
        target.alignment = Alignment(vertical="top", wrap_text=True)
        target.border = border
        target.font = Font(name="Aptos", size=11, color="FFFFFF" if header else "23392D", bold=header)
        target.fill = fill_header if header else fill_identity if identity else fill_alternate if row % 2 == 0 else white
        if link or location:
            target.hyperlink = Hyperlink(ref=target.coordinate, target=link or None, location=location or None)
            target.font = Font(name="Aptos", size=11, color="176691", underline="single", bold=header)
        return target

    def heading(sheet, label, subtitle, columns):
        sheet.sheet_view.showGridLines = False
        sheet.sheet_properties.pageSetUpPr.fitToPage = False
        sheet.page_setup.orientation = "landscape"
        sheet.print_options.horizontalCentered = False
        sheet.oddFooter.center.text = "Working report; source review remains separate | Page &P"
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=columns)
        top = sheet.cell(1, 1, _excel_text(label))
        top.data_type = "s"
        top.font = Font(name="Aptos Display", size=23, bold=True, color=dark)
        top.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.row_dimensions[1].height = 36
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=columns)
        sub = sheet.cell(2, 1, _excel_text(subtitle))
        sub.data_type = "s"
        sub.font = Font(name="Aptos", size=11, color="526459")
        sub.alignment = Alignment(vertical="top", wrap_text=True)
        sheet.row_dimensions[2].height = 34
        sheet.sheet_properties.outlinePr.summaryRight = False

    def header(sheet, values, widths, row=5):
        for index, (label, width) in enumerate(zip(values, widths), 1):
            cell(sheet, row, index, label, header=True)
            sheet.column_dimensions[sheet.cell(row, index).column_letter].width = width
        sheet.row_dimensions[row].height = 32

    def row_height(sheet, row, values, widths):
        lines = max((sum(max(1, math.ceil(len(line) / max(1, int(width)))) for line in _text(value).split("\n"))
                     for value, width in zip(values, widths)), default=1)
        sheet.row_dimensions[row].height = min(409, max(32, lines * 15 + 12))

    window = f"Publication window: {view.get('from_date', '')} through {view.get('through_date', '')} (inclusive)"
    counts = view["counts"]
    summary = f"{window} | As of {view.get('as_of', '')} | {counts['included']} included items; {counts['excluded']} excluded candidates"
    companies = workbook.create_sheet("Companies")
    company_headers = ["Company", "Requested name", "Company ID", "Identity", "Research outcome", "Archive search", "Web search", "Included items", "Excluded candidates", "Captured sources", "Notes"]
    company_widths = [30, 30, 29, 20, 34, 22, 22, 17, 19, 18, 80]
    heading(companies, view["title"], summary, len(company_headers))
    header(companies, company_headers, company_widths)
    companies.freeze_panes = "C6"
    for row, company in enumerate(view["companies"], 6):
        values = [company["name"], company.get("requested_name"), company.get("company_id"), _label(company.get("resolution")),
                  company["outcome"], _label(company.get("archive_status")), _label(company.get("web_status")),
                  company["included_count"], company["excluded_count"], company["source_count"], company.get("notes")]
        for column, value in enumerate(values, 1):
            cell(companies, row, column, value, identity=column <= 2)
        row_height(companies, row, values, company_widths)
    companies.auto_filter.ref = f"A5:K{max(5, companies.max_row)}"
    companies.print_title_rows = "1:5"

    developments = workbook.create_sheet("Developments")
    entry_headers = ["Entry ID", "Company", "Published date", "Event timing", "Headline", "Summary", "News angle", "Qualification", "Source IDs", "Included", "Entry type", "Analyst review", "Analyst edited", "Date window", "Missing source IDs"]
    entry_widths = [30, 30, 18, 30, 64, 88, 72, 76, 32, 15, 20, 22, 18, 26, 30]
    heading(developments, "Developments and reporting leads", summary, len(entry_headers))
    developments.merge_cells("A3:O3")
    developments["A3"] = "Included items feed the narrative and PDF. Excluded candidates remain here for review. Source IDs link to the reference table in Scope."
    developments["A3"].font = Font(name="Aptos", size=10, color="526459")
    header(developments, entry_headers, entry_widths)
    developments.freeze_panes = "D6"
    source_rows = {source["id"]: row for row, source in enumerate(view["sources"], 8)}
    for row, entry in enumerate(view["entries"], 6):
        references = [view["source_lookup"][value]["reference"] + " · " + value
                      if value in view["source_lookup"] else value for value in entry["source_ids"]]
        values = [entry["id"], entry["company_name"], entry.get("published_date"), entry.get("event_date"), entry["headline"],
                  entry.get("summary"), entry.get("news_angle"), entry.get("qualification"), "\n".join(references),
                  "Yes" if entry["included"] else "No", "Reporting lead" if entry["entry_type"] == "lead" else "Development",
                  _label(entry.get("review_status") or "unreviewed"), "Yes" if entry.get("analyst_edited") else "No",
                  "Outside requested window" if entry["outside_window"] else "Date not recorded" if not _date(entry.get("published_date")) else "Within requested window",
                  "\n".join(entry["missing_source_ids"])]
        source_row = next((source_rows[value] for value in entry["source_ids"] if value in source_rows), None)
        for column, value in enumerate(values, 1):
            cell(developments, row, column, value, date_value=column in {3, 4}, identity=column <= 2,
                 location=f"'Scope'!A{source_row}" if column == 9 and source_row else "")
        row_height(developments, row, values, entry_widths)
    developments.auto_filter.ref = f"A5:O{max(5, developments.max_row)}"
    developments.print_title_rows = "1:5"

    scope = workbook.create_sheet("Scope")
    heading(scope, "Scope and source references", window, 13)
    scope.merge_cells("A3:D3")
    scope["A3"] = _excel_text(f"As of: {view.get('as_of', '')} | Research state: {_label(view.get('status'))}")
    scope.merge_cells("E3:H3")
    scope["E3"] = _excel_text(f"Berry: {_text(view.get('berry_id')).removeprefix('berry-') or 'All berries'} | Source mode: {view.get('source_scope', '')}")
    scope.merge_cells("I3:M3")
    scope["I3"] = _excel_text("Topic: " + (_text(view.get("topic")) or "Company news"))
    scope.merge_cells("A4:M4")
    scope["A4"] = _excel_text(f"Saved: {view.get('created_at', '')} | {counts['companies']} requested organizations | {counts['included']} included / {counts['excluded']} excluded items | {counts['sources']} retained source records")
    scope.merge_cells("A5:M5")
    scope["A5"] = "Publication dates define the inclusive window; event timing and capture dates are separate. Search completion does not establish exhaustive coverage. Metadata-only, blocked and undated sources retain their qualifications. Analyst review of a report does not approve canonical Evidence."
    for coordinate in ("A3", "E3", "I3", "A4", "A5"):
        scope[coordinate].font = Font(name="Aptos", size=11, color="526459")
        scope[coordinate].alignment = Alignment(vertical="top", wrap_text=True)
    scope.row_dimensions[3].height = 32
    scope.row_dimensions[4].height = 30
    scope.row_dimensions[5].height = 44
    source_headers = ["Reference / source ID", "Title", "Published date", "Date basis", "Source origin", "Trust class", "Capture status", "Eligibility", "Qualification", "Public URL", "Passage locator", "Source version / hash", "Evidence ID"]
    source_widths = [34, 65, 18, 26, 22, 28, 25, 27, 76, 82, 35, 70, 32]
    header(scope, source_headers, source_widths, row=7)
    scope.freeze_panes = "B8"
    for row, source in enumerate(view["sources"], 8):
        values = [source["reference"] + " · " + _text(source.get("id")), source["title"], source.get("published_date"),
                  source.get("publication_date_basis"), _label(source.get("origin")), source.get("trust_class"), _label(source.get("capture_status")),
                  _label(source.get("eligibility")), source.get("qualification"), source["url"], source.get("passage_locator"),
                  source.get("source_version"), source.get("evidence_id")]
        for column, value in enumerate(values, 1):
            cell(scope, row, column, value, date_value=column == 3, identity=column == 1, link=source["url"] if column == 10 else "")
        row_height(scope, row, values, source_widths)
    scope.auto_filter.ref = f"A7:M{max(7, scope.max_row)}"
    scope.print_title_rows = "1:7"

    raw = BytesIO()
    workbook.save(raw)
    # Strip time-varying ZIP container metadata. The same saved snapshot then
    # yields the same download bytes, without modifying any underlying record.
    result = BytesIO()
    with ZipFile(BytesIO(raw.getvalue())) as original, ZipFile(result, "w", ZIP_DEFLATED, compresslevel=6) as output:
        for name in sorted(original.namelist()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            body = original.read(name)
            if name == "docProps/core.xml":
                # The pinned writer stamps modified at save time. Preserve the
                # saved review timestamp instead of refreshing this metadata.
                for prefix, namespace in (("cp", "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"),
                                          ("dc", "http://purl.org/dc/elements/1.1/"), ("dcterms", "http://purl.org/dc/terms/"),
                                          ("xsi", "http://www.w3.org/2001/XMLSchema-instance")):
                    ElementTree.register_namespace(prefix, namespace)
                core = ElementTree.fromstring(body)
                modified = core.find("{http://purl.org/dc/terms/}modified")
                if modified is not None:
                    modified.text = created.isoformat(timespec="seconds") + "Z"
                body = ElementTree.tostring(core, encoding="utf-8")
            output.writestr(info, body)
    return result.getvalue()


def render_company_news_pdf(
    snapshot: dict[str, Any], *, title: str = "Company news review", confidentiality: str = "Internal / Confidential"
) -> bytes:
    """Render an editorial report with navigable companies and cited findings.

    Only included entries enter the narrative. Every requested company remains
    in the directory and body, including unresolved and quiet companies.
    """
    from pathlib import Path
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, HRFlowable, PageTemplate, Paragraph, Spacer, Table, TableStyle

    if (len(_rows(snapshot, "companies")) > MAX_EXPORT_COMPANIES
            or sum(entry.get("included") is True for entry in _rows(snapshot, "entries")) > MAX_PDF_INCLUDED_ENTRIES):
        raise ValueError("This saved review exceeds the PDF export limit; narrow the included selection or split the company roster")
    view = company_news_view(snapshot, title=title)
    _require_included_sources(view)
    cited_ids = {identity for entry in view["included_entries"] for identity in entry["source_ids"]}
    pdf_sources = [source for source in view["sources"] if source["id"] in cited_ids]
    if len(pdf_sources) > MAX_PDF_SOURCES:
        raise ValueError("This saved review exceeds the PDF source-reference limit; narrow the included selection or export Excel")
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("NewsSans", "Vera.ttf"), ("NewsSansBold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    if "STSong-Light" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFontFamily("NewsSans", normal="NewsSans", bold="NewsSansBold", italic="NewsSans", boldItalic="NewsSansBold")

    def text(value):
        safe = escape(_text(value), {'"': "&quot;"})
        safe = re.sub(r"[\u2e80-\u9fff\uf900-\ufaff]+", lambda match: '<font face="STSong-Light">' + match[0] + "</font>", safe)
        return safe.replace("\n", "<br/>")

    dark, green, muted = colors.HexColor("#173F2A"), colors.HexColor("#367247"), colors.HexColor("#526459")
    styles = {
        "kicker": ParagraphStyle("NewsKicker", fontName="NewsSansBold", fontSize=8.5, leading=12, textColor=green, spaceAfter=10),
        "title": ParagraphStyle("NewsTitle", fontName="NewsSansBold", fontSize=27, leading=32, textColor=dark, spaceAfter=12),
        "meta": ParagraphStyle("NewsMeta", fontName="NewsSans", fontSize=8.2, leading=12, textColor=muted, spaceAfter=8),
        "h2": ParagraphStyle("NewsCompany", fontName="NewsSansBold", fontSize=18, leading=23, textColor=dark, spaceBefore=20, spaceAfter=6, keepWithNext=True),
        "h3": ParagraphStyle("NewsHeadline", fontName="NewsSansBold", fontSize=12.5, leading=17, textColor=dark, spaceBefore=13, spaceAfter=6, keepWithNext=True),
        "body": ParagraphStyle("NewsBody", fontName="NewsSans", fontSize=10.5, leading=15.5, textColor=colors.HexColor("#263D2D"), spaceAfter=8),
        "angle": ParagraphStyle("NewsAngle", fontName="NewsSans", fontSize=10, leading=15, textColor=dark, spaceAfter=7),
        "qualification": ParagraphStyle("NewsQualification", fontName="NewsSans", fontSize=9, leading=13, textColor=colors.HexColor("#72561E"), leftIndent=10, borderColor=colors.HexColor("#D7C58B"), borderWidth=1, borderPadding=7, spaceBefore=3, spaceAfter=10),
        "source": ParagraphStyle("NewsSource", fontName="NewsSans", fontSize=8.2, leading=12, textColor=muted, spaceAfter=6, splitLongWords=True),
        "toc": ParagraphStyle("NewsContents", fontName="NewsSans", fontSize=9, leading=13, textColor=dark),
    }

    def anchor(kind, identity):
        return kind + "_" + sha256(_text(identity).encode()).hexdigest()[:20]

    class NewsDocument(BaseDocTemplate):
        def afterFlowable(self, flowable):
            key = getattr(flowable, "_news_bookmark", None)
            if key:
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(getattr(flowable, "_news_title", "Section"), key,
                                         level=getattr(flowable, "_news_level", 0), closed=False)

    output = BytesIO()
    doc = NewsDocument(output, pagesize=LETTER, leftMargin=.7 * inch, rightMargin=.7 * inch,
                       topMargin=.75 * inch, bottomMargin=.75 * inch, title=view["title"], author="Berry Intelligence OS")

    def footer(pdf_canvas, document):
        pdf_canvas.saveState()
        pdf_canvas.setFillColor(green)
        pdf_canvas.rect(doc.leftMargin, LETTER[1] - .43 * inch, 32, 3, fill=1, stroke=0)
        pdf_canvas.setFont("NewsSans", 7)
        pdf_canvas.setFillColor(muted)
        pdf_canvas.drawString(doc.leftMargin, .4 * inch, _text(confidentiality))
        pdf_canvas.drawCentredString(LETTER[0] / 2, .4 * inch, "Working report; source review remains separate")
        pdf_canvas.drawRightString(LETTER[0] - doc.rightMargin, .4 * inch, str(document.page))
        pdf_canvas.restoreState()

    doc.addPageTemplates(PageTemplate(id="company-news", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")], onPage=footer))
    story: list[Any] = [Paragraph("BERRY INTELLIGENCE / COMPANY NEWS REVIEW", styles["kicker"]),
                       Paragraph(text(view["title"]), styles["title"]),
                       Paragraph(text(f"Published {view.get('from_date', '')} through {view.get('through_date', '')} · As of {view.get('as_of', '')}"), styles["meta"])]
    if view.get("overview"):
        story.append(Paragraph(text(view["overview"]), styles["body"]))
    if view["latest_findings"]:
        story.append(Paragraph("Latest included findings", styles["h2"]))
        for entry in view["latest_findings"]:
            story.append(Paragraph(text(entry["headline"]), styles["h3"]))
            story.append(Paragraph(text(entry["company_name"] + " · " + entry["published_date"]), styles["meta"]))
    counts = view["counts"]
    story.append(Paragraph(text(f"{counts['companies']} requested organizations · {counts['included']} included items · {counts['excluded']} excluded candidates retained in Excel · Research state: {_label(view.get('status'))}"), styles["meta"]))
    story.append(Paragraph("Company directory", styles["h2"]))
    directory = [[Paragraph("Company", styles["toc"]), Paragraph("Included / research outcome", styles["toc"])]]
    for company in view["companies"]:
        directory.append([Paragraph('<link href="#' + anchor("company", company["key"]) + '">' + text(company["name"]) + "</link>", styles["toc"]),
                          Paragraph(text(f"{company['included_count']} / {company['outcome']}"), styles["toc"])])
    table = Table(directory, colWidths=[doc.width * .44, doc.width * .56], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF5E6")),
                               ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#A7BFA1")),
                               ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#D7E2D2")),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([table, Spacer(1, 10)])

    def references(entry):
        parts = []
        for source in entry["sources"]:
            parts.append('<link href="#' + anchor("source", source["id"]) + '">' + text(source["reference"]) + "</link>")
        parts.extend(text("Missing reference: " + identity) for identity in entry["missing_source_ids"])
        return " · ".join(parts) or "No retained source reference"

    for company in (row for row in view["companies"] if row["included_entries"]):
        story.append(CondPageBreak(110))
        heading = Paragraph(text(company["name"]), styles["h2"])
        heading._news_bookmark = anchor("company", company["key"])
        heading._news_title = company["name"]
        heading._news_level = 0
        story.extend([heading, HRFlowable(width="100%", thickness=.7, color=colors.HexColor("#A7BFA1"), spaceAfter=8)])
        if company.get("requested_name") != company["name"]:
            story.append(Paragraph(text("Requested as " + _text(company.get("requested_name"))), styles["meta"]))
        story.append(Paragraph(text(company["outcome"] + " · Archive: " + _label(company.get("archive_status"))
                                    + " · Web: " + _label(company.get("web_status"))), styles["meta"]))
        if company.get("notes"):
            story.append(Paragraph(text(company["notes"]), styles["meta"]))
        for entry in company["included_entries"]:
            story.append(Paragraph(text(entry["headline"]), styles["h3"]))
            timing = "Published " + (entry.get("published_date") or "date not recorded")
            if entry.get("event_date"):
                timing += " · Event timing: " + entry["event_date"]
            timing += " · " + ("Reporting lead" if entry["entry_type"] == "lead" else "Development")
            timing += " · " + _label(entry.get("review_status") or "unreviewed")
            story.append(Paragraph(text(timing), styles["meta"]))
            if entry.get("summary"):
                story.append(Paragraph(text(entry["summary"]), styles["body"]))
            if entry.get("news_angle"):
                story.append(Paragraph("<b>News angle</b> · " + text(entry["news_angle"]), styles["angle"]))
            qualifications = [_text(entry.get("qualification"))] if entry.get("qualification") else []
            if entry["outside_window"]:
                qualifications.append("The publication date is outside the requested window; this item was included explicitly.")
            if not _date(entry.get("published_date")):
                qualifications.append("A publication date is not recorded; capture timing is not a publication date.")
            if qualifications:
                story.append(Paragraph(text("\n".join(qualifications)), styles["qualification"]))
            story.append(Paragraph("Sources · " + references(entry), styles["source"]))

    other_companies = [row for row in view["companies"] if not row["included_entries"]]
    if other_companies:
        story.append(CondPageBreak(95))
        story.append(Paragraph("Other company outcomes", styles["h2"]))
        for company in other_companies:
            heading = Paragraph("<b>" + text(company["name"]) + "</b> · " + text(company["outcome"]), styles["body"])
            heading._news_bookmark = anchor("company", company["key"])
            heading._news_title = company["name"]
            heading._news_level = 0
            story.append(heading)
            if company.get("notes"):
                story.append(Paragraph(text(company["notes"]), styles["meta"]))

    story.append(CondPageBreak(120))
    story.append(Paragraph("Scope and source references", styles["h2"]))
    story.append(Paragraph(text(f"Inclusive publication window: {view.get('from_date', '')} through {view.get('through_date', '')}. As of {view.get('as_of', '')}. Berry: {_text(view.get('berry_id')).removeprefix('berry-') or 'All berries'}. Topic: {view.get('topic') or 'Company news'}."), styles["body"]))
    story.append(Paragraph("The workflow searches the platform archive first and fills source gaps from the web when requested. Per-company outcomes distinguish completed, pending, partial and blocked research. Search completion does not prove exhaustive coverage. Publication dates, event timing and capture dates are distinct. Source and claim review gates remain separate from report editing.", styles["source"]))
    story.append(Paragraph(text(f"Saved review state: {_label(view.get('status'))}. {counts['included']} items are included in this narrative; {counts['excluded']} excluded candidates and every roster outcome remain available in the workbook."), styles["source"]))
    if not pdf_sources:
        message = "No source records were captured in this saved review." if not view["sources"] else "No retained source record supports the included selection. Source records for excluded candidates remain in the workbook."
        story.append(Paragraph(message, styles["body"]))
    elif len(pdf_sources) != len(view["sources"]):
        story.append(Paragraph("References below support the included selection. Source records for excluded candidates remain in the workbook.", styles["source"]))
    for source in pdf_sources:
        paragraph = Paragraph(text(source["reference"] + " · " + source["title"]), styles["h3"])
        paragraph._news_bookmark = anchor("source", source["id"])
        paragraph._news_title = source["reference"] + " · " + source["title"]
        paragraph._news_level = 0
        story.append(paragraph)
        facts = ["Published " + (source.get("published_date") or "date not recorded"),
                 _label(source.get("publication_date_basis")), _label(source.get("origin")), _text(source.get("trust_class")),
                 _label(source.get("capture_status")), _label(source.get("eligibility"))]
        story.append(Paragraph(text(" · ".join(value for value in facts if value)), styles["source"]))
        if source.get("qualification"):
            story.append(Paragraph(text(source["qualification"]), styles["source"]))
        if source["url"]:
            story.append(Paragraph('<link href="' + escape(source["url"], {'"': "&quot;"}) + '">' + text(source["url"]) + "</link>", styles["source"]))
        else:
            story.append(Paragraph("No public source URL is available.", styles["source"]))
    doc.build(story, canvasmaker=lambda *args, **kwargs: canvas.Canvas(*args, **{**kwargs, "invariant": 1}))
    return output.getvalue()
