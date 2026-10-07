"""Independent public germplasm comparison, not acquisition or identity approval.

Only literal Cultivar labels enter the comparison. Stocks, accessions, samples,
parents and dataset joins never create varieties, aliases or company roles.
"""
import csv
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from app.services.variety_universe.identity import candidate_query_names, fold_identity, resolve_identity

GDR_URL = "https://www.rosaceae.org/tripal_megasearch?datatype=tripal_megasearch_stock"
GENUS_BERRIES = {"Fragaria": ["berry-strawberry"], "Rubus": ["berry-raspberry", "berry-blackberry"]}
REQUIRED_FIELDS = {"Unique Name", "Type", "Organism", "Cultivar", "Accession", "Institutional Name", "Dataset"}


def analyze_gdr_csv(path: Path, *, checked_on: str, reported_stocks: int, query_organisms=None):
    """Reduce a supplied native export to body-free, literal comparison inputs.

    Stock keys retain organism; cultivar labels retain genus. Neither is an
    approved variety identity. Duplicate joins are accounted for, not discarded.
    """
    date.fromisoformat(checked_on)
    if type(reported_stocks) is not int or reported_stocks < 1:
        raise ValueError("A positive stock count from the public search is required")
    raw = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS <= set(reader.fieldnames or []):
            raise ValueError("The CSV lacks required GDR germplasm fields")
        rows = list(reader)
    if not rows:
        raise ValueError("The CSV is empty")
    stocks, labels, material_labels = set(), defaultdict(dict), defaultdict(set)
    nonlabel_stocks, label_stocks, organisms, row_counts = set(), set(), set(), Counter()
    for row in rows:
        if None in row or any(row.get(field) is None for field in REQUIRED_FIELDS):
            raise ValueError("The CSV contains an incomplete or malformed row")
        organism, unique = row["Organism"].strip(), row["Unique Name"].strip()
        genus = organism.split(" ", 1)[0]
        if genus not in GENUS_BERRIES or row["Type"].strip() != "accession" or not unique:
            raise ValueError("The export must contain only named Fragaria/Rubus accession keys")
        key = (unique, organism)
        stocks.add(key)
        organisms.add(organism)
        label = row["Cultivar"].strip()
        if not label:
            nonlabel_stocks.add(key)
            continue
        label_stocks.add(key)
        material_labels[key].add(label)
        row_counts[(genus, label)] += 1
        # Fields are literal references. Accession/institution numbers are not aliases.
        ref = (unique, organism, row["Accession"].strip(), row["Institutional Name"].strip())
        labels[(genus, label)].setdefault(ref, set())
        if row["Dataset"].strip():
            labels[(genus, label)][ref].add(row["Dataset"].strip())
    if len(stocks) != reported_stocks:
        raise ValueError(f"Export has {len(stocks)} stock/organism keys; search reported {reported_stocks}. Check scope or truncation")
    if query_organisms is not None and (not isinstance(query_organisms, list) or not query_organisms
            or any(not isinstance(item, str) or item.split(' ', 1)[0] not in GENUS_BERRIES for item in query_organisms)
            or not organisms <= set(query_organisms)):
        raise ValueError("Captured query organisms do not cover the exported rows")
    entries = []
    for (genus, label), refs in sorted(labels.items(), key=lambda item: (item[0][0], item[0][1].casefold(), item[0][1])):
        entries.append({"genus": genus, "name": label, "export_rows": row_counts[(genus, label)],
            "references": [{"unique_name": ref[0], "organism": ref[1], "accession": ref[2],
                "institutional_name": ref[3], "datasets": sorted(datasets),
                "other_cultivar_labels": sorted(material_labels[(ref[0], ref[1])] - {label})}
                for ref, datasets in sorted(refs.items())]})
    return {"kind": "unreviewed_external_germplasm_comparison", "id": "gdr-fragaria-rubus-accessions",
        "source_title": "Genome Database for Rosaceae", "source_url": GDR_URL, "checked_on": checked_on,
        "query": {"data_type": "Germplasm", "type": "accession", "selected_organisms": sorted(set(query_organisms or [])),
            "selection_retained": query_organisms is not None, "fields": "All Fields"},
        "observed_organisms": sorted(organisms),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "totals": {"export_rows": len(rows), "reported_stocks": reported_stocks, "stock_organism_keys": len(stocks),
            "distinct_cultivar_labels": len({entry["name"] for entry in entries}), "genus_label_keys": len(entries),
            "stocks_with_cultivar_label": len(label_stocks), "stocks_without_cultivar_label": len(stocks - label_stocks),
            "stocks_with_both_blank_and_named_rows": len(nonlabel_stocks & label_stocks),
            "stocks_with_multiple_cultivar_labels": sum(len(values) > 1 for values in material_labels.values())},
        "entries": entries}


