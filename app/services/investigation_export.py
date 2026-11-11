"""Explicit, dated investigation output over current governed domain models.

Preview and PDF rebuild the same selected payload. A content hash guards against
changed records between those actions. There is no new store, acquisition,
provider invocation, source-body hydration, or canonical mutation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any

from app.services import investigation_api as api

SECTION_TITLES = {
    "readout": "What the applied scope shows",
    "relationships": "Complete recorded relationships",
    "portfolio": "Recorded company and cultivar portfolio",
    "geography": "Recorded geographic activity",
    "comparison": "Selected profile comparison",
    "developments": "Relevant retained developments",
}
DEFAULT_SECTIONS = tuple(SECTION_TITLES)
DEMO_PATH = Path(__file__).resolve().parents[1] / "demo_data/flavor/synthetic-overall-liking-v1.json"


class ContentChangedError(ValueError):
    """The explicitly previewed data basis is no longer the current basis."""


def _load_demo():
    fixture = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    metric, specimens = fixture.get("metric", {}), fixture.get("specimens", [])
    if (fixture.get("synthetic") is not True or fixture.get("namespace") != "synthetic-sensory-v1"
            or metric.get("id") != "overall_liking" or metric.get("minimum") != 1 or metric.get("maximum") != 9
            or not isinstance(specimens, list) or not specimens
            or any(not str(row.get("id", "")).startswith("demo-specimen-")
                   or isinstance(row.get("value"), bool) or not isinstance(row.get("value"), (int, float))
                   or not 1 <= row["value"] <= 9 for row in specimens)
            or len({row["id"] for row in specimens}) != len(specimens)):
        raise ValueError("The isolated synthetic fixture is unavailable or incompatible.")
    return fixture


def _selected_demo(context):
    fixture = _load_demo()
    requested = api.ids(context.get("demo_specimens", ""))
    available = {row["id"] for row in fixture["specimens"]}
    if requested and set(requested) - available:
        raise ValueError("Some selected demo specimens are unavailable. Choose available specimens or explicitly select all before exporting the synthetic annex.")
    return {**fixture, "specimens": [row for row in fixture["specimens"] if not requested or row["id"] in requested]}


def _source_ids(value):
    """Find explicit evidence references in curated presenter objects only."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_ids" and isinstance(item, list):
                found.update(str(v) for v in item if v)
            elif key == "evidence_id" and item:
                found.add(str(item))
            elif key not in {"record", "article", "transcript", "decision"}:
                found.update(_source_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_source_ids(item))
    return found


def _comparison_projection(world, context):
    """Curated complete presenter values, with exact role edges alongside them."""
    raw = api.comparison_data(world, context)
    kind = raw["comparison_kind"]
    if kind == "company":
        companies = []
        for company in raw.get("companies", []):
            roles = {}
            for bucket, parties in company.get("roles", {}).items():
                roles[bucket] = [{"id": party["id"], "name": party.get("name") or party["id"]} for party in parties]
            variety_ids = {party["id"] for parties in roles.values() for party in parties}
            role_edges = [{key: edge.get(key) for key in ("id", "subject_id", "object_id", "predicate", "status", "notes", "evidence_ids")}
                          for edge in world.relationships
                          if edge.get("subject_id") == company["id"] and edge.get("object_id") in variety_ids]
            companies.append({"id": company["id"], "name": company["name"], "berries": company.get("berries", []),
                              "roles": roles, "role_edges": role_edges,
                              "geographies": [{"id": row["id"], "name": row.get("name") or row["id"]} for row in company.get("geographies", [])],
                              "rights_published": [{key: row.get(key) for key in ("id", "title", "kind", "published_date")}
                                                   for row in company.get("rights_published", [])]})
        return {"comparison_kind": kind, "companies": companies, "role_labels": raw.get("role_labels", {}),
                "invalid_ids": raw.get("invalid_ids", []), "overflow_ids": raw.get("overflow_ids", []),
                "scope_applicability": raw["scope_applicability"]}
    varieties = []
    for variety in raw.get("varieties", []):
        varieties.append({"id": variety["id"], "name": world.entities[variety["id"]].get("name", variety["id"]),
                          "berries": variety.get("berries", []),
                          "countries_observed": [{"id": row["id"], "name": row.get("name") or row["id"]} for row in variety.get("countries_observed", [])],
                          "rights_published": [{key: row.get(key) for key in ("id", "title", "kind", "published_date")}
                                               for row in variety.get("rights_published", [])]})
    dimensions = []
    for dimension in raw.get("dimensions", []):
        dimensions.append({"name": dimension["name"], "cells": [
            {"variety_id": cell["variety_id"], "has_data": cell["has_data"], "rows": [
                {key: row.get(key) for key in ("id", "statement", "fact_status", "evidence_id", "does_not_prove", "geography", "trait_names")}
                for row in cell.get("rows", [])]} for cell in dimension.get("cells", [])]})
    return {"comparison_kind": kind, "varieties": varieties, "dimensions": dimensions,
            "invalid_ids": raw.get("invalid_ids", []), "overflow_ids": raw.get("overflow_ids", []),
            "scope_applicability": raw["scope_applicability"]}


