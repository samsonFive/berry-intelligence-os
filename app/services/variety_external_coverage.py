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
GRIN_URL = "https://npgsweb.ars-grin.gov/gringlobal/search"
GENUS_BERRIES = {"Fragaria": ["berry-strawberry"], "Rubus": ["berry-raspberry", "berry-blackberry"]}
EXTERNAL_GENERA = {*GENUS_BERRIES, "Vaccinium"}
# Exact source taxonomy verified in GRIN's visible Nomenclature/Common Names.
# Vaccinium as a whole is NOT a blueberry crop assignment; hybrids stay unresolved.
GRIN_BLUEBERRY_TAXA = {
    "Vaccinium corymbosum L.": ("Highbush blueberry", "41002"),
    "Vaccinium virgatum Aiton": ("Rabbit-eye blueberry", "41068"),
    "Vaccinium angustifolium Aiton": ("Lowbush blueberry", "40981"),
    "Vaccinium darrowii Camp": ("Darrow's blueberry", "41007"),
}
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


def analyze_grin_values(values, *, workbook_path: Path, checked_on: str, reported_accessions: int):
    """Reduce a native XLSX matrix imported read-only by Artifact Tool.

    Only source-classified Cultivar records supply names. Four independently
    checked blueberry species are comparable; generic hybrids remain crop
    questions. Other taxa/material are accounted for without importing names.
    Narrative, collecting locations, received dates and source dates are omitted.
    """
    date.fromisoformat(checked_on)
    headers = [None, "ACCESSION", "PLANT NAME", "TAXONOMY", "ORIGIN", "GENEBANK", "AVAILABILITY",
               "RECEIVED", "SOURCE TYPE", "SOURCE DATE", "COLLECTION SITE", "COORDINATES", "ELEVATION",
               "HABITAT", "IMPROVEMENT LEVEL", "NARRATIVE", None]
    if not isinstance(values, list) or len(values) < 3 or values[1] != headers:
        raise ValueError("Expected the native GRIN accession export header")
    if type(reported_accessions) is not int or reported_accessions < 1 or len(values) - 2 != reported_accessions:
        raise ValueError("GRIN export does not reconcile to the public accession count")
    accessions, labels, levels, dispositions, excluded_taxa = set(), defaultdict(list), Counter(), Counter(), Counter()
    observed_genera = Counter()
    cultivar_names = set()
    for row in values[2:]:
        if not isinstance(row, list) or len(row) != len(headers):
            raise ValueError("GRIN export contains an incomplete row")
        accession, name, taxon, bank, level = (row[index] for index in (1, 2, 3, 5, 14))
        if not isinstance(accession, str) or not accession.strip() or accession.strip() in accessions:
            raise ValueError("GRIN export needs unique accession identifiers")
        if not isinstance(taxon, str) or not taxon.strip():
            raise ValueError("GRIN export needs literal taxonomy")
        # The native 'any part or synonym' query also returns other genera.
        # Query membership alone cannot establish the crop or even the genus.
        observed_genera[taxon.strip().split(" ", 1)[0]] += 1
        if level is not None and not isinstance(level, str):
            raise ValueError("GRIN improvement level must remain a source label")
        accessions.add(accession.strip())
        levels[level or "Unknown"] += 1
        if level != "Cultivar":
            dispositions["other_material"] += 1
            continue
        if not isinstance(name, str) or not name.strip() or (bank is not None and not isinstance(bank, str)):
            raise ValueError("GRIN Cultivar record lacks its plant name or genebank")
        cultivar_names.add(name.strip())
        normalized_taxon = taxon.strip()
        if normalized_taxon in GRIN_BLUEBERRY_TAXA:
            scope = "blueberry"
        elif normalized_taxon == "Vaccinium hybr.":
            scope = "crop_unresolved"
        else:
            dispositions["other_taxon_cultivar"] += 1
            excluded_taxa[normalized_taxon] += 1
            continue
        dispositions[scope] += 1
        labels[(scope, name.strip())].append({"unique_name": accession.strip(), "accession": accession.strip(),
            "organism": taxon, "institutional_name": bank or "", "datasets": [], "other_cultivar_labels": [],
            "improvement_level": level})
    entries = [{"genus": "Vaccinium", "berry_scope": scope, "name": name, "export_rows": len(refs),
                "references": sorted(refs, key=lambda ref: ref["unique_name"])}
               for (scope, name), refs in sorted(labels.items(), key=lambda item: (item[0][1].casefold(), item[0][0]))]
    return {"kind": "unreviewed_external_germplasm_comparison", "id": "grin-vaccinium-cultivars",
        "source_title": "USDA National Plant Germplasm System (GRIN)", "source_url": GRIN_URL, "checked_on": checked_on,
        "query": {"scientific_name": "Vaccinium", "include_historical": True, "row_limit": 10000,
                  "match_mode": "Any part of scientific name or synonyms", "improvement_level_filter": None},
        "input_sha256": hashlib.sha256(workbook_path.read_bytes()).hexdigest(),
        "values_sha256": hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "taxonomy_scope": {taxon: {"common_name": common, "url": "https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=" + tid}
                           for taxon, (common, tid) in GRIN_BLUEBERRY_TAXA.items()},
        "improvement_levels": dict(sorted(levels.items())), "observed_genera": dict(sorted(observed_genera.items())),
        "dispositions": dict(dispositions),
        "other_taxon_cultivars": dict(sorted(excluded_taxa.items())),
        "totals": {"export_rows": len(values) - 2, "reported_stocks": reported_accessions,
                   "stock_organism_keys": len(accessions), "distinct_cultivar_labels": len({row["name"] for row in entries}),
                   "genus_label_keys": len(entries), "source_cultivar_records": levels["Cultivar"],
                   "source_distinct_cultivar_labels": len(cultivar_names),
                   "compared_records": dispositions["blueberry"], "unresolved_crop_records": dispositions["crop_unresolved"],
                   "vaccinium_records": observed_genera["Vaccinium"],
                   "other_genus_records": len(accessions) - observed_genera["Vaccinium"]},
        "entries": entries}