def load_external_baselines(data_dir: Path):
    latest = {}
    for path in sorted((data_dir / "imports").glob("variety-external-baseline-*/comparison.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("kind") != "unreviewed_external_germplasm_comparison" or payload.get("source_url") != GDR_URL:
            raise ValueError("Unknown external germplasm comparison")
        date.fromisoformat(payload["checked_on"])
        entries = payload.get("entries")
        if not isinstance(entries, list) or any(not isinstance(row, dict) or row.get("genus") not in GENUS_BERRIES
                or not isinstance(row.get("name"), str) or not row["name"].strip()
                or type(row.get("export_rows")) is not int or row["export_rows"] < 1
                or not isinstance(row.get("references"), list) or not row["references"] for row in entries):
            raise ValueError("External comparison needs literal names, genera and references")
        for row in entries:
            for ref in row["references"]:
                if not isinstance(ref, dict) or any(not isinstance(ref.get(key), str)
                        for key in ("unique_name", "organism", "accession", "institutional_name")) or not ref["unique_name"]:
                    raise ValueError("External comparison needs literal collection identifiers")
                if ref["organism"].split(' ', 1)[0] != row["genus"] or any(
                        not isinstance(ref.get(key), list) or any(not isinstance(item, str) for item in ref[key])
                        for key in ("datasets", "other_cultivar_labels")):
                    raise ValueError("External comparison has inconsistent reference scope")
        if len({(row['genus'], row['name']) for row in entries}) != len(entries):
            raise ValueError("External comparison repeats a crop-group/name key")
        if len(entries) != payload["totals"]["genus_label_keys"]:
            raise ValueError("External comparison label accounting is inconsistent")
        if sum(row['export_rows'] for row in entries) > payload['totals']['export_rows']:
            raise ValueError("External comparison exceeds its exported row population")
        old = latest.get(payload["id"])
        if old is None or payload["checked_on"] >= old["checked_on"]:
            latest[payload["id"]] = payload
    return list(latest.values())


def compare_baseline(baseline, *, varieties, candidates):
    """Live exact-name comparison. Text matches suggest review, never sameness."""
    candidate_index = defaultdict(list)
    for candidate in candidates:
        for value, _role in candidate_query_names(candidate):
            folded = fold_identity(value)
            if len(folded) >= 3:
                candidate_index[folded].append(candidate)
    entries = []
    for entry in baseline["entries"]:
        berries = GENUS_BERRIES[entry["genus"]]
        resolution = resolve_identity({"candidate_name": entry["name"], "berry_ids": berries}, varieties)
        catalog = {match["variety_id"]: match["variety_name"] for match in resolution["matches"]
                   if match["reason"] == "exact_identity_string"}
        found = {candidate["id"]: candidate for candidate in candidate_index.get(fold_identity(entry["name"]), [])
                 if candidate.get("berry_id") in berries}
        status = "catalog_name_found" if catalog else "candidate_name_found" if found else "no_name_match"
        entries.append({**entry, "status": status,
            "catalog_matches": [{"id": key, "name": value, "href": "/entities/variety/" + key} for key, value in sorted(catalog.items())],
            "candidate_matches": [{"id": key, "name": candidate.get("candidate_name", key), "status": candidate.get("status", "unreviewed"),
                "human_gated": bool(candidate.get("human_gated")),
                "href": "/varieties/candidates?" + urlencode({"q": entry["name"]}) + "#" + key}
                for key, candidate in sorted(found.items())]})
    return {**baseline, "entries": entries, "comparison_counts": dict(Counter(row["status"] for row in entries))}


def external_coverage_view(*, baselines, varieties, candidates, filters):
    reports = [compare_baseline(row, varieties=varieties, candidates=candidates) for row in baselines]
    entries = [row for report in reports for row in report["entries"]]
    q = str(filters.get("external_q", "")).strip()[:200]
    genus = filters.get("external_genus", "")
    genus = genus if genus in GENUS_BERRIES else ""
    status = filters.get("external_status", "no_name_match")
    status = status if status in {"", "no_name_match", "catalog_name_found", "candidate_name_found"} else "no_name_match"
    rows = [row for row in entries if (not genus or genus == row["genus"]) and (not status or status == row["status"])
            and (not q or q.casefold() in row["name"].casefold() or any(q.casefold() in ref["unique_name"].casefold()
                     or q.casefold() in ref["accession"].casefold() for ref in row["references"]))]
    rows.sort(key=lambda row: (row["name"].casefold(), row["genus"]))
    pages = max(1, (len(rows) + 49) // 50)
    try:
        page = min(pages, max(1, int(filters.get("external_page", 1))))
    except (ValueError, TypeError):
        page = 1
    params = {key: value for key, value in filters.items() if key != "external_page"}
    def href(number):
        return "/varieties/coverage?" + urlencode({**params, "external_page": number}) + "#external-coverage"
    return {"reports": reports, "counts": dict(Counter(row["status"] for row in entries)),
        "filters": {"q": q, "genus": genus, "status": status}, "entries": rows[(page-1)*50:page*50],
        "filtered_count": len(rows), "page": page, "pages": pages,
        "previous_href": href(page-1) if page > 1 else "", "next_href": href(page+1) if page < pages else ""}
