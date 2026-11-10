"""Source-backed spot checks and their research gaps for the berry landscape."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

CROPS = ("blueberry", "strawberry", "raspberry", "blackberry")
REGIONS = ("north-america", "latin-america", "europe", "mea", "asia-pacific")
ROLES = ("breeding", "rights", "propagation", "growing", "packing", "marketing", "distribution", "retail")
BASELINE = Path("imports/global-berry-landscape-2026-11-09/public-baseline.json")
FOLLOWUPS = BASELINE.with_name("public-followups.json")

_REGION_START = {
    "north-america": ("USDA and Canadian crop and operator sources", "https://www.nass.usda.gov/"),
    "latin-america": ("Mexico SENASICA and national grower/exporter registers", "https://www.gob.mx/senasica"),
    "europe": ("Freshfel Europe and national producer associations", "https://freshfel.org/"),
    "mea": ("Morocco Foodex and regional grower associations", "https://www.moroccofoodex.org.ma/en/"),
    "asia-pacific": ("Berries Australia and national grower associations", "https://berries.net.au/"),
}
_RIGHTS_START = {
    "north-america": ("USDA PVPO and USPTO plant patents; verify Canada separately", "https://www.ams.usda.gov/services/plant-variety-protection"),
    "latin-america": ("Mexico SNICS and the applicable national register", "https://www.gob.mx/snics"),
    "europe": ("CPVO Variety Finder and the applicable national register", "https://cpvo.europa.eu/en/applications-and-examinations/cpvo-variety-finder"),
    "mea": ("South Africa's plant breeders’ rights office; verify Morocco and other jurisdictions separately", "https://www.gov.za/services/plant-production/plant-breeders-rights"),
    "asia-pacific": ("IP Australia; verify Japan, China and other jurisdictions separately", "https://ipsearch.ipaustralia.gov.au/pbr/"),
}
_ROLE_SEARCH = {
    "breeding": "Find named breeding programs and confirm the crop and recent releases in their own catalogues.",
    "rights": "Match legal denominations and aliases to filing, grant and current holder in each relevant jurisdiction.",
    "propagation": "Find named nurseries and confirm current crop-specific propagation scope and licensors.",
    "growing": "Find named growers and dated crop acreage or shipments, including geography and production scope.",
    "packing": "Identify named facilities and verify the crop, location, operator and dated throughput.",
    "marketing": "Verify named marketer and grower programs, commercialization terms and served markets.",
    "distribution": "Verify named distributors, shipment lanes and whether arrangements are exclusive.",
    "retail": "Check for a named buyer program, supply window and listing evidence in the retailer’s own disclosures.",
}

_MILESTONE_TYPES = {
    "mbo-hortifrut-naturipe-blueberry-genetics-2026-07-30": ("partnership", "Collaboration announced"),
    "uc-davis-eurosemillas-strawberry-licensing-termination-2024-05-21": ("licensing", "Termination announced"),
    "cornell-crimson-beauty-crimson-blush-spring-2025-availability": ("commercial", "Available for spring 2025 planting"),
    "arkansas-sweet-ark-immaculate-release-2024-02-08": ("commercial", "Cultivar release announced"),
    "agroberries-berryworld-combination-announcement-2024-09-10": ("ownership", "Combination announced"),
    "pairwise-blackberry-aphis-rsr-24-087-01rsr": ("regulatory", "Regulatory determination"),
}


def _observed_milestones(baseline, followups, crop, region, role):
    observations = {row["id"]: row for row in baseline.get("observations", [])}
    events = list(followups.get("milestones", []))
    for candidate in baseline.get("event_candidates", []):
        key = candidate["event_key"]
        if key not in _MILESTONE_TYPES:
            continue
        kind, stage = _MILESTONE_TYPES[key]
        observation = observations.get(candidate.get("observation_id"), {})
        sources = candidate.get("sources") or [{
            "name": observation.get("source_name"), "url": observation.get("source_url"),
            "published_date": observation.get("source_date"),
        }]
        regions = [observation["region"]] if observation else ["europe"]
        places = [observation.get("country") or "United Kingdom (BerryWorld Group base)"]
        roles = [observation["role"]] if observation else []
        if key == "mbo-hortifrut-naturipe-blueberry-genetics-2026-07-30":
            regions.append("latin-america")
            places.extend(("Mexico", "Peru"))
        elif kind == "licensing":
            regions = []
            places = ["International agreements with terms to verify by market"]
            roles = ["rights"]
        elif key == "cornell-crimson-beauty-crimson-blush-spring-2025-availability":
            roles.append("propagation")
        stamp, basis = candidate.get("event_date"), "Event date"
        if not stamp:
            stamp, basis = candidate.get("announcement_date"), "Announced"
        if not stamp:
            stamp, basis = sources[0].get("published_date"), "Source published"
        events.append({
            "id": key, "kind": kind, "stage": stage,
            "title": candidate.get("title") or observation["title"],
            "summary": candidate.get("summary") or observation["summary"],
            "date": stamp or "", "date_label": basis,
            "crops": [berry_id.removeprefix("berry-") for berry_id in candidate["berry_ids"]],
            "regions": regions, "roles": roles,
            "entity_ids": candidate.get("entity_ids", []),
            "places": places,
            "existing_evidence_id": candidate.get("existing_evidence_id"),
            "identifier": "24-087-01rsr" if kind == "regulatory" else "",
            "jurisdiction": "US" if kind == "regulatory" else "",
            "sources": [{"source_name": source["name"], "source_url": source["url"],
                         "published_date": source.get("published_date")} for source in sources],
        })

    registration = observations.get("st-ap-yotsuboshi-registration")
    if registration:
        for identifier, stage, stamp in (
            ("28844", "Application filed", "2014-01-10"),
            ("28844", "Application published", "2014-07-14"),
            ("25605", "Registered denomination", "2017-02-08"),
        ):
            events.append({
                "id": f"jp-yotsuboshi-{stamp}", "kind": "ip", "stage": stage,
                "title": "YOTSUBOSHI strawberry · Japan", "summary": registration["summary"],
                "date": stamp, "date_label": stage, "crops": ["strawberry"],
                "regions": ["asia-pacific"], "roles": ["rights"], "entity_ids": [],
                "places": ["Japan"], "existing_evidence_id": None, "identifier": identifier,
                "jurisdiction": "JP", "sources": [{
                    "source_name": registration["source_name"], "source_url": registration["source_url"],
                    "published_date": registration["source_date"],
                }],
            })
    return sorted((
        row for row in events
        if (not crop or crop in row["crops"])
        and (not region or region in row["regions"])
        and (not role or role in row["roles"])
    ), key=lambda row: (row["date"], row["id"]), reverse=True)


def public_coverage(
    data_dir: Path, *, crop: str = "", region: str = "", role: str = ""
) -> dict:
    """Keep source verification distinct from canonical publication and absence."""
    path = Path(data_dir) / BASELINE
    baseline = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    path = Path(data_dir) / FOLLOWUPS
    followups = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    scope = set(product(
        (crop,) if crop else CROPS,
        (region,) if region else REGIONS,
        (role,) if role else ROLES,
    ))
    observations_by_cell = {key: [] for key in scope}
    observations = []
    for observation in [*baseline.get("observations", []), *followups.get("observations", [])]:
        key = (observation["crop"], observation["region"], observation["role"])
        if key in observations_by_cell:
            observations_by_cell[key].append(observation)
            observations.append(observation)
    searched_gaps = {
        (gap["crop"], gap["region"], gap["role"]): gap
        for gap in baseline.get("searched_gaps", [])
    }

    counts = {"evidenced": 0, "searched_gap": 0, "unresearched": 0}
    cells = []
    for crop_key, region_key, role_key in product(CROPS, REGIONS, ROLES):
        key = (crop_key, region_key, role_key)
        if key not in scope:
            continue
        rows = observations_by_cell[key]
        actors = {
            (row["entity_id"], row["entity_name"]): {"id": row["entity_id"], "name": row["entity_name"]}
            for row in rows
        }
        source_name, source_url = (_RIGHTS_START if role_key == "rights" else _REGION_START)[region_key]
        if rows:
            state = "evidenced"
            reason = "At least one scoped public source was checked. Operator coverage is partial."
            next_step = _ROLE_SEARCH[role_key]
        elif key in searched_gaps:
            state = "searched_gap"
            gap = searched_gaps[key]
            reason, source_url, next_step = gap["reason"], gap["next_source"], gap["next_step"]
            source_name = ""
        else:
            state = "unresearched"
            reason = "No role-specific primary-source check is logged for this cell."
            next_step = _ROLE_SEARCH[role_key]
        counts[state] += 1
        cells.append({
            "crop": crop_key,
            "region": region_key,
            "role": role_key,
            "state": state,
            "actors": list(actors.values()),
            "latest_dated_evidence": max((row["source_date"] for row in rows if row["source_date"]), default=None),
            "reason": reason,
            "next_source": source_url,
            "next_source_name": source_name,
            "next_step": next_step,
        })

    return {
        "as_of": max(filter(None, (baseline.get("as_of"), followups.get("as_of"))), default=None),
        "cells": cells,
        "counts": counts,
        "observations": observations,
        "milestones": _observed_milestones(baseline, followups, crop, region, role),
    }
