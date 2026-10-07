"""Complete, escaped, standalone exports of the exact explorer bundle."""
import csv
from datetime import datetime, timezone
from html import escape
from io import StringIO
import textwrap
from app.services.landscape_explorer import ROLE_LABELS


def _meta(bundle):
    f = bundle["filters"]
    countries = ", ".join(lane["label"] for lane in bundle["lanes"]) or "All recorded countries"
    focus = bundle["nodes"].get(f["focus"], {}).get("label", f["focus"]) or "No focus"
    policy = "Reviewed sources" if f["evidence"] == "reviewed" else "Includes unreviewed sources"
    status = {"all": "All statuses, including disputes/history", "active": "Documented current", "historical": "Historical", "disputed": "Disputed / review required"}[f["status"]]
    role = ROLE_LABELS.get(f["predicate"], "All roles")
    clock = {"documented": "First captured / newly documented", "published": "Source publication", "event": "Recorded event / effective date"}[f["time"]]
    window = f"{f['start']} to {f['end']}" if f["start"] else "All recorded dates"
    return f"{countries} · {focus} · {policy} · {status} · {role} · Search: {f['q'] or 'none'} · {clock}: {window}"


def csv_export(bundle):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["data_version", "relationship_id", "subject_id", "subject", "predicate", "object_id", "object", "status", "scope", "caveat", "effective_date", "first_seen_source_capture", "source_number", "evidence_id", "source_title", "source_url", "source_review", "published_date", "captured_date", "relationship_notes", "subject_identity_status", "object_identity_status", "berry_id", "country_filters", "focus_id", "date_clock", "window_start", "window_end", "generated_at"])
    sources = {row["id"]: row for row in bundle["sources"]}
    def cell(value):
        value = str(value or "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
    for edge in bundle["edges"]:
        for sid in edge["evidence_ids"]:
            source = sources[sid]
            f = bundle["filters"]
            writer.writerow([cell(value) for value in [bundle["version"], edge["id"], edge["subject_id"], bundle["nodes"][edge["subject_id"]]["label"], edge["predicate"], edge["object_id"], bundle["nodes"][edge["object_id"]]["label"], edge["status"], edge["scope_kind"], edge["caveat"], edge["effective"], edge["first_seen"], source["number"], sid, source["title"], source["url"], source["review"], source["published"], source["captured"], edge["notes"], bundle["nodes"][edge["subject_id"]]["identity_status"], bundle["nodes"][edge["object_id"]]["identity_status"], f["berry"], ",".join(f["countries"]), f["focus"], f["time"], f["start"], f["end"], datetime.now(timezone.utc).isoformat()]])
    return "\ufeff" + output.getvalue()


def svg_export(bundle):
    """Vector panels: one readable labeled connection per row; no crop/loss."""
    sources = {row["id"]: row for row in bundle["sources"]}
    parts = []
    y = 34
    def text(value, x, top, *, size=14, weight="normal", color="#224334"):
        return f'<text x="{x}" y="{top}" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(value))}</text>'
    def lines(value, x, top, width=65, size=13):
        result = []
        for line in textwrap.wrap(str(value), width=width) or [""]:
            result.append(text(line, x, top, size=size))
            top += size + 6
        return "".join(result), top
    parts.append(text(bundle["title"], 30, y, size=30, weight="bold")); y += 32
    content, y = lines(_meta(bundle), 30, y, width=135); parts.append(content)
    parts.append(text(f"Generated {datetime.now(timezone.utc).isoformat()} · Data {bundle['version']} · Complete selected scope", 30, y)); y += 30
    parts.append(text("Legend: green documented · amber disputed · gray historical. Location ≠ variety growing presence.", 30, y)); y += 34
    for insight in bundle.get("insights", []):
        parts.append(text(insight["title"], 30, y, size=18, weight="bold")); y += 25
        content, y = lines(insight["text"], 30, y, width=130); parts.append(content)
        content, y = lines(insight["next_step"], 30, y, width=130); parts.append(content)
        content, y = lines("Sources: " + ", ".join(f"[{sources[sid]['number']}]" for sid in insight["evidence_ids"]), 30, y, width=130); parts.append(content)
        y += 15
    parts.append(text(bundle["explanation"]["question"], 30, y, size=20, weight="bold")); y += 28
    content, y = lines("Changes: " + bundle["explanation"]["changes"], 30, y, width=130); parts.append(content)
    parts.append(text("Unknowns and evidence boundaries", 30, y, weight="bold")); y += 24
    for warning in bundle["warnings"]:
        content, y = lines(warning, 30, y, width=135); parts.append(content)
    y += 20
    for index, edge in enumerate(bundle["edges"]):
        if index % 10 == 0:
            parts.append(text(f"Relationship panel {index // 10 + 1} · {len(bundle['edges'])} connections in selected scope", 30, y, size=19, weight="bold")); y += 32
        color = {"active": "#397940", "disputed": "#9b6414", "historical": "#737e75"}[edge["status"]]
        left_node, right_node = bundle["nodes"][edge["subject_id"]], bundle["nodes"][edge["object_id"]]
        left_label = left_node["label"] + (" · Provisional identity" if left_node["identity_note"] else "")
        right_label = right_node["label"] + (" · Provisional identity" if right_node["identity_note"] else "")
        name_height = max(len(textwrap.wrap(left_label, 36)), len(textwrap.wrap(right_label, 36))) * 21
        detail_y = max(80, name_height + 25)
        row_height = detail_y + 90
        parts.append(f'<rect x="30" y="{y}" width="1140" height="{row_height}" rx="9" fill="#ffffff" stroke="{color}"/>')
        parts.append(f'<path d="M 390 {y+38} H 780 l -9 -5 m 9 5 l -9 5" fill="none" stroke="{color}" stroke-width="2"/>')
        content, _ = lines(left_label, 45, y+28, width=36, size=15); parts.append(content)
        content, _ = lines(right_label, 800, y+28, width=36, size=15); parts.append(content)
        parts.append(text(edge["role"], 410, y+26, weight="bold", color=color))
        refs = ", ".join(f"[{sources[sid]['number']}]" for sid in edge["evidence_ids"])
        content, detail_end = lines(f"{edge['status_label']} · {edge['scope_kind']} · Sources {refs}", 45, y+detail_y, width=130); parts.append(content)
        content, detail_end = lines(edge["caveat"] or f"Event: {edge['effective'] or 'not recorded'} · First captured: {edge['first_seen'] or 'not recorded'}", 45, detail_end+5, width=135); parts.append(content)
        parts.append(text(edge["id"], 45, detail_end+5, size=11))
        y += row_height + 16
    if not bundle["edges"]:
        parts.append(text("No supported relationships match this selection.", 30, y)); y += 35
    parts.append(text("Numbered source notes", 30, y, size=21, weight="bold")); y += 30
    for source in bundle["sources"]:
        content, y = lines(f"[{source['number']}] {source['title']} · {source['id']} · {source['review']}", 30, y, width=130); parts.append(content)
        content, y = lines(f"Published {source['published'] or 'unknown'} · Captured {source['captured'] or 'unknown'} · {source['url'] or 'URL not recorded'}", 30, y, width=135)
        parts.append(f'<a href="{escape(source["url"], quote=True)}">{content}</a>' if source["url"] else content)
        content, y = lines(f"Locator: {source['locator']} · Origin: {source['origin']}", 30, y, width=135); parts.append(content)
        if source.get("varieties"):
            content, y = lines("Source-named varieties: " + ", ".join(row["name"] + (" (in catalog)" if row["catalog_id"] else " (catalog review needed)") for row in source["varieties"]), 30, y, width=135); parts.append(content)
        y += 12
    parts.append(text("Interpretation: connection counts show captured coverage, not company scale. Missing information is not inactivity.", 30, y)); y += 28
    content, y = lines("Return to refreshed view: " + bundle["url"], 30, y, width=130); parts.append(content)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{y+30}" viewBox="0 0 1200 {y+30}" role="img" aria-label="Complete landscape relationships and source notes"><rect width="1200" height="100%" fill="#f0f5eb"/><g font-family="Arial, sans-serif">' + "".join(parts) + "</g></svg>"


def html_export(bundle, *, return_url=""):
    e = lambda value: escape(str(value or ""), quote=True)
    refs = {row["id"]: row["number"] for row in bundle["sources"]}
    findings = "".join(f'<li>{e(row["text"])} ' + " ".join(f'<a href="#source-{refs[sid]}">[{refs[sid]}]</a>' for sid in row["evidence_ids"]) + "</li>" for row in bundle["explanation"]["findings"])
    rows = []
    for edge in bundle["edges"]:
        citations = " ".join(f'<a href="#source-{refs[sid]}">[{refs[sid]}]</a>' for sid in edge["evidence_ids"])
        rows.append(f'<tr><th>{e(bundle["nodes"][edge["subject_id"]]["label"])}<small>{e(bundle["nodes"][edge["subject_id"]]["identity_note"])}</small></th><td><b>{e(edge["role"])}</b><br>{e(edge["status_label"])}<br>{e(edge["caveat"])}</td><td>{e(bundle["nodes"][edge["object_id"]]["label"])}<small>{e(bundle["nodes"][edge["object_id"]]["identity_note"])}</small></td><td>{e(edge["scope_kind"])}<br>Event: {e(edge["effective"] or "Unknown")}<br>First captured: {e(edge["first_seen"] or "Unknown")}<br>Publication: {e(", ".join(edge["published"]) or "Unknown")}</td><td>{citations}<small>{e(edge["id"])}</small><p>{e(edge["notes"])}</p></td></tr>')
    sources = "".join(f'<li id="source-{row["number"]}"><h3>[{row["number"]}] {e(row["title"])}</h3><p>{e(row["review"])} · Published {e(row["published"] or "unknown")} · Captured {e(row["captured"] or "unknown")}</p><a href="{e(row["url"])}">{e(row["url"] or "Original URL not recorded")}</a><p>{e(row["summary"])}</p><p>Locator: {e(row["locator"])}</p><small>{e(row["id"])} · Origin: {e(row["origin"])}</small></li>' for row in bundle["sources"])
    lanes = "".join(f'<section class="lane"><h3>{e(lane["label"])}</h3><ul>' + "".join(f'<li>{e(actor["label"])} <small>{e(actor["type"].replace("_", " "))}</small></li>' for actor in lane["all_actors"]) + '</ul><p>Exact location links only; portfolios are not assigned growing locations.</p></section>' for lane in bundle["lanes"])
    takeaways = '<div class="lanes">' + "".join('<section class="lane"><h3>' + e(row["title"]) + '</h3><p class="lead">' + e(row["text"]) + '</p><p>' + e(row["next_step"]) + '</p>' + " ".join(f'<a href="#source-{refs[sid]}">[{refs[sid]}]</a>' for sid in row["evidence_ids"]) + '</section>' for row in bundle.get("insights", [])) + '</div>'
    sources += ''.join('<li><h3>Varieties named in source ' + str(source["number"]) + '</h3><p>' + ', '.join(e(row["name"]) + (' (in catalog)' if row["catalog_id"] else ' (catalog review needed)') for row in source.get("varieties", [])) + '</p></li>' for source in bundle["sources"] if source.get("varieties"))
    market_rows = ''.join('<tr><th>' + e(row['actor']['label']) + '</th>' + ''.join('<td>' +
        '<br>'.join(e(edge['location_label']) + ' ' + ' '.join(f'<a href="#source-{refs[sid]}">[{refs[sid]}]</a>' for sid in edge['evidence_ids']) for edge in market['edges']) + '</td>' for market in row['markets']) + '</tr>' for row in bundle.get('market_rows', []))
    matrix = '<table><thead><tr><th>Company</th>' + ''.join('<th>' + e(lane['label']) + '</th>' for lane in bundle['lanes']) + '</tr></thead><tbody>' + market_rows + '</tbody></table><p>Company locations are not variety growing footprints. Blank cells mean no location record in this scope.</p>'
    lanes = takeaways + matrix
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + f'<title>{e(bundle["title"])}</title>' + '''<style>
body{font:15px/1.5 Arial,sans-serif;color:#193d2e;background:#f3f7ee;margin:0}main{max-width:1180px;margin:auto;padding:32px}h1{font-size:36px;line-height:1.15;margin:6px 0 18px}h2{font-size:24px;margin-top:32px}h3{font-size:18px}a{color:#17603e;overflow-wrap:anywhere}small{display:block;font-size:12px;color:#4c6254}.lead{font-size:18px}.scope{padding:18px;background:#e3edd9;border-left:5px solid #467638}.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.lane{background:white;border:1px solid #a7bea0;border-radius:10px;padding:14px}table{width:100%;border-collapse:collapse;background:white;font-size:13px}th,td{padding:12px;border:1px solid #bdcdb7;text-align:left;vertical-align:top}th{width:17%}tr{break-inside:avoid}thead{display:table-header-group}li{margin-bottom:14px}#sources>li{break-inside:avoid;padding:10px 0;border-bottom:1px solid #b7c9ac}.notes{background:#fff5de;padding:18px;border:1px solid #d9be85}@media print{body{background:white}main{padding:0;max-width:none}h2{break-after:avoid}a{color:#193d2e}button{display:none}.new-page{break-before:page}@page{size:A4 landscape;margin:14mm}}
</style><main>''' + f'<p>BERRY INTELLIGENCE · LANDSCAPE BRIEFING</p><h1>{e(bundle["title"])}</h1><div class="scope"><p class="lead">{e(_meta(bundle))}</p><p>Generated {e(datetime.now(timezone.utc).isoformat())} · Data version {e(bundle["version"])} · {len(bundle["edges"])} relationships · {len(bundle["sources"])} source records · {bundle["independence"]["independent_source_count"]} source origins</p><p>Complete selected scope is included below, including connections hidden by screen limits. This is a frozen export; the return link loads current data.</p><a href="{e(return_url or bundle["url"])}">Return to the selected landscape</a></div><h2>Landscape portrait</h2><div class="portrait">{lanes}</div><p>Legend: Documented = active registry relationship, not claim verification. Disputed = conflict or review required. Historical = retained historical record; an end date is not implied.</p><h2>{e(bundle["explanation"]["question"])}</h2><ol>{findings or "<li>No supported findings match this selection.</li>"}</ol><h2>Changes</h2><p>{e(bundle["explanation"]["changes"])}</p><h2>Possible implications</h2><p>{e(bundle["explanation"]["implications"][0])}</p><h2>Unknowns and boundaries</h2><ul class="notes">' + "".join(f'<li>{e(warning)}</li>' for warning in bundle["warnings"]) + f'</ul><h2 class="new-page">All selected relationships</h2><table><thead><tr><th>From</th><th>Relationship / status</th><th>To</th><th>Scope and clocks</th><th>Evidence and notes</th></tr></thead><tbody>{"".join(rows)}</tbody></table><h2 class="new-page">Numbered source notes</h2><ol id="sources">{sources}</ol></main></html>'
