#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path("/workspace")
OUT_DIR = ROOT / "docs/reviews/berry-backlog-human-approval"
TODAY = date.today().isoformat()

REVIEW_COLUMNS = [
    ("record_id", 46),
    ("queue_type", 28),
    ("current_status", 40),
    ("title", 55),
    ("publisher", 24),
    ("source_url", 48),
    ("published_date", 14),
    ("captured_date", 14),
    ("date_basis", 28),
    ("berries", 28),
    ("companies", 28),
    ("geographies", 24),
    ("content_state", 34),
    ("short_summary", 60),
    ("relevance_reason", 42),
    ("quality_flags", 44),
    ("duplicate_of", 46),
    ("proposed_batch", 30),
    ("recommended_action", 24),
    ("recommendation_reason", 55),
    ("final_decision", 18),
    ("reviewer_notes", 36),
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")
WARN_FILL = PatternFill("solid", fgColor="FFF2CC")
REJECT_FILL = PatternFill("solid", fgColor="FCE4EC")
KEEP_FILL = PatternFill("solid", fgColor="E8F5E9")
HOLD_FILL = PatternFill("solid", fgColor="FFF8E1")

BERRY_LABELS = {
    "berry-blueberry": "blueberry",
    "berry-strawberry": "strawberry",
    "berry-raspberry": "raspberry",
    "berry-blackberry": "blackberry",
}

BATCH_META = {
    "B01_genetics_ip_varieties": (
        "Genetics, varieties, breeding, patents/PBR, licensing — clear commercial keep.",
        "validate",
    ),
    "B02_trade_export_supply": (
        "Export/import, seasons, volumes, prices, market outlook — clear commercial keep.",
        "validate",
    ),
    "B03_company_maa_investment": (
        "Company expansion, M&A, investment, partnerships — clear commercial keep.",
        "validate",
    ),
    "B04_production_agronomy": (
        "Acreage, harvest, greenhouse/tunnel, labor, grower systems — clear commercial keep.",
        "validate",
    ),
    "B05_litigation_regulation": (
        "Litigation, IP disputes, regulation, certification, MRLs — clear commercial keep.",
        "validate",
    ),
    "B06_trade_press_general": (
        "Other clear commercial soft-berry trade-press items — keep.",
        "validate",
    ),
    "B07_consumer_fluff_reject": (
        "Recipes, consumer health fluff, local interest — reject as sources.",
        "reject_as_source",
    ),
    "B08_offtopic_produce_reject": (
        "Other produce / non-target / no commercial soft-berry signal — reject.",
        "reject_as_source",
    ),
    "B09_false_match_reject": (
        "False matches (electronics, entertainment brands, etc.) — reject.",
        "reject_as_source",
    ),
    "B10_content_recovery": (
        "Likely relevant but body missing/thin — recover content; do not reject solely for that.",
        "needs_content_recovery",
    ),
    "B11_likely_duplicates": (
        "Near-duplicate titles/syndication — keep primary, hold others for human check.",
        "hold",
    ),
    "B12_borderline_hold": (
        "Borderline / insufficient snippet — human judgment required.",
        "hold",
    ),
}

COMMERCIAL_RE = re.compile(
    r"\b("
    r"variet(?:y|ies)|cultivar|breed(?:ing|er)?|genomic|genetics?|germplasm|"
    r"patent|PBR|plant\s*breed|licens|royalt|"
    r"export|import|shipment|tariff|trade|customs|quota|"
    r"acqui(?:re|sition)|merger|joint\s*venture|\bJV\b|invest(?:ment|or)?|"
    r"private\s*equity|funding|IPO|"
    r"lawsuit|litigation|infring|court|verdict|settlement|dispute|"
    r"regulat|FDA|USDA|EFSA|MRL|recall|quarantine|certif|"
    r"price|market|demand|supply|forecast|outlook|wholesale|retail(?:er)?|"
    r"harvest|yield|acreage|hectare|greenhouse|tunnel|labor|labour|grower|"
    r"nursery|packer|shipper|marketer|producer|"
    r"Driscoll|Planasa|Fall\s*Creek|Hortifrut|Agrovision|Wish\s*Farms|"
    r"Naturipe|Costa|BerryWorld|Sanlucar|Giddings|Ozblu|Oz\s*Blu|"
    r"Bloom\s*Fresh|Plant\s*Sciences|California\s*Berry"
    r")\b",
    re.I,
)
FALSE_MATCH_RULES = [
    (re.compile(r"raspberry\s*pi\b", re.I), "false_match_raspberry_pi"),
    (
        re.compile(
            r"\bblackberry\b.{0,60}\b(phone|smartphone|device|electronics|bbm|qnx|rim)\b",
            re.I,
        ),
        "false_match_blackberry_electronics",
    ),
    (
        re.compile(r"strawberry\s*shortcake|wildbrain.*strawberry", re.I),
        "false_match_strawberry_shortcake",
    ),
]
CONSUMER_RE = re.compile(
    r"\b(recipe|smoothie|dessert|cake|muffin|pancake|yogurt|breakfast bowl|"
    r"cookie\s*recipe|how to make|taste test)\b",
    re.I,
)
HEALTH_FLUFF_RE = re.compile(
    r"\b(antioxidant|superfood|good for you|heart[- ]healthy|cognitive|"
    r"brain health|burn fat|gut health|inflammation|health benefit|"
    r"healthy snack|helps older adults)\b",
    re.I,
)
OTHER_PRODUCE_RE = re.compile(
    r"\b(apples?\b|pears?\b|avocado|banana|citrus|tomatoes?\b|potato|"
    r"goji|serviceberr|juneberr|pitless cherry|nadorcott|mandarin)\b",
    re.I,
)
TARGET_BERRY_RE = re.compile(
    r"\b(strawberr|blueberr|raspberr|blackberr|caneberr)\w*\b", re.I
)
ACCESS_WALL_RE = re.compile(
    r"\b(enable javascript|cookie (policy|settings|consent)|accept cookies|"
    r"captcha|access denied|just a moment|subscribe to continue|"
    r"sign in to read|bot detection)\b",
    re.I,
)
LOCAL_FLUFF_RE = re.compile(
    r"\b(u-?pick|pick[- ]your[- ]own|farmers?\s*market|fun day|"
    r"buckets of local)\b",
    re.I,
)


def load_name_maps():
    companies = {}
    geos = {}
    for folder, dest in (
        ("companies", companies),
        ("geographies", geos),
        ("retailers", companies),
        ("brands", companies),
        ("breeding_programs", companies),
    ):
        path = ROOT / "data" / "entities" / folder
        if not path.is_dir():
            continue
        for p in path.glob("*.json"):
            row = json.loads(p.read_text(encoding="utf-8"))
            dest[row["id"]] = row.get("name") or row.get("label") or row["id"]
    return companies, geos


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(
        r"\s+[-–|]\s+(freshplaza|fruitnet|hortidaily|eastfruit|the packer|"
        r"andnowuknow|freshfruitportal|growing produce|perishable news|"
        r"produce report|morocco world news|capital press|fruitgrowersnews).*$",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def domain_of(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower()
    except Exception:
        return ""


def berry_labels(record: dict) -> str:
    return ", ".join(BERRY_LABELS.get(i, i) for i in (record.get("berry_ids") or []))


def resolve_names(ids, lookup):
    return ", ".join(lookup.get(i, i) for i in (ids or []))


def content_state(record: dict) -> str:
    summary = (record.get("summary") or "").strip()
    flags = []
    if domain_of(record.get("source_url") or "").endswith("news.google.com"):
        flags.append("google_news_wrapper_url")
    if not summary:
        flags.append("missing_summary")
    else:
        if summary.endswith("…") or summary.endswith("..."):
            flags.append("truncated_snippet")
        if len(summary) < 90:
            flags.append("thin_snippet")
    if ACCESS_WALL_RE.search(summary):
        flags.append("access_wall_language")
    return "|".join(flags) if flags else "snippet_present"


def classify(record: dict) -> dict:
    title = record.get("title") or ""
    summary = record.get("summary") or ""
    text = f"{title}\n{summary}"
    flags = []

    for cre, flag in FALSE_MATCH_RULES:
        if cre.search(text):
            flags.append(flag)

    has_target = bool(TARGET_BERRY_RE.search(text) or record.get("berry_ids"))
    has_berry_sector = bool(re.search(r"\bberr(?:y|ies)\b", text, re.I))
    commercial = bool(COMMERCIAL_RE.search(text))
    consumer = bool(CONSUMER_RE.search(text))
    health = bool(HEALTH_FLUFF_RE.search(text))
    other = bool(OTHER_PRODUCE_RE.search(text))
    local = bool(LOCAL_FLUFF_RE.search(text))
    wall = bool(ACCESS_WALL_RE.search(text))
    state = content_state(record)
    thin = ("thin_snippet" in state) or ("missing_summary" in state) or wall

    if wall:
        flags.append("possible_access_wall")
    if consumer:
        flags.append("consumer_recipe_or_fluff")
    if health and not commercial:
        flags.append("consumer_health_fluff")
    if other and not (has_target and commercial):
        flags.append("other_produce_or_non_target")
    if local and not commercial:
        flags.append("local_consumer_interest")
    if not has_target:
        flags.append("no_target_berry_signal")

    flags.append("recommendation_from_title_and_snippet_only")
    if domain_of(record.get("source_url") or "").endswith("news.google.com"):
        flags.append("canonical_url_not_resolved")

    pub = record.get("published_date") or ""
    cap = record.get("captured_date") or ""
    if pub and cap and pub == cap:
        flags.append("published_date_equals_captured_date")
        date_basis = "uncertain_equals_capture"
    elif pub:
        date_basis = "feed_or_publisher_date"
    else:
        date_basis = "missing_published_date_do_not_use_capture"
        flags.append("missing_published_date")

    action = "hold"
    batch = "B12_borderline_hold"
    relevance = ""
    reason = ""

    if any(f.startswith("false_match_") for f in flags):
        action = "reject_as_source"
        batch = "B09_false_match_reject"
        relevance = "False semantic match; not commercial berry intelligence."
        reason = (
            "Title/snippet indicates a non-berry false match "
            f"({', '.join(f for f in flags if f.startswith('false_match_'))}). "
            "Recommend reject; map to legacy purge only after explicit human confirmation."
        )
    elif consumer and not commercial:
        action = "reject_as_source"
        batch = "B07_consumer_fluff_reject"
        relevance = "Consumer/recipe content without commercial berry signal."
        reason = "Consumer fluff/recipe pattern without company/trade/genetics signal."
    elif health and not commercial:
        action = "reject_as_source"
        batch = "B07_consumer_fluff_reject"
        relevance = "Consumer health coverage; not commercial berry intelligence."
        reason = "Health/superfood framing without commercial operators, genetics, or trade facts."
    elif other and not (has_target and commercial):
        action = "reject_as_source"
        batch = "B08_offtopic_produce_reject"
        relevance = "Primarily other produce or non-target berry."
        reason = "Other-produce or non-target berry dominates; weak commercial soft-berry relevance."
    elif local and not commercial:
        action = "reject_as_source"
        batch = "B07_consumer_fluff_reject"
        relevance = "Local consumer/seasonal interest piece."
        reason = "Local u-pick / consumer seasonal piece without commercial depth."
    elif commercial and (has_target or has_berry_sector):
        if re.search(r"\b(variet|cultivar|breed|genomic|genetic|patent|PBR|germplasm|licens)\b", text, re.I):
            batch = "B01_genetics_ip_varieties"
            relevance = "Genetics / variety / IP / breeding commercial signal."
        elif re.search(r"\b(lawsuit|litigation|infring|court|verdict|settlement|dispute)\b", text, re.I):
            batch = "B05_litigation_regulation"
            relevance = "Litigation / rights dispute with berry commercial impact."
        elif re.search(r"\b(regulat|FDA|USDA|EFSA|MRL|recall|quarantine|certif)\b", text, re.I):
            batch = "B05_litigation_regulation"
            relevance = "Regulatory / trade-compliance signal for berries."
        elif re.search(r"\b(acqui|merger|joint venture|\bJV\b|invest|funding|private equity)\b", text, re.I):
            batch = "B03_company_maa_investment"
            relevance = "Company move / investment / M&A in berry value chain."
        elif re.search(r"\b(export|import|shipment|tariff|trade|customs|season|volume|price|market|forecast|outlook)\b", text, re.I):
            batch = "B02_trade_export_supply"
            relevance = "Trade / market / supply-season commercial reporting."
        elif re.search(r"\b(harvest|yield|acreage|hectare|greenhouse|tunnel|labor|grower|nursery)\b", text, re.I):
            batch = "B04_production_agronomy"
            relevance = "Production / acreage / grower-system commercial reporting."
        else:
            batch = "B06_trade_press_general"
            relevance = "Commercial berry trade-press item."

        if thin:
            action = "needs_content_recovery"
            batch = "B10_content_recovery"
            flags.append("legitimate_topic_missing_body")
            reason = (
                "Commercial soft-berry signal present, but only a thin/walled snippet "
                "is stored. Content recovery — not automatic rejection. Does not approve "
                "claims or authorize extraction."
            )
        else:
            action = "validate"
            reason = (
                "Commercially relevant soft-berry reporting on title+snippet. "
                "Maps to legacy validate (confirm keep). Does NOT create facts, "
                "approve claims, or authorize extraction."
            )
            if "truncated_snippet" in state:
                flags.append("body_recovery_still_useful")
    elif has_target:
        action = "hold"
        batch = "B12_borderline_hold"
        relevance = "Target berry mentioned; commercial value unclear from snippet."
        reason = "Headline/snippet insufficient to judge commercial value confidently."
    else:
        action = "reject_as_source"
        batch = "B08_offtopic_produce_reject"
        relevance = "No clear commercial soft-berry intelligence value."
        reason = "No clear strawberry/blueberry/raspberry/blackberry commercial signal."

    return {
        "action": action,
        "batch": batch,
        "relevance": relevance,
        "reason": reason,
        "flags": flags,
        "date_basis": date_basis,
    }


def find_duplicates(records):
    by_norm = defaultdict(list)
    for r in records:
        key = normalize_title(r.get("title") or "")
        if len(key) < 20:
            continue
        by_norm[key].append(r)
    dup_of = {}
    for group in by_norm.values():
        if len(group) < 2:
            continue
        group_sorted = sorted(
            group,
            key=lambda r: (
                r.get("published_date") or "9999",
                r.get("captured_date") or "9999",
                r.get("id") or "",
            ),
        )
        primary = group_sorted[0]["id"]
        for other in group_sorted[1:]:
            dup_of[other["id"]] = primary
    return dup_of


def build():
    companies, geos = load_name_maps()
    records = []
    for p in sorted((ROOT / "data" / "evidence").glob("*.json")):
        row = json.loads(p.read_text(encoding="utf-8"))
        if row.get("auto_captured"):
            records.append(row)

    dup_of = find_duplicates(records)
    review_rows = []

    for record in records:
        verdict = classify(record)
        rid = record["id"]
        flags = list(verdict["flags"])
        batch = verdict["batch"]
        action = verdict["action"]
        reason = verdict["reason"]

        if rid in dup_of:
            flags.append("likely_duplicate_or_syndication")
            if action in {"validate", "needs_content_recovery"}:
                batch = "B11_likely_duplicates"
                action = "hold"
                reason = (
                    f"Likely duplicate/syndication of {dup_of[rid]}. "
                    "Distinguish syndication from independent corroboration before "
                    "validating both. Primary is the earlier/canonical row."
                )

        review_rows.append(
            {
                "record_id": rid,
                "queue_type": "legacy_unvalidated_evidence",
                "current_status": "published; legacy_validated=true; commercial_review_pending",
                "title": record.get("title") or "",
                "publisher": record.get("source_name") or "",
                "source_url": record.get("source_url") or "",
                "published_date": record.get("published_date") or "",
                "captured_date": record.get("captured_date") or "",
                "date_basis": verdict["date_basis"],
                "berries": berry_labels(record),
                "companies": resolve_names(record.get("entity_ids"), companies),
                "geographies": resolve_names(record.get("geography_ids"), geos),
                "content_state": content_state(record),
                "short_summary": (record.get("summary") or "").strip(),
                "relevance_reason": verdict["relevance"],
                "quality_flags": "|".join(flags),
                "duplicate_of": dup_of.get(rid, ""),
                "proposed_batch": batch,
                "recommended_action": action,
                "recommendation_reason": reason,
                "final_decision": "",
                "reviewer_notes": "",
                "prior_human_decision": "validate",
                "origin_domain": record.get("origin_domain") or "",
                "tags": ", ".join(record.get("tags") or []),
            }
        )

    batch_counts = Counter(r["proposed_batch"] for r in review_rows)
    action_counts = Counter(r["recommended_action"] for r in review_rows)

    exceptions = []
    for r in review_rows:
        ex_reasons = []
        if any(x in r["content_state"] for x in ("missing_summary", "thin_snippet", "access_wall_language")):
            if r["recommended_action"] in {"validate", "needs_content_recovery", "hold"}:
                ex_reasons.append("thin_or_missing_content")
        if r["duplicate_of"]:
            ex_reasons.append("likely_duplicate")
        if "false_match_" in r["quality_flags"]:
            ex_reasons.append("false_match")
        if "published_date_equals_captured_date" in r["quality_flags"] or r["date_basis"].startswith("uncertain"):
            ex_reasons.append("uncertain_date")
        if "no_target_berry_signal" in r["quality_flags"] and r["recommended_action"] != "reject_as_source":
            ex_reasons.append("uncertain_identity")
        if "canonical_url_not_resolved" in r["quality_flags"] and r["recommended_action"] == "needs_content_recovery":
            ex_reasons.append("unresolved_canonical_url")
        if ex_reasons:
            exceptions.append(
                {
                    "exception_id": f"EX-{r['record_id']}",
                    "record_id": r["record_id"],
                    "severity": "|".join(ex_reasons),
                    "proposed_batch": r["proposed_batch"],
                    "recommended_action": r["recommended_action"],
                    "detail": r["recommendation_reason"],
                    "title": r["title"],
                }
            )

    record_keys = [name for name, _ in REVIEW_COLUMNS] + [
        "prior_human_decision",
        "origin_domain",
        "tags",
    ]

    dataset = {
        "dataset_id": "checked-in-auto-captured-evidence-master",
        "inspected_at": TODAY,
        "git_branch": "cursor/berry-backlog-review-workbook-d16f",
        "repo": "github.com/samsonFive/berry-intelligence-os",
        "scope_note": (
            "Reviewed all checked-in data/evidence records with auto_captured=true "
            f"({len(records)} rows). These carry validated=true from the "
            "2026-08-06 validate/purge spreadsheet, but priority.* still says "
            "'not yet reviewed' — this workbook is the commercial batch review. "
            "Pending publication, source-fidelity, and atomic-claim queues were "
            "not present in this checkout (no inbox/) and are left empty/distinct."
        ),
        "queues": {
            "legacy_unvalidated_evidence": {
                "present": True,
                "reviewed_count": len(records),
                "note": (
                    "Checked-in auto_captured corpus. Legacy validate already applied; "
                    "commercial review pending. Queue kept on validate/reject semantics."
                ),
            },
            "pending_publication": {"present": False, "reviewed_count": 0},
            "source_fidelity_recovery": {"present": False, "reviewed_count": 0},
            "atomic_evidence_claim": {"present": False, "reviewed_count": 0},
        },
        "action_counts": dict(action_counts),
        "batch_counts": dict(batch_counts),
        "exception_count": len(exceptions),
        "decision_mapping": {
            "validate": "scripts/apply_review_decisions.py decision=validate. Confirms keep as Evidence/source. Does not create facts or approve claims.",
            "reject_as_source": "Recommendation only. Human may later map to legacy purge after explicit confirmation. No executable purge/purge+block emitted.",
            "needs_content_recovery": "Not a legacy validate/purge. Route to content recovery/source-fidelity; do not reject solely for missing body; do not treat as claim approval.",
            "hold": "Leave untouched until human decides.",
        },
        "records": [{k: r[k] for k in record_keys} for r in review_rows],
        "batches": [
            {
                "proposed_batch": key,
                "row_count": batch_counts.get(key, 0),
                "review_rationale": BATCH_META[key][0],
                "suggested_action": BATCH_META[key][1],
            }
            for key in BATCH_META
            if batch_counts.get(key, 0)
        ],
        "exceptions": exceptions,
        "limitations": [
            "Recommendations use title + stored snippet only; Google News wrapper URLs were not resolved en masse.",
            "Public pages were not opened for every row; material uncertainty is held or sent to recovery.",
            "prior_human_decision=validate preserved from legacy spreadsheet; final_decision left blank.",
            "Company/geography columns only show linked entity ids present on the record (often empty).",
            "Pending publication / source-fidelity / atomic queues absent here — not reviewed.",
        ],
    }

    wb = Workbook()
    ws_i = wb.active
    ws_i.title = "Instructions"
    instructions = [
        ("Berry Intelligence OS — Human Approval Workbook", ""),
        ("Generated", TODAY),
        ("Dataset", dataset["dataset_id"]),
        ("Rows reviewed", str(len(review_rows))),
        ("", ""),
        ("PURPOSE", ""),
        ("Batch-approve clear article groups while Astra repairs the app. Fill final_decision only. Leave blank rows untouched on apply.", ""),
        ("", ""),
        ("HARD BOUNDARIES", ""),
        ("1. Queues stay distinct — source approval ≠ claim approval ≠ fact creation ≠ extraction authorization.", ""),
        ("2. Do not put executable purge / purge+block in final_decision unless you intentionally want deletion.", ""),
        ("3. Preserve prior human decisions; this sheet leaves final_decision blank for you.", ""),
        ("4. Preserve record IDs and source URLs exactly.", ""),
        ("5. Never substitute captured_date for published_date.", ""),
        ("6. Missing body + legitimate topic => content recovery, not automatic reject.", ""),
        ("7. Do not blanket-approve merely because the publisher is reputable.", ""),
        ("", ""),
        ("QUEUE IN THIS FILE", ""),
        ("legacy_unvalidated_evidence", "Checked-in auto_captured rows (legacy validate already applied; commercial review pending)."),
        ("pending_publication", "Not present in this checkout."),
        ("source_fidelity_recovery", "Not present in this checkout."),
        ("atomic_evidence_claim", "Not present in this checkout."),
        ("", ""),
        ("RECOMMENDED_ACTION MEANINGS", ""),
        ("validate", "Confirm keep as Evidence/source. Maps to apply_review_decisions.py validate."),
        ("reject_as_source", "Recommend drop as intelligence source. NOT auto-purge; human may later confirm purge."),
        ("needs_content_recovery", "Likely relevant; recover body/fidelity before trusting content. Not claim approval."),
        ("hold", "Needs human judgment; leave untouched."),
        ("", ""),
        ("FINAL_DECISION VALUES TO ENTER", ""),
        ("validate | reject_as_source | needs_content_recovery | hold | (blank=untouched)", ""),
        ("If you truly want deletion after reject_as_source, tell the primary agent explicitly to map to purge.", ""),
        ("", ""),
        ("HOW PRIMARY AGENT SHOULD APPLY", ""),
        ("1. Apply only non-blank final_decision rows.", ""),
        ("2. Honor queue_type; no cross-queue side effects.", ""),
        ("3. validate => legacy validate only.", ""),
        ("4. reject_as_source => do not purge unless human explicitly confirms purge mapping.", ""),
        ("5. needs_content_recovery => fidelity/recovery workflow only.", ""),
        ("6. Never create facts/claims/relationships from source approval alone.", ""),
    ]
    ws_i["A1"] = "Item"
    ws_i["B1"] = "Detail"
    for cell in ws_i[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for i, (a, b) in enumerate(instructions, start=2):
        ws_i.cell(i, 1, a)
        ws_i.cell(i, 2, b)
        if a in {
            "PURPOSE",
            "HARD BOUNDARIES",
            "QUEUE IN THIS FILE",
            "RECOMMENDED_ACTION MEANINGS",
            "FINAL_DECISION VALUES TO ENTER",
            "HOW PRIMARY AGENT SHOULD APPLY",
        }:
            ws_i.cell(i, 1).font = Font(bold=True, color="1F4E79")
    ws_i.column_dimensions["A"].width = 44
    ws_i.column_dimensions["B"].width = 110
    ws_i.freeze_panes = "A2"

    ws_r = wb.create_sheet("Review")
    for idx, (name, width) in enumerate(REVIEW_COLUMNS, start=1):
        cell = ws_r.cell(1, idx, name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws_r.column_dimensions[get_column_letter(idx)].width = width
    ws_r.freeze_panes = "A2"
    ws_r.auto_filter.ref = f"A1:{get_column_letter(len(REVIEW_COLUMNS))}{len(review_rows) + 1}"

    fills = {
        "validate": KEEP_FILL,
        "reject_as_source": REJECT_FILL,
        "needs_content_recovery": WARN_FILL,
        "hold": HOLD_FILL,
    }
    for r in review_rows:
        ws_r.append([r[name] for name, _ in REVIEW_COLUMNS])
        fill = fills.get(r["recommended_action"])
        if fill:
            for col in range(1, len(REVIEW_COLUMNS) + 1):
                ws_r.cell(ws_r.max_row, col).fill = fill

    action_list = '"validate,reject_as_source,needs_content_recovery,hold"'
    dv = DataValidation(type="list", formula1=action_list, allow_blank=True)
    ws_r.add_data_validation(dv)
    dv.add(f"S2:S{len(review_rows) + 1}")
    dv.add(f"U2:U{len(review_rows) + 1}")

    ws_b = wb.create_sheet("Batches")
    b_headers = [
        ("proposed_batch", 32),
        ("row_count", 12),
        ("suggested_action", 24),
        ("review_rationale", 80),
        ("includes_exceptions", 18),
    ]
    for idx, (name, width) in enumerate(b_headers, start=1):
        cell = ws_b.cell(1, idx, name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        ws_b.column_dimensions[get_column_letter(idx)].width = width
    ws_b.freeze_panes = "A2"
    ex_by_batch = Counter(e["proposed_batch"] for e in exceptions)
    for key in BATCH_META:
        count = batch_counts.get(key, 0)
        if not count:
            continue
        ws_b.append(
            [
                key,
                count,
                BATCH_META[key][1],
                BATCH_META[key][0],
                "yes" if ex_by_batch.get(key) else "no",
            ]
        )

    ws_e = wb.create_sheet("Exceptions")
    e_headers = [
        ("exception_id", 42),
        ("record_id", 46),
        ("severity", 36),
        ("proposed_batch", 28),
        ("recommended_action", 22),
        ("title", 55),
        ("detail", 70),
    ]
    for idx, (name, width) in enumerate(e_headers, start=1):
        cell = ws_e.cell(1, idx, name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        ws_e.column_dimensions[get_column_letter(idx)].width = width
    ws_e.freeze_panes = "A2"
    ws_e.auto_filter.ref = f"A1:G{max(1, len(exceptions)) + 1}"
    for ex in exceptions:
        ws_e.append(
            [
                ex["exception_id"],
                ex["record_id"],
                ex["severity"],
                ex["proposed_batch"],
                ex["recommended_action"],
                ex["title"],
                ex["detail"],
            ]
        )
        for col in range(1, 8):
            ws_e.cell(ws_e.max_row, col).fill = WARN_FILL

    xlsx_path = OUT_DIR / "berry-backlog-review.xlsx"
    json_path = OUT_DIR / "berry-backlog-review.json"
    wb.save(xlsx_path)
    json_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "xlsx": str(xlsx_path),
        "json": str(json_path),
        "rows": len(review_rows),
        "actions": dict(action_counts),
        "batches": dict(batch_counts),
        "exceptions": len(exceptions),
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