def build_payload(world, context_values, section_ids=None, include_demo=False):
    if not isinstance(context_values, dict) or set(context_values) - set(api.CONTEXT_FIELDS):
        raise ValueError("Export context must contain only supported investigation selectors.")
    context, issues = api.normalize_context(context_values)
    sections = list(DEFAULT_SECTIONS if section_ids is None else section_ids)
    if (not sections or len(sections) > len(SECTION_TITLES) or len(set(sections)) != len(sections)
            or any(section not in SECTION_TITLES for section in sections)):
        raise ValueError("Choose one or more supported export sections without duplicates.")
    if not isinstance(include_demo, bool):
        raise ValueError("Synthetic annex selection must be explicit true or false.")
    bundle = api.base_bundle(world, context)
    issues += api.selection_issues(world, context, bundle)
    landscape = api.landscape_data(world, context, bundle)
    data, summaries, source_ids = {}, [], set()
    extra_sources = {}
    for section in sections:
        section_source_ids = set()
        if section == "readout":
            content = deepcopy(landscape["findings"])
            count, basis = len(content), "Deterministic findings about the applied standing scope; focus does not redefine them."
        elif section == "relationships":
            content = deepcopy(landscape["edges"])
            count, basis = len(content), "All matching directed stored relationships, beyond the initial screen rows."
        elif section == "portfolio":
            content = []
            for portrait in landscape["portfolios"]:
                for edge in portrait["portfolio_edges"]:
                    content.append({"actor_id": portrait["actor"]["id"], "actor": portrait["actor"]["label"], "edge": deepcopy(edge)})
            count, basis = len(content), "Associated actor and actual directed program/cultivar edge; no invented intermediary or growing location."
        elif section == "geography":
            content = [deepcopy(edge) for edge in landscape["edges"] if edge["company_geography"] or edge["genetic_geography"]]
            count, basis = len(content), "Exact geographic relationship basis; company activity is not cultivar growing evidence."
        elif section == "comparison":
            content = _comparison_projection(world, context)
            count = len(content.get("companies", content.get("varieties", [])))
            basis = "Full selected profiles; berry, country and publication filters do not trim portfolio records."
            for entity in content.get("companies", content.get("varieties", [])):
                section_source_ids.update(row["id"] for row in entity.get("rights_published", []))
        else:
            developments = api.developments_data(world, context, bundle, all_cards=True)
            allowed = ("id", "headline", "deck", "source_name", "source_url", "published_at", "source_reviewed", "trusted",
                       "media_label", "media_note", "company_mentions", "scope_match", "coverage_sources", "independence", "translated", "translation_pending")
            content = {"heading": developments["heading"], "basis": developments["basis"],
                       "scope_applicability": developments.get("scope_applicability", {}),
                       "cards": [{key: card.get(key) for key in allowed if key in card} for card in developments["cards"]]}
            count = len(content["cards"])
            if count != developments["matching_count"]:
                raise ValueError("The complete developments basis could not be resolved; no partial PDF was produced.")
            basis = "Source geography and publication dates, then " + developments["basis"] + "; all matching retained source rows."
            for card in content["cards"]:
                section_source_ids.add(card["id"])
                section_source_ids.update(row["id"] for row in card.get("coverage_sources") or [])
            extra_sources = {row["id"]: row for row in developments.get("sources", [])}
        refs = _source_ids(content)
        refs.update(section_source_ids)
        source_ids.update(refs)
        data[section] = content
        summaries.append({"id": section, "title": SECTION_TITLES[section], "row_count": count, "basis": basis,
                          "source_ids": sorted(refs)})
    sources = []
    metadata_index = {row["id"]: row for row in landscape["sources"]}
    metadata_index.update(extra_sources)
    for key in sorted(source_ids):
        metadata = metadata_index.get(key)
        if metadata is None and key in world.evidence_index:
            metadata = api.source_metadata(world.evidence_index[key])
        if metadata is None:
            metadata = {"id": key, "availability": "Source metadata unavailable in the current authorized read model"}
        sources.append({key: value for key, value in metadata.items() if key in
                        {"id", "title", "url", "source_name", "status", "review", "published", "captured", "availability"}})
    label = lambda key: world.entities.get(key, {}).get("name", key)
    payload = {"export_v": 1, "context": context, "section_ids": sections, "include_demo": include_demo,
               "scope": {"berry": "All berries" if context["berry"] == "all" else label(context["berry"]),
                         "countries": [label(key) for key in api.ids(context["countries"])],
                         "geographic_basis": context["geo_basis"], "actor_roles": api.ids(context["actor_roles"]),
                         "standing_geographic_basis": api.module_scope(context, "landscape")["geo_basis"],
                         "developments_geographic_basis": "source_geography",
                         "relationship_types": api.ids(context["relationship_types"]),
                         "news_from": context["news_from"], "news_to": context["news_to"],
                         "comparison_companies": [label(key) for key in api.ids(context["cohort_companies"])],
                         "comparison_varieties": [label(key) for key in api.ids(context["cohort_varieties"])]},
               "nodes": {key: {field: row[field] for field in ("id", "label", "type", "identity_status", "identity_note") if field in row}
                         for key, row in landscape["nodes"].items()},
               "sections": summaries, "data": data, "sources": sources, "issues": issues,
               "scope_notes": landscape["scope_notes"]}
    if include_demo:
        payload["demo_annex"] = _selected_demo(context)
    return payload