def _entry_key(row):
    return row["genus"], row.get("berry_scope", "genus"), row["name"]


def load_external_baselines(data_dir: Path):
    latest = {}
    for path in sorted((data_dir / "imports").glob("variety-external-baseline-*/comparison.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        is_grin = payload.get("id") == "grin-vaccinium-cultivars" and payload.get("source_url") == GRIN_URL
        is_gdr = payload.get("id") == "gdr-fragaria-rubus-accessions" and payload.get("source_url") == GDR_URL
        if payload.get("kind") != "unreviewed_external_germplasm_comparison" or not (is_grin or is_gdr):
            raise ValueError("Unknown external germplasm comparison")
        date.fromisoformat(payload["checked_on"])
        entries = payload.get("entries")
        if not isinstance(entries, list) or any(not isinstance(row, dict) or row.get("genus") not in ( {"Vaccinium"} if is_grin else GENUS_BERRIES)
                or not isinstance(row.get("name"), str) or not row["name"].strip()
                or type(row.get("export_rows")) is not int or row["export_rows"] < 1
                or not isinstance(row.get("references"), list) or not row["references"] for row in entries):
            raise ValueError("External comparison needs literal names, genera and references")
        for row in entries:
            if is_grin and row.get("berry_scope") not in {"blueberry", "crop_unresolved"}:
                raise ValueError("GRIN comparison needs explicit crop scope")
            for ref in row["references"]:
                if not isinstance(ref, dict) or any(not isinstance(ref.get(key), str)
                        for key in ("unique_name", "organism", "accession", "institutional_name")) or not ref["unique_name"]:
                    raise ValueError("External comparison needs literal collection identifiers")
                if ref["organism"].split(' ', 1)[0] != row["genus"] or any(
                        not isinstance(ref.get(key), list) or any(not isinstance(item, str) for item in ref[key])
                        for key in ("datasets", "other_cultivar_labels")):
                    raise ValueError("External comparison has inconsistent reference scope")
                if is_grin and (ref.get("improvement_level") != "Cultivar" or (ref["organism"].strip() not in
                        (GRIN_BLUEBERRY_TAXA if row["berry_scope"] == "blueberry" else {"Vaccinium hybr."}))):
                    raise ValueError("GRIN reference contradicts its source classification or crop scope")
        if len({_entry_key(row) for row in entries}) != len(entries):
            raise ValueError("External comparison repeats a crop-group/name key")
        if len(entries) != payload["totals"]["genus_label_keys"]:
            raise ValueError("External comparison label accounting is inconsistent")
        if sum(row['export_rows'] for row in entries) > payload['totals']['export_rows']:
            raise ValueError("External comparison exceeds its exported row population")
        if is_grin:
            dispositions, totals = payload["dispositions"], payload["totals"]
            refs = [ref for row in entries for ref in row["references"]]
            if (any(row["export_rows"] != len(row["references"]) for row in entries)
                    or len({ref["unique_name"] for ref in refs}) != len(refs)
                    or sum(dispositions.values()) != totals["export_rows"]
                    or sum(payload["improvement_levels"].values()) != totals["export_rows"]
                    or sum(payload["observed_genera"].values()) != totals["export_rows"]
                    or totals["vaccinium_records"] != payload["observed_genera"].get("Vaccinium", 0)
                    or totals["other_genus_records"] + totals["vaccinium_records"] != totals["export_rows"]
                    or totals["reported_stocks"] != totals["stock_organism_keys"]
                    or totals["reported_stocks"] != totals["export_rows"]
                    or totals["source_cultivar_records"] != payload["improvement_levels"].get("Cultivar", 0)
                    or totals["compared_records"] != dispositions.get("blueberry", 0)
                    or totals["unresolved_crop_records"] != dispositions.get("crop_unresolved", 0)
                    or sum(payload["other_taxon_cultivars"].values()) != dispositions.get("other_taxon_cultivar", 0)
                    or totals["source_cultivar_records"] != sum(dispositions.get(key, 0) for key in
                                                              ("blueberry", "crop_unresolved", "other_taxon_cultivar"))
                    or any(sum(row["export_rows"] for row in entries if row["berry_scope"] == scope) != dispositions.get(scope, 0)
                           for scope in ("blueberry", "crop_unresolved"))
                    or payload["taxonomy_scope"] != {taxon: {"common_name": common,
                        "url": "https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=" + tid}
                        for taxon, (common, tid) in GRIN_BLUEBERRY_TAXA.items()}):
                raise ValueError("GRIN comparison population accounting or taxonomy scope is inconsistent")
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
        berries = (["berry-blueberry"] if entry.get("berry_scope") == "blueberry" else []) if entry["genus"] == "Vaccinium" else GENUS_BERRIES[entry["genus"]]
        resolution = resolve_identity({"candidate_name": entry["name"], "berry_ids": berries}, varieties) if berries else {"matches": []}
        catalog = {match["variety_id"]: match["variety_name"] for match in resolution["matches"]
                   if match["reason"] == "exact_identity_string"}
        found = {candidate["id"]: candidate for candidate in candidate_index.get(fold_identity(entry["name"]), [])
                 if candidate.get("berry_id") in berries}
        status = "crop_scope_needed" if not berries else "catalog_name_found" if catalog else "candidate_name_found" if found else "no_name_match"
        entries.append({**entry, "source_title": baseline["source_title"], "baseline_id": baseline["id"],
            "input_sha256": baseline["input_sha256"], "status": status,
            "catalog_matches": [{"id": key, "name": value, "href": "/entities/variety/" + key} for key, value in sorted(catalog.items())],
            "candidate_matches": [{"id": key, "name": candidate.get("candidate_name", key), "status": candidate.get("status", "unreviewed"),
                "human_gated": bool(candidate.get("human_gated")),
                "href": "/varieties/candidates?" + urlencode({"q": entry["name"]}) + "#" + key}
                for key, candidate in sorted(found.items())]})
    return {**baseline, "entries": entries, "comparison_counts": dict(Counter(row["status"] for row in entries))}


def prepare_blueberry_identity_lead(*, baselines, baseline_id, name, input_sha256, varieties, candidates):
    """One explicit queue handoff; no identity, source or catalog approval.

    Existing names/decisions take precedence. Never infer a crop from generic
    hybrids or overwrite a candidate during replay of a newer source snapshot.
    """
    from app.services.variety_universe.registry_import import build_candidate
    baseline = next((row for row in baselines if row["id"] == baseline_id), None)
    if baseline is None or baseline["id"] != "grin-vaccinium-cultivars" or baseline["input_sha256"] != input_sha256:
        raise ValueError("The saved comparison changed. Refresh it before adding a lead.")
    entry = next((row for row in baseline["entries"] if row["name"] == name and row.get("berry_scope") == "blueberry"), None)
    if entry is None:
        raise ValueError("Only a source-classified name in checked blueberry species can enter this handoff.")
    compared = compare_baseline({**baseline, "entries": [entry]}, varieties=varieties, candidates=candidates)["entries"][0]
    if compared["catalog_matches"]:
        matches = compared["catalog_matches"]
        return {"candidate": None, "href": matches[0]["href"] if len(matches) == 1 else "/varieties/coverage?" + urlencode(
            {"external_q": name, "external_genus": "Vaccinium", "external_status": ""}) + "#external-coverage"}
    if compared["candidate_matches"]:
        matches = compared["candidate_matches"]
        return {"candidate": None, "href": matches[0]["href"] if len(matches) == 1 else "/varieties/candidates?" + urlencode({"q": name, "berry": "berry-blueberry"})}
    seed = json.dumps([baseline_id, "blueberry", name], ensure_ascii=False, separators=(",", ":"))
    candidate_id = "vcand-" + hashlib.sha256(seed.encode()).hexdigest()[:12]
    retained = next((row for row in candidates if row.get("id") == candidate_id), None)
    href = "/varieties/candidates?" + urlencode({"q": (retained or {}).get("candidate_name") or name}) + "#" + candidate_id
    if retained:
        return {"candidate": None, "href": href}
    candidate = build_candidate({"id": candidate_id, "candidate_name": name, "berry_id": "berry-blueberry",
        "source_url": baseline["source_url"], "source_label": baseline["source_title"],
        "source_type": "public_germplasm_collection", "source_tier": "weak_noncanonical_lead"},
        varieties=varieties)
    candidate["external_collection"] = {"baseline_id": baseline_id, "checked_on": baseline["checked_on"],
        "input_sha256": input_sha256, "source_name": name, "references": entry["references"],
        "limitations": "Collection label only; release status, aliases, breeder, traits, rights and growing regions need source review."}
    return {"candidate": candidate, "href": href}


def external_coverage_view(*, baselines, varieties, candidates, filters):
    reports = [compare_baseline(row, varieties=varieties, candidates=candidates) for row in baselines]
    entries = [row for report in reports for row in report["entries"]]
    q = str(filters.get("external_q", "")).strip()[:200]
    genus = filters.get("external_genus", "")
    genus = genus if genus in EXTERNAL_GENERA else ""
    status = filters.get("external_status", "no_name_match")
    status = status if status in {"", "no_name_match", "catalog_name_found", "candidate_name_found", "crop_scope_needed"} else "no_name_match"
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
    return {"reports": [report for report in reports if not genus or any(row["genus"] == genus for row in report["entries"])],
        "counts": dict(Counter(row["status"] for row in entries)),
        "scope_counts": dict(Counter(row["status"] for row in entries if not genus or row["genus"] == genus)),
        "filters": {"q": q, "genus": genus, "status": status}, "entries": rows[(page-1)*50:page*50],
        "filtered_count": len(rows), "page": page, "pages": pages,
        "previous_href": href(page-1) if page > 1 else "", "next_href": href(page+1) if page < pages else ""}
