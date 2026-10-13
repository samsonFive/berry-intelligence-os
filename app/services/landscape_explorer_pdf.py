"""Server-rendered, paginated Landscape snapshots; no browser/provider required.

Uses the existing report typography and ReportLab infrastructure. All selected
edges and source notes remain available beyond the portrait's display limit.
"""
from io import BytesIO
from pathlib import Path
from threading import RLock
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak

from app.services.report_builder.pdf_export import _styles as report_styles
from app.services.landscape_explorer_export import _meta, crop_label, trait_rows

_FONT_LOCK = RLock()
_FONTS = Path(__file__).resolve().parents[1] / "assets" / "pdf-fonts"
_GREEN = colors.HexColor("#286f42")
_LINE = colors.HexColor("#b9cdb0")
_SOFT = colors.HexColor("#edf4e6")


def _register_fonts():
    with _FONT_LOCK:
        if "BINoto" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("BINoto", str(_FONTS / "NotoSans-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("BINotoBold", str(_FONTS / "NotoSans-Bold.ttf")))
            pdfmetrics.registerFontFamily("BINoto", normal="BINoto", bold="BINotoBold", italic="BINoto", boldItalic="BINotoBold")
            for name in ("STSong-Light", "HeiseiMin-W3", "HYSMyeongJo-Medium"):
                pdfmetrics.registerFont(UnicodeCIDFont(name))


def _text(value):
    """Escape source text and choose CJK glyph runs without changing identities."""
    value = str("" if value is None else value).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-").replace("→", "->")
    runs, current, font = [], [], "BINoto"
    for char in value:
        code = ord(char)
        target = ("HeiseiMin-W3" if 0x3040 <= code <= 0x30FF else "HYSMyeongJo-Medium" if 0xAC00 <= code <= 0xD7AF else
                  "STSong-Light" if 0x3400 <= code <= 0x9FFF else "BINoto")
        if target != font and current:
            text = escape("".join(current))
            runs.append(text if font == "BINoto" else f'<font name="{font}">{text}</font>')
            current = []
        current.append(char)
        font = target
    if current:
        text = escape("".join(current))
        runs.append(text if font == "BINoto" else f'<font name="{font}">{text}</font>')
    return "".join(runs).replace("\n", "<br/>")


def pdf_export(bundle, *, return_url=""):
    _register_fonts()
    styles = report_styles()
    for style in styles.values():
        style.fontName = "BINotoBold" if "Bold" in style.fontName else "BINoto"
    styles["cell"] = ParagraphStyle("LandscapeCell", parent=styles["body"], fontSize=8.7, leading=12, spaceAfter=0)
    styles["cell_name"] = ParagraphStyle("LandscapeName", parent=styles["cell"], fontName="BINotoBold", textColor=_GREEN)
    styles["cell_meta"] = ParagraphStyle("LandscapeCellMeta", parent=styles["meta"], fontSize=7.5, leading=10.5, spaceAfter=0)
    styles["h2"].spaceBefore = 12
    styles["source_title"].keepWithNext = True
    output = BytesIO()
    size = landscape(LETTER)
    doc = SimpleDocTemplate(output, pagesize=size, leftMargin=40, rightMargin=40, topMargin=45, bottomMargin=40,
                            title=bundle["title"], author="Berry Intelligence", pageCompression=1)
    sources = {row["id"]: row for row in bundle["sources"]}
    nodes, edges, filters = bundle["nodes"], bundle["edges"], bundle["filters"]
    p = lambda value, style="body": Paragraph(_text(value), styles[style])
    refs = lambda edge: " ".join(f"[{sources[sid]['number']}]" for sid in edge["evidence_ids"])

    def table(rows, widths, *, shared_rows=()):
        # Oversized rows may paginate, but never leave a one-line row fragment
        # and a second repeated header at the foot of the same page.
        result = Table(rows, colWidths=widths, repeatRows=1, splitInRow=120, hAlign="LEFT")
        commands = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), _SOFT),
                    ("LINEBELOW", (0, 0), (-1, 0), .7, _GREEN), ("LINEBELOW", (0, 1), (-1, -1), .35, _LINE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
        commands += [("BACKGROUND", (0, index), (0, index), _SOFT) for index in shared_rows]
        result.setStyle(TableStyle(commands))
        return result

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFillColor(_GREEN)
        canvas.rect(40, size[1]-28, 40, 3, fill=1, stroke=0)
        canvas.setStrokeColor(_LINE)
        canvas.line(40, 30, size[0]-40, 30)
        canvas.setFont("BINoto", 7)
        canvas.setFillColor(colors.HexColor("#526459"))
        canvas.drawString(40, 18, "Landscape snapshot - source review does not verify every claim")
        canvas.drawRightString(size[0]-40, 18, f"Page {document.page}")
        canvas.restoreState()

    story = [p("BERRY INTELLIGENCE / LANDSCAPE BRIEFING", "kicker"), p(bundle["title"], "title"),
             p(f"Generated {bundle['generated_at']} / Data version {bundle['version']}", "meta"),
             p(_meta(bundle), "meta"),
             p(f"{len(edges)} sourced connections / {len(sources)} source records / {bundle['independence']['independent_source_count']} source origins", "h3"),
             p("Complete selected scope. Screen limits do not remove connections from this snapshot. Saved views reopen current data; this export remains dated.", "meta")]
    link = return_url or bundle["url"]
    story.append(Paragraph(f'<link href="{escape(link, {chr(34): "&quot;"})}" color="#286f42">Return to this selection with current data</link>', styles["source"]))
    if bundle.get("company_scope", {}).get("active"):
        story.append(p("Company scope includes matching companies/programs and programs linked through recorded ownership. Connected parties can appear; marks do not approve evidence.", "meta"))
        for edge in bundle["company_scope"]["basis"]:
            story.append(p(edge["label"] + " / " + edge["status_label"] + " / " + edge["review"] + (" / " + edge["caveat"] if edge["caveat"] else "") + " Sources " + refs(edge), "meta"))
    for insight in bundle.get("insights", []):
        story += [p(insight["title"], "h2"), p(insight["text"], "takeaway"), p(insight["next_step"], "meta"),
                  p("Sources: " + " ".join(f"[{sources[sid]['number']}]" for sid in insight["evidence_ids"]), "meta")]
    story += [p("Evidence boundaries", "h3"),
              p("Documented = a stored active relationship. Historical = a retained older link. Disputed = conflict or review required. None is blanket claim verification.", "meta")]
    for warning in bundle["warnings"]:
        story.append(p(warning, "meta"))
    crops = bundle.get("crop_scopes", [])
    if crops:
        story.append(p("Recorded coverage by crop", "h2"))
        rows = [[p(text, "cell_name") for text in ("Crop", "Connections", "Sources", "Direct genetics-location links")]]
        rows += [[p(c["label"], "cell_name"), p(c["coverage"]["relationships"], "cell"), p(c["coverage"]["sources"], "cell"), p(c["coverage"]["genetic_location_links"], "cell")] for c in crops]
        story.append(table(rows, [doc.width*.35, doc.width*.18, doc.width*.18, doc.width*.29]))

    if filters.get("pair"):
        story += [CondPageBreak(110), p("Compare companies and programs", "h2"),
                  p("Shared companies/programs are highlighted. Varieties remain separate. These counts and roles do not establish market scale or shared growing locations.", "meta")]
        rows = [[p("Company / program", "cell_name"), *[p(c["label"], "cell_name") for c in crops]]]
        shared_rows = []
        for key, node in nodes.items():
            if node["type"] not in {"company", "breeding_program"}:
                continue
            shared = key in bundle.get("common_actor_ids", [])
            name = node["label"] + ("\nShared " + ("program" if node["type"] == "breeding_program" else "company") if shared else "")
            if node["identity_note"]:
                name += "\n" + node["identity_note"]
            values = []
            for crop in crops:
                selected = [edge for edge in edges if edge["id"] in crop["edge_ids"] and key in {edge["subject_id"], edge["object_id"]}]
                entries = []
                for edge in selected:
                    label = edge["role"] + " -> " + nodes[edge["object_id"]]["label"] if edge["subject_id"] == key else edge["label"]
                    qualifier = edge["caveat"] or (edge["status_label"] if edge["status"] != "active" else "")
                    entries.append(label + ("\n" + qualifier if qualifier else "") + " " + refs(edge))
                values.append(p("\n".join(entries) or "No sourced connections in this selection.", "cell"))
            rows.append([p(name, "cell_name"), *values])
            if shared:
                shared_rows.append(len(rows)-1)
        story.append(table(rows, [doc.width*.25, doc.width*.375, doc.width*.375], shared_rows=shared_rows))
    else:
        story += [CondPageBreak(110), p("Companies across these markets", "h2"),
                  p("Country cells show exact recorded company-location links. Blank cells mean no location record, not inactivity. Connected varieties are not assigned to company locations.", "meta")]
        lanes = bundle["lanes"]
        for start in range(0, len(lanes), 3):
            group = lanes[start:start+3]
            rows = [[p("Company", "cell_name"), *[p(lane["label"], "cell_name") for lane in group]]]
            for row in bundle.get("market_rows", []):
                markets = row["markets"][start:start+3]
                if not any(m["edges"] for m in markets):
                    continue
                cells = [p("\n\n".join(edge["location_label"] + ("\n" + edge["status_label"] if edge["status"] != "active" else "") + " " + refs(edge) for edge in m["edges"]) or "-", "cell") for m in markets]
                rows.append([p(row["actor"]["label"], "cell_name"), *cells])
            story.append(table(rows, [doc.width*.28, *[doc.width*.72/len(group)]*len(group)]))
            story.append(Spacer(1, 12))
        if not bundle.get("market_rows"):
            story.append(p("No sourced company-location links match. Genetics connections may still be available below.", "body"))

    story += [CondPageBreak(110), p("All selected connections", "h2"),
              p("Every connection, including rows hidden by screen limits. Read breeder, owner, licensee, grower, marketer and distributor as separate roles.", "meta")]
    note_numbers = {}
    rows = [[p(label, "cell_name") for label in ("Connection", "Scope / dates", "Evidence")]]
    for edge in edges:
        left, right = nodes[edge["subject_id"]], nodes[edge["object_id"]]
        notes = edge["notes"]
        if notes and notes not in note_numbers:
            note_numbers[notes] = len(note_numbers) + 1
        name = [p(left["label"], "cell_name"), p(edge["role"] + " -> " + right["label"], "cell")]
        for node in (left, right):
            if node["identity_note"]:
                name.append(p(node["label"] + ": " + node["identity_note"], "cell_meta"))
        scope = crop_label(edge) + " / " + edge["status_label"]
        scope += "\n" + (edge["caveat"] or edge["scope_kind"])
        scope += f"\nEvent: {edge['effective'] or 'Not recorded'}\nPublished: {', '.join(edge['published']) or 'Not recorded'}\nFirst captured: {edge['first_seen'] or 'Not recorded'}"
        evidence = "Sources " + refs(edge) + "\n" + edge["review"]
        if notes:
            evidence += "\nContext note " + str(note_numbers[notes])
        evidence += "\n" + edge["id"]
        rows.append([name, p(scope, "cell_meta"), p(evidence, "cell_meta")])
    if edges:
        story.append(table(rows, [doc.width*.42, doc.width*.30, doc.width*.28]))
    if not edges:
        story.append(p("No sourced relationships match this selection.", "body"))
    if note_numbers:
        story += [CondPageBreak(110), p("Connection context notes", "h2"),
                  p("Exact repeated notes appear once. Each connection above identifies its note; separate relationships and source review states are retained.", "meta")]
        for notes, number in note_numbers.items():
            story += [p("Context note " + str(number), "source_title"), p(notes, "cell"), Spacer(1, 8)]
    if trait_rows(bundle):
        story += [CondPageBreak(110), p("Cited variety traits and sensory context", "h2"),
                  p("Source claims and measurements keep their conditions; different trials and scales are not a common ranking. Numbers are not generalized beyond their cited scope.", "meta")]
        rows = [[p(label, "cell_name") for label in ("Variety / trait", "Reported value", "Basis / conditions / sources")]]
        seen_notes = set()
        for node, row in trait_rows(bundle):
            citations = " ".join(f"[{sources[sid]['number']}]" for sid in row["evidence_ids"])
            value = [p(row["display_value"] + ("\nUnits: " + row["units"] if row["units"] else ""), "cell")]
            if node.get("trait_note") and node["id"] not in seen_notes:
                note_refs = " ".join(f"[{sources[sid]['number']}]" for sid in node["trait_note_evidence_ids"])
                value.append(p("Variety profile note: " + node["trait_note"] + " Sources " + note_refs, "cell_meta"))
                seen_notes.add(node["id"])
            rows.append([p(node["label"] + "\n" + row["trait_name"], "cell_name"), value,
                         p(row["source_kind"] + "\n" + (row["asserted_by"] or "Reporting party not recorded") + "\n" + (row["conditions"] or "Conditions not recorded") + "\nSources " + citations, "cell_meta")])
        story.append(table(rows, [doc.width*.25, doc.width*.4, doc.width*.35]))
    story += [CondPageBreak(110), p(bundle["explanation"]["question"], "h2")]
    for finding in bundle["explanation"]["findings"]:
        story += [p(finding["text"], "body"), p("Sources " + " ".join(f"[{sources[sid]['number']}]" for sid in finding["evidence_ids"]), "meta")]
    story += [p("Changes", "h3"), p(bundle["explanation"]["changes"]),
              p("Possible implications - interpretation", "h3"), p(bundle["explanation"]["implications"][0]),
              CondPageBreak(110), p("Numbered source notes", "h2")]
    for source in bundle["sources"]:
        story += [p(f"[{source['number']}] {source['title']}", "source_title"),
                  p(f"{source['source_name']} / {source['review']} / Published: {source['published'] or 'Not recorded'} / Captured: {source['captured'] or 'Not recorded'}", "cell_meta")]
        if source["url"]:
            url = escape(source["url"], {'"': '&quot;'})
            story.append(Paragraph(f'<link href="{url}" color="#286f42">{_text(source["url"])}</link>', styles["cell_meta"]))
        else:
            story.append(p("Original URL not recorded.", "source"))
        story += [p("Source summary", "cell_name"), p(source["summary"], "cell"),
                  p("Locator: " + source["locator"] + " / Origin: " + source["origin"], "cell_meta"),
                  p("Source record " + source["id"], "cell_meta")]
        if source.get("varieties"):
            story.append(p("Names in this source: " + ", ".join(row["name"] + (" (catalog)" if row["catalog_id"] else " (catalog review needed)") for row in source["varieties"]), "cell_meta"))
        story.append(Spacer(1, 12))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