def content_hash(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def preview(world, context_values, section_ids=None, include_demo=False):
    payload = build_payload(world, context_values, section_ids, include_demo)
    return {"api_v": 1, "content_hash": content_hash(payload), "section_ids": payload["section_ids"],
            "include_demo": include_demo, "scope": payload["scope"], "sections": payload["sections"],
            "sources": payload["sources"], "issues": payload["issues"],
            "synthetic_annex": {"namespace": payload["demo_annex"]["namespace"], "metric": payload["demo_annex"]["metric"],
                                "specimen_count": len(payload["demo_annex"]["specimens"]),
                                "specimen_labels": [row["label"] for row in payload["demo_annex"]["specimens"]],
                                "selection_mode": "explicit selection" if payload["context"].get("demo_specimens") else "all available specimens"} if include_demo else None,
            "date_note": "The PDF will carry its generation time; source publication and capture dates retain their distinct meaning."}


def pdf(world, context_values, section_ids, include_demo, expected_content_hash):
    if not isinstance(expected_content_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_content_hash):
        raise ValueError("Preview the exact selected output before requesting the PDF.")
    payload = build_payload(world, context_values, section_ids, include_demo)
    current = content_hash(payload)
    if current != expected_content_hash:
        raise ContentChangedError("The investigation basis changed after preview. Review a fresh preview before exporting.")
    return render_pdf(payload), current


def render_pdf(payload, *, generated_at=None):
    """Render complete selected domain rows using the existing bundled Noto fonts."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.graphics.shapes import Circle, Drawing, Line, String
    from app.services.landscape_explorer_pdf import _register_fonts, _text
    _register_fonts()
    ink, muted = colors.HexColor("#24382d"), colors.HexColor("#5f6e62")
    forest, line, sage = colors.HexColor("#284e37"), colors.HexColor("#dce0d3"), colors.HexColor("#edf1e7")
    styles = {
        "title": ParagraphStyle("InvestigationTitle", fontName="BINotoBold", fontSize=25, leading=31, textColor=ink, spaceAfter=13),
        "h2": ParagraphStyle("InvestigationHeading", fontName="BINotoBold", fontSize=16, leading=22, textColor=forest, spaceBefore=18, spaceAfter=10, keepWithNext=True),
        "h3": ParagraphStyle("InvestigationSubheading", fontName="BINotoBold", fontSize=10, leading=14, textColor=ink, spaceBefore=9, spaceAfter=6, keepWithNext=True),
        "body": ParagraphStyle("InvestigationBody", fontName="BINoto", fontSize=9, leading=13.5, textColor=ink, spaceAfter=7, splitLongWords=True),
        "meta": ParagraphStyle("InvestigationMetadata", fontName="BINoto", fontSize=7.5, leading=11, textColor=muted, spaceAfter=6, splitLongWords=True),
        "cell": ParagraphStyle("InvestigationCell", fontName="BINoto", fontSize=7.5, leading=10.5, textColor=ink, spaceAfter=0, splitLongWords=True),
    }
    p = lambda text, style="body": Paragraph(_text(text), styles[style])
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=43, rightMargin=43, topMargin=43, bottomMargin=43,
                                 title="Berry OS - Landscape investigation", author="Berry OS", pageCompression=1)
    stamp = generated_at or datetime.now(timezone.utc)
    generated = stamp.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    sources = {row["id"]: row for row in payload["sources"]}
    numbers = {key: index + 1 for index, key in enumerate(sources)}
    refs = lambda values: " ".join(f"[{numbers[key]}]" if key in numbers else f"[{key}: metadata unavailable]" for key in dict.fromkeys(values or []))
    node = lambda key: payload["nodes"].get(key, {}).get("label", key)
    relationship = lambda edge: edge.get("label") or f"{node(edge['subject_id'])} {edge.get('predicate', 'connects to')} {node(edge['object_id'])}"
    unknown = "Unknown / no recorded observation"

    def table(headers, rows, proportions):
        cells = [[p(value, "cell") for value in headers]] + [[p(value, "cell") for value in row] for row in rows]
        result = Table(cells, colWidths=[document.width * part for part in proportions], repeatRows=1, splitInRow=120, hAlign="LEFT")
        result.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), sage), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("GRID", (0, 0), (-1, -1), .35, line), ("LEFTPADDING", (0, 0), (-1, -1), 7),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        return result

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(line)
        canvas.line(43, 32, A4[0] - 43, 32)
        canvas.setFont("BINoto", 7)
        canvas.setFillColor(muted)
        canvas.drawString(43, 21, "Dated investigation output - source review does not approve every claim")
        canvas.drawRightString(A4[0] - 43, 21, str(doc.page))
        canvas.restoreState()

    scope = payload["scope"]
    story = [p("BERRY OS / INVESTIGATION OUTPUT", "meta"), p("Landscape investigation", "title"),
             p(scope["berry"] + " / " + (" / ".join(scope["countries"]) or "All countries"), "h3"),
             p("Generated " + generated + ". This is a dated output of current records, not a frozen canonical backend snapshot.", "meta"),
             p("Standing geographic basis: " + scope["standing_geographic_basis"].replace("_", " ") + ". Requested basis: " + scope["geographic_basis"].replace("_", " ") + ". Actor roles: " + (", ".join(scope["actor_roles"]) or "All authored roles") + ".", "meta"),
             p("Relationship filters: " + (", ".join(scope["relationship_types"]) or "All supported predicates") + ". Developments use source geography; comparison uses full selected profiles.", "meta"),
             p("Developments publication interval: " + (scope["news_from"] or "Earliest recorded") + " to " + (scope["news_to"] or "Latest recorded") + ". Dates do not trim standing portfolios.", "meta"),
             p("Included sections: " + "; ".join(SECTION_TITLES[key] for key in payload["section_ids"]) + ("; explicitly selected synthetic annex" if payload["include_demo"] else ""), "meta"),
             p("Recorded roles, source review, claim approval, analyst interpretation and synthetic demonstration retain separate meanings. Missing observations remain unknown; a coverage gap does not establish inactivity.", "body")]
    for issue in payload["issues"]:
        story.append(p(issue["message"] + (" " + str(issue["id"]) if issue.get("id") else ""), "meta"))
    for summary in payload["sections"]:
        section = summary["id"]
        content = payload["data"][section]
        story += [CondPageBreak(150), p(summary["title"], "h2"), p(summary["basis"], "meta")]
        if not content:
            story.append(p("No records in this selected section. Missing captured data does not establish no activity.", "body"))
            continue
        if section == "readout":
            for finding in content:
                story += [p(finding["text"]), p("Sources " + refs(finding["evidence_ids"]), "meta")]
        elif section == "relationships":
            for edge in content:
                story.append(KeepTogether([p(relationship(edge), "h3"),
                          p(edge["status_label"] + " / " + edge["review"] + " / " + edge["scope_kind"], "meta"),
                          p(edge["notes"]), p((edge["caveat"] + ". " if edge["caveat"] else "") + "Relationship " + edge["id"] + " / Sources " + refs(edge["evidence_ids"]), "meta")]))
        elif section == "portfolio":
            story.append(table(["Associated actor", "Actual directed edge", "Recorded role / status", "Sources"], [
                [row["actor"], node(row["edge"]["subject_id"]) + " -> " + node(row["edge"]["object_id"]),
                 row["edge"]["role"] + "\n" + row["edge"]["status_label"] + ("\n" + row["edge"]["caveat"] if row["edge"]["caveat"] else ""), refs(row["edge"]["evidence_ids"])]
                for row in content], [.21, .35, .29, .15]))
        elif section == "geography":
            for edge in content:
                story.append(KeepTogether([p(relationship(edge), "h3"), p(edge["location_label"] + ". " + edge["scope_kind"]),
                          p(edge["status_label"] + (" / " + edge["caveat"] if edge["caveat"] else "") + " / Sources " + refs(edge["evidence_ids"]), "meta")]))
        elif section == "comparison":
            for key in ("invalid_ids", "overflow_ids"):
                if content[key]:
                    story.append(p(key.replace("_", " ") + ": " + ", ".join(content[key]), "meta"))
            entities = content.get("companies", content.get("varieties", []))
            if not entities:
                story.append(p("No valid subjects selected for this typed comparison. Company and cultivar cohorts remain separate."))
            for entity in entities:
                story += [p(entity["name"], "h3"), p("Declared berries: " + (", ".join(entity["berries"]) or unknown), "meta")]
                if content["comparison_kind"] == "company":
                    for bucket, parties in entity["roles"].items():
                        if not parties:
                            continue
                        story.append(p(content["role_labels"].get(bucket, bucket.replace("_", " ")) + ": " + ", ".join(party["name"] for party in parties)))
                    for edge in entity["role_edges"]:
                        story.append(p("Relationship " + edge["id"] + " / " + str(edge["predicate"]) + " / " + str(edge["status"]) + " / Sources " + refs(edge.get("evidence_ids")), "meta"))
                    story.append(p("Geographic profile context: " + (", ".join(row["name"] for row in entity["geographies"]) or unknown) + ". Company locations and observed market context do not establish cultivar growing.", "meta"))
                else:
                    for dimension in content["dimensions"]:
                        cell = next((row for row in dimension["cells"] if row["variety_id"] == entity["id"]), None)
                        story.append(p(dimension["name"], "h3"))
                        if not cell or not cell["has_data"]:
                            story.append(p(unknown))
                        else:
                            for row in cell["rows"]:
                                story += [p(row["statement"]), p((row.get("fact_status") or "Recorded observation") + " / Sources " + refs([row["evidence_id"]] if row.get("evidence_id") else []), "meta")]
                                if row.get("does_not_prove"):
                                    story.append(p("Limits: " + "; ".join(row["does_not_prove"]), "meta"))
                    if not content["dimensions"]:
                        story.append(p("Sourced trait observations: " + unknown))
                    story.append(p("Observed commercial markets: " + (", ".join(row["name"] for row in entity["countries_observed"]) or unknown) + ". An observed market is not growing origin.", "meta"))
                for right in entity["rights_published"]:
                    story.append(p((right.get("title") or right["id"]) + " / " + (right.get("kind") or "Rights record") + " / Published " + str(right.get("published_date") or "Unknown") + " / " + refs([right["id"]]), "meta"))
        else:
            story.append(p(content["heading"], "h3"))
            if not content["cards"]:
                story.append(p("No retained developments match the applied subject and scope. No unfiltered fallback was substituted."))
            for card in content["cards"]:
                trust = "Escalated" if card.get("trusted") else "Source reviewed" if card.get("source_reviewed") else "Unreviewed source"
                entry = [p(card["headline"], "h3"), p((card.get("source_name") or "Publisher not recorded") + " / Published " + str(card.get("published_at") or "Unknown") + " / " + trust + " / " + refs([card["id"]]), "meta")]
                if card.get("deck"):
                    entry.append(p(card["deck"]))
                scope_match = card.get("scope_match") or {}
                if scope_match.get("kind") == "related_context":
                    entry.append(p(("About " + scope_match["primary_label"] + " / " if scope_match.get("primary_label") else "")
                                   + "Context for " + ", ".join(scope_match["subject_labels"]), "meta"))
                if card.get("company_mentions"):
                    entry.append(p("Mentioned in source: " + ", ".join(row["name"] for row in card["company_mentions"]) + ". Company link not reviewed.", "meta"))
                if card.get("media_label"):
                    entry.append(p(card["media_label"] + (" / " + card["media_note"] if card.get("media_note") else ""), "meta"))
                if card.get("coverage_sources"):
                    entry.append(p((card.get("independence") or "Retained source grouping; independence not stated") + " / Sources " + refs([row["id"] for row in card["coverage_sources"]]), "meta"))
                story.append(KeepTogether(entry))
    if payload["scope_notes"]:
        story.append(KeepTogether([p("Scope and source limits", "h2"), *(p(note, "meta") for note in payload["scope_notes"])]))
    story += [PageBreak(), p("Source appendix", "h2"), p("Publication and capture dates remain distinct. These references identify the retained source basis; source approval does not approve every claim.", "meta")]
    if not sources:
        story.append(p("No source references are attached to the selected sections."))
    for key, source in sources.items():
        entry = [p(f"[{numbers[key]}] " + (source.get("title") or source.get("availability") or key), "h3"),
                  p("ID: " + key + " / " + (source.get("source_name") or "Publisher not recorded"), "meta"),
                  p("Published: " + str(source.get("published") or "Unknown") + " / Captured: " + str(source.get("captured") or "Unknown"), "meta"),
                  p(source.get("review") or source.get("status") or source.get("availability") or "Review state unavailable", "meta")]
        if source.get("url"):
            entry.append(p(source["url"], "meta"))
        story.append(KeepTogether(entry))
    if payload["include_demo"]:
        fixture = payload["demo_annex"]
        story += [PageBreak(), p("SYNTHETIC ANNEX / FICTITIOUS SPECIMENS", "meta"), p(fixture["metric"]["label"], "h2"),
                  p(fixture["scope_note"]), p(fixture["disclaimer"], "meta")]
        drawing = Drawing(document.width, 75 + len(fixture["specimens"]) * 33)
        x1, x2, baseline = 120, document.width - 30, 35
        for tick in range(1, 10):
            x = x1 + (tick - 1) / 8 * (x2 - x1)
            drawing.add(Line(x, baseline, x, drawing.height - 12, strokeColor=line, strokeWidth=.4))
            drawing.add(String(x, baseline - 15, str(tick), fontName="BINoto", fontSize=8, textAnchor="middle", fillColor=muted))
        drawing.add(Line(x1, baseline, x2, baseline, strokeColor=muted, strokeWidth=.7))
        for index, specimen in enumerate(fixture["specimens"]):
            y = drawing.height - 25 - index * 33
            x = x1 + (specimen["value"] - 1) / 8 * (x2 - x1)
            drawing.add(String(x1 - 14, y - 3, specimen["label"], fontName="BINoto", fontSize=8, textAnchor="end", fillColor=ink))
            drawing.add(Circle(x, y, 4.5, fillColor=colors.HexColor("#70455f"), strokeColor=None))
            drawing.add(String(x + 10, y - 3, str(specimen["value"]), fontName="BINoto", fontSize=7.5, fillColor=muted))
        drawing.add(String((x1 + x2) / 2, 3, "Synthetic overall liking / 1-9", fontName="BINoto", fontSize=8, textAnchor="middle", fillColor=muted))
        story += [drawing, p("Synthetic illustration only. One value per fictitious specimen; no distribution, statistical comparison or real-cultivar measurement is represented.", "meta")]
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
