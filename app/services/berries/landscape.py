"""BerriesLandscapeService (V2 Phase 2B.2, moved from app/main.py -- V2
Phase 1.5B's BERRIES LANDSCAPE PROTOTYPE LOGIC block, BL-026).

An "Intelligence Product" that synthesizes a market view is a Core concept
(03-DOMAIN-MODEL.md, "Intelligence Product") -- but the specific rollup
computed here (variety/patent/geography coverage per company, region
derived from geography name lookups, "about this berry" derivation) is
entirely Berries-shaped, so it lives here rather than in app/queries/.
Consumes Core query services (ScopeQueryService, CoverageQueryService,
EntityIntelligenceQueryService) and record repositories -- never a
filesystem path directly.

Deliberately absent: any single blended "competitive strength" or "top
variety" score. Every count below is a labeled coverage indicator (how
much the dataset says about X), never a ranking.

Moved verbatim; behavior is unchanged except that internal data access
goes through repositories/query services instead of load_json_files().
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.services.berries.geography import entity_regions, evidence_regions, geography_region, REGIONS

# V1 seed/demo fixtures, explicitly self-described as fictional
# ("Fictional ... used as seed data") in their own description field, mixed
# into the same data/entities and data/evidence folders as real intelligence
# with no structural flag to distinguish them. Excluded here only -- not
# from individual entity/evidence pages -- because the Landscape's entire
# purpose is a truthful picture built from real data.
SEED_FIXTURE_ENTITY_IDS = {
    "company-example-genetics",
    "company-example-nursery",
    "retailer-example-market",
    "variety-example-blue",
    "variety-example-red",
}
SEED_FIXTURE_EVIDENCE_IDS = {
    "ev-sample-patent-published",
    "ev-sample-retail-placement",
    "ev-sample-variety-launch",
}

PRIMARY_SOURCE_TYPES = {
    "government_registry",
    "patent_record",
    "plant_breeders_rights_record",
    "regulatory_or_registry_record",
    "company_annual_report",
    "research_program_publication",
}


class BerriesLandscapeService:
    def __init__(self, repos: Any, queries: Any) -> None:
        self._repos = repos
        self._queries = queries

    def landscape_evidence(self, berry_id: str) -> list[dict[str, Any]]:
        return [
            r
            for r in self._repos.evidence.list(status="published")
            if berry_id in (r.get("berry_ids") or []) and r["id"] not in SEED_FIXTURE_EVIDENCE_IDS
        ]

    def landscape_entities(self, berry_id: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        return [
            e
            for e in self._repos.entities.list()
            if berry_id in (e.get("berry_ids") or [])
            and e["id"] not in SEED_FIXTURE_ENTITY_IDS
            and (entity_type is None or e.get("entity_type") == entity_type)
        ]

    def landscape_intelligence_objects(
        self, berry_id: str, berry_entity_ids: set[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Signal carries its own berry_ids; Assessment/Recommendation
        derive berry-relevance transitively via ScopeQueryService's
        legacy/default entity-intersection rule (D-012: this is a derived
        signal, not an explicit one, for either object type today)."""
        signals = [s for s in self._repos.signals.list() if berry_id in (s.get("berry_ids") or [])]
        assessments = self._queries.scope.records_by_entity_intersection(
            self._repos.assessments.list(), berry_entity_ids
        )
        recommendations = self._queries.scope.records_by_entity_intersection(
            self._repos.recommendations.list(), berry_entity_ids
        )
        return {"signals": signals, "assessments": assessments, "recommendations": recommendations}

    def landscape_competitive_field(
        self, berry_id: str, relationships: list[dict[str, Any]], entities: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        companies = self.landscape_entities(berry_id, "company")
        company_ids = {c["id"] for c in companies}
        develops: dict[str, set[str]] = defaultdict(set)
        owns_patents: dict[str, set[str]] = defaultdict(set)
        owns_brands: dict[str, set[str]] = defaultdict(set)
        licenses: dict[str, set[str]] = defaultdict(set)
        operates_in: dict[str, set[str]] = defaultdict(set)
        for rel in relationships:
            subject_id, object_id, predicate = rel.get("subject_id"), rel.get("object_id"), rel.get("predicate")
            if subject_id not in company_ids:
                continue
            obj = entities.get(object_id)
            if obj is None:
                continue
            if predicate == "develops" and obj.get("entity_type") == "variety":
                develops[subject_id].add(object_id)
            elif predicate == "owns" and obj.get("entity_type") == "patent":
                owns_patents[subject_id].add(object_id)
            elif predicate == "owns" and obj.get("entity_type") == "brand":
                owns_brands[subject_id].add(object_id)
            elif predicate == "licenses" and obj.get("entity_type") == "variety":
                licenses[subject_id].add(object_id)
            elif predicate == "operates_in" and obj.get("entity_type") == "geography":
                operates_in[subject_id].add(object_id)

        evidence = self.landscape_evidence(berry_id)
        rows = []
        for company in companies:
            cid = company["id"]
            company_regions = entity_regions(company, entities, evidence)
            company_regions |= {
                geography_region(entities[gid])
                for gid in operates_in[cid]
                if geography_region(entities[gid])
            }
            rows.append(
                {
                    "entity": company,
                    "varieties_developed": len(develops[cid]),
                    "varieties_licensed": len(licenses[cid]),
                    "patents_owned": len(owns_patents[cid]),
                    "brands_owned": len(owns_brands[cid]),
                    "geographies": len(operates_in[cid]),
                    "geography_names": sorted(entities[gid]["name"] for gid in operates_in[cid]),
                    "regions": sorted(company_regions),
                    "brands": sorted(entities[eid]["name"] for eid in owns_brands[cid]),
                    "varieties": sorted(
                        entities[eid]["name"] for eid in develops[cid] | licenses[cid]
                    ),
                    "evidence_count": len([r for r in evidence if cid in (r.get("entity_ids") or [])]),
                    "signals": self._queries.entity_intelligence.signals_for_entity(cid),
                    "assessments": self._queries.entity_intelligence.assessments_for_entity(cid),
                    "recommendations": self._queries.entity_intelligence.recommendations_for_entity(cid),
                }
            )
        # Alphabetical, not by any coverage count -- a table's row order must
        # not itself imply a ranking.
        rows.sort(key=lambda r: r["entity"]["name"])
        return rows

    def landscape_variety_rollup(self, berry_id: str, entities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        varieties = self.landscape_entities(berry_id, "variety")
        evidence = self.landscape_evidence(berry_id)
        rows = []
        for variety in varieties:
            vid = variety["id"]
            breeding_program_id = (variety.get("attributes") or {}).get("breeding_program_id")
            traits = (variety.get("attributes") or {}).get("traits") or []
            rows.append(
                {
                    "entity": variety,
                    "breeder": (variety.get("attributes") or {}).get("breeder"),
                    "breeding_program": entities.get(breeding_program_id) if breeding_program_id else None,
                    "trait_count": len(traits),
                    "traits": traits,
                    "trait_labels": sorted(
                        {t.get("trait", "").removeprefix("trait-").replace("-", " ") for t in traits}
                    ),
                    "regions": sorted(entity_regions(variety, entities, evidence)),
                    "has_patent_number": bool((variety.get("attributes") or {}).get("patent_number")),
                    "evidence_count": len([r for r in evidence if vid in (r.get("entity_ids") or [])]),
                    "signals": self._queries.entity_intelligence.signals_for_entity(vid),
                    "assessments": self._queries.entity_intelligence.assessments_for_entity(vid),
                }
            )
        rows.sort(key=lambda r: r["entity"]["name"])
        return rows

    def landscape_geographic_footprint(
        self, berry_id: str, relationships: list[dict[str, Any]], entities: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        geographies = self.landscape_entities(berry_id, "geography")
        buckets: dict[str, dict[str, Any]] = {
            region: {"geographies": [], "companies": set(), "evidence_count": 0} for region in REGIONS
        }
        buckets["Unclassified"] = {"geographies": [], "companies": set(), "evidence_count": 0}

        for geo in geographies:
            region = geography_region(geo) or "Unclassified"
            buckets[region]["geographies"].append(geo)

        for rel in relationships:
            if rel.get("predicate") != "operates_in":
                continue
            obj = entities.get(rel.get("object_id"))
            if not obj or obj.get("entity_type") != "geography":
                continue
            region = geography_region(obj) or "Unclassified"
            buckets[region]["companies"].add(rel.get("subject_id"))

        for record in self.landscape_evidence(berry_id):
            for region in evidence_regions(record, entities):
                if region in buckets:
                    buckets[region]["evidence_count"] += 1

        rows = []
        for region in [*REGIONS, "Unclassified"]:
            data = buckets[region]
            if not data["geographies"] and not data["companies"] and not data["evidence_count"]:
                continue
            rows.append(
                {
                    "region": region,
                    "geography_names": sorted(g["name"] for g in data["geographies"]),
                    "company_count": len(data["companies"]),
                    "evidence_count": data["evidence_count"],
                }
            )
        return rows

    def landscape_recent_movement(
        self,
        evidence_pool: list[dict[str, Any]],
        signals: list[dict[str, Any]],
        assessments: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        cap: int = 12,
    ) -> list[dict[str, Any]]:
        """'Recent' filtered to evidence connected to something the platform
        has already judged meaningful (a Signal/Assessment/Recommendation
        cites it) -- not simply the newest records."""
        important_ids: set[str] = set()
        for record in [*signals, *assessments, *recommendations]:
            important_ids.update(record.get("evidence_ids") or [])
        candidates = [r for r in evidence_pool if r["id"] in important_ids]
        candidates.sort(key=lambda r: r.get("published_date") or r.get("captured_date") or "", reverse=True)
        return candidates[:cap]

    def landscape_evidence_coverage(
        self, berry_id: str, berry_entity_ids: set[str], entities: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        evidence = self.landscape_evidence(berry_id)
        source_type_counts, primary_count = self._queries.coverage.evidence_source_breakdown(
            evidence, PRIMARY_SOURCE_TYPES
        )
        confidence_counts, disputed_facts = self._queries.coverage.fact_confidence_and_disputes(berry_entity_ids)
        disputed_rels = self._queries.coverage.disputed_relationships(berry_entity_ids)
        unresolved_sqs = self._queries.coverage.active_strategic_questions()
        thin_varieties = [
            v for v in self.landscape_entities(berry_id, "variety") if len(v.get("evidence_ids") or []) <= 1
        ]

        return {
            "evidence_count": len(evidence),
            "primary_source_count": primary_count,
            "source_type_breakdown": source_type_counts.most_common(),
            "confidence_distribution": confidence_counts,
            "disputed_fact_count": len(disputed_facts),
            "disputed_relationship_count": len(disputed_rels),
            "unresolved_strategic_question_count": len(unresolved_sqs),
            "thin_coverage_varieties": thin_varieties,
        }

    def landscape_context(self, berry_id: str) -> dict[str, Any]:
        entities = {e["id"]: e for e in self._repos.entities.list() if e.get("id")}
        relationships = self._repos.relationships.list()
        berry_entities = self.landscape_entities(berry_id)
        berry_entity_ids = {e["id"] for e in berry_entities}
        evidence = self.landscape_evidence(berry_id)
        intelligence = self.landscape_intelligence_objects(berry_id, berry_entity_ids)

        dated_evidence = [r for r in evidence if r.get("published_date") or r.get("captured_date")]
        last_material_update = None
        if dated_evidence:
            last_material_update = max(r.get("published_date") or r.get("captured_date") for r in dated_evidence)

        entity_type_counts = Counter(e.get("entity_type") for e in berry_entities)

        geographic_footprint = self.landscape_geographic_footprint(berry_id, relationships, entities)
        footprint_by_region = {row["region"]: row for row in geographic_footprint}

        def regional_summary(label: str, source_regions: list[str]) -> dict[str, Any]:
            rows = [footprint_by_region[r] for r in source_regions if r in footprint_by_region]
            return {
                "label": label,
                "geography_names": sorted({name for row in rows for name in row["geography_names"]}),
                "company_count": sum(row["company_count"] for row in rows),
                "evidence_count": sum(row["evidence_count"] for row in rows),
            }

        regional_summaries = {
            "americas": regional_summary("Americas", ["Americas"]),
            "emea": regional_summary("EMEA", ["Europe", "Middle East & Africa"]),
            "australia-nz": regional_summary("Australia / New Zealand", ["Oceania"]),
            # Asia is intentionally not inferred from entity attributes: the
            # Berries filter taxonomy does not classify it yet (see geography.py).
            "asia": regional_summary("Asia", ["Asia"]),
        }

        region_groups = {
            "americas": {"Americas"},
            "emea": {"Europe", "Middle East & Africa"},
            "australia-nz": {"Oceania"},
            "asia": {"Asia"},
        }
        evidence_by_region = {
            key: [r for r in evidence if evidence_regions(r, entities) & regions]
            for key, regions in region_groups.items()
        }
        competitive_field = self.landscape_competitive_field(berry_id, relationships, entities)
        variety_rollup = self.landscape_variety_rollup(berry_id, entities)
        theme_definitions = {
            "Flavor / Sweetness": {"eating quality", "soluble solids"},
            "Firmness / Shelf Life": {"fruit firmness", "postharvest shelf life"},
            "Yield / Production": {"yield", "machine harvest suitability"},
            "Climate adaptability": {"chilling requirement"},
            "Fruit size": {"fruit size"},
        }
        competitive_themes = []
        for label, trait_names in theme_definitions.items():
            matches = [
                row for row in variety_rollup if set(row["trait_labels"]) & trait_names
            ]
            if matches:
                competitive_themes.append(
                    {"label": label, "varieties": [row["entity"]["name"] for row in matches]}
                )

        evidence_index = {record["id"]: record for record in evidence}
        variety_by_id = {row["entity"]["id"]: row for row in variety_rollup}
        matrix_rows = []
        for company in competitive_field:
            company_id = company["entity"]["id"]
            associated_ids = {
                rel.get("object_id")
                for rel in relationships
                if rel.get("subject_id") == company_id
                and rel.get("predicate") in {"develops", "licenses"}
                and rel.get("object_id") in variety_by_id
            }
            associated_varieties = [
                variety_by_id[variety_id]
                for variety_id in associated_ids
                if variety_by_id[variety_id]["trait_labels"]
            ]
            if not associated_varieties:
                continue
            cells = []
            for theme_label, trait_names in theme_definitions.items():
                associations = []
                for variety in associated_varieties:
                    matching_traits = [
                        trait
                        for trait in variety["traits"]
                        if trait.get("trait", "").removeprefix("trait-").replace("-", " ") in trait_names
                    ]
                    if not matching_traits:
                        continue
                    supporting_ids = sorted(
                        {
                            evidence_id
                            for trait in matching_traits
                            for evidence_id in (trait.get("evidence_ids") or [])
                            if evidence_id in evidence_index
                        }
                    )
                    supporting_records = [evidence_index[eid] for eid in supporting_ids]
                    supporting_records.sort(
                        key=lambda record: record.get("published_date") or record.get("captured_date") or "",
                        reverse=True,
                    )
                    associations.append(
                        {
                            "variety": variety["entity"],
                            "traits": sorted(
                                {
                                    trait.get("trait", "").removeprefix("trait-").replace("-", " ")
                                    for trait in matching_traits
                                }
                            ),
                            "regions": variety["regions"],
                            "evidence_count": len(supporting_ids),
                            "latest_evidence": supporting_records[0] if supporting_records else None,
                        }
                    )
                cells.append({"theme": theme_label, "associations": associations})
            matrix_rows.append(
                {
                    "company": company["entity"],
                    "cells": cells,
                    "documented_variety_count": len(associated_varieties),
                    "evidence_count": company["evidence_count"],
                }
            )
        matrix_rows.sort(
            key=lambda row: (-row["documented_variety_count"], -row["evidence_count"], row["company"]["name"])
        )
        matrix_rows = matrix_rows[:12]
        for signal in intelligence["signals"]:
            signal_regions = set()
            for eid in signal.get("entity_ids") or []:
                if eid in entities:
                    signal_regions |= entity_regions(entities[eid], entities, evidence)
            for evidence_id in signal.get("evidence_ids") or []:
                record = next((r for r in evidence if r["id"] == evidence_id), None)
                if record:
                    signal_regions |= evidence_regions(record, entities)
            signal["regions"] = sorted(signal_regions)
            signal["supporting_evidence_count"] = len(signal.get("evidence_ids") or [])

        recent_movement = self.landscape_recent_movement(
            evidence, intelligence["signals"], intelligence["assessments"], intelligence["recommendations"]
        )
        for record in recent_movement:
            record["regions"] = sorted(evidence_regions(record, entities))
            record["actor_names"] = sorted(
                entities[eid]["name"]
                for eid in record.get("entity_ids") or []
                if eid in entities and entities[eid].get("entity_type") == "company"
            )
            record["linked_signal_titles"] = [
                signal["title"]
                for signal in intelligence["signals"]
                if record["id"] in (signal.get("evidence_ids") or [])
            ]
            record["intelligence_link_count"] = sum(
                record["id"] in (item.get("evidence_ids") or [])
                for item in [
                    *intelligence["signals"],
                    *intelligence["assessments"],
                    *intelligence["recommendations"],
                ]
            )
        curated_movement = sorted(
            recent_movement,
            key=lambda record: record.get("published_date") or record.get("captured_date") or "",
            reverse=True,
        )
        curated_movement.sort(key=lambda record: record["intelligence_link_count"], reverse=True)
        curated_movement = curated_movement[:5]

        briefing_cues = {
            "assessment-financial-capital-entering-berry-genetics-ownership": {
                "why_it_matters": "Ownership links can change disclosure, licensing posture and whether nominal competitors remain economically independent.",
                "could_change": "Transaction reversals, disclosed passive-only holdings, or evidence that licensing and disclosure remain unchanged.",
            },
            "assessment-blueberry-genetics-commercialized-through-platforms": {
                "why_it_matters": "Access terms, membership and marketing support may become as decision-relevant as the cultivar itself.",
                "could_change": "Evidence that the named platforms are only marketing wrappers over conventional per-variety licences.",
            },
            "assessment-public-trait-claims-not-yet-comparable": {
                "why_it_matters": "Programme rankings built from unmatched public claims would create false precision in testing and commercial decisions.",
                "could_change": "Comparable independent or internal measurements reproducing the published figures under disclosed protocols.",
            },
            "assessment-public-observability-varies-by-breeder": {
                "why_it_matters": "The most visible pipeline in one registry is not necessarily the largest or most active competitive pipeline.",
                "could_change": "A systematic multi-jurisdiction sweep showing the apparent asymmetry was caused only by incomplete search.",
            },
            "assessment-southern-africa-licensing-enforcement": {
                "why_it_matters": "Licensing disputes and third-party commercial management reveal whether proprietary control is holding after deployment.",
                "could_change": "Evidence that the documented enforcement event was isolated and the regional programmes remain commercially marginal.",
            },
        }
        executive_assessments = []
        recommendation_by_assessment: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for recommendation in intelligence["recommendations"]:
            for assessment_id in recommendation.get("assessment_ids") or []:
                recommendation_by_assessment[assessment_id].append(recommendation)
        prioritized_assessments = sorted(
            intelligence["assessments"],
            key=lambda assessment: (
                bool(assessment.get("ai_proposed")),
                {"high": 0, "medium": 1, "low": 2}.get(assessment.get("confidence"), 3),
                assessment["title"],
            ),
        )
        for assessment in prioritized_assessments[:5]:
            executive_assessments.append(
                {
                    **assessment,
                    **briefing_cues.get(assessment["id"], {}),
                    "supporting_evidence_count": len(assessment.get("evidence_ids") or []),
                    "supporting_fact_count": len(assessment.get("fact_ids") or []),
                    "linked_recommendations": recommendation_by_assessment[assessment["id"]],
                }
            )

        actor_rows = [
            row for row in competitive_field if "competitor" in (row["entity"].get("roles") or [])
        ]
        actor_rows.sort(
            key=lambda row: (-len(row["signals"]), -row["evidence_count"], -len(row["varieties"]), row["entity"]["name"])
        )
        actors_to_watch = []
        for row in actor_rows[:8]:
            role_labels = [role.replace("_", " ") for role in row["entity"].get("roles") or [] if role != "competitor"]
            actors_to_watch.append(
                {
                    **row,
                    "archetype": ", ".join(role_labels[:3]),
                    "why_it_matters": (
                        f"{len(row['signals'])} linked signal{'s' if len(row['signals']) != 1 else ''}; "
                        f"{row['evidence_count']} evidence records; "
                        f"{len(row['varieties'])} documented developed/licensed varieties."
                    ),
                }
            )

        priority_signals = sorted(
            intelligence["signals"],
            key=lambda signal: (
                {"strong": 0, "moderate": 1, "weak": 2}.get(signal.get("strength"), 3),
                -signal["supporting_evidence_count"],
                signal["title"],
            ),
        )[:5]

        question_signal_counts = Counter(
            question_id
            for signal in intelligence["signals"]
            for question_id in signal.get("strategic_question_ids") or []
        )
        intelligence_agenda = {"now": [], "watch": [], "deeper": []}
        for question in self._repos.strategic_questions.list():
            linked_count = question_signal_counts[question["id"]]
            item = {**question, "linked_signal_count": linked_count}
            if linked_count >= 2:
                intelligence_agenda["now"].append(item)
            elif linked_count == 1:
                intelligence_agenda["watch"].append(item)
            else:
                intelligence_agenda["deeper"].append(item)

        region_metrics = {}
        for key, regions in region_groups.items():
            subset = evidence_by_region[key]
            regional_companies = [
                row for row in competitive_field if set(row["regions"]) & regions
            ]
            regional_companies.sort(key=lambda row: (-row["evidence_count"], row["entity"]["name"]))
            regional_varieties = [row for row in variety_rollup if set(row["regions"]) & regions]
            regional_signals = [s for s in intelligence["signals"] if set(s["regions"]) & regions]
            region_metrics[key] = {
                "companies": len(regional_companies),
                "varieties": len(regional_varieties),
                "evidence": len(subset),
                "sources": len({r.get("source_name") for r in subset if r.get("source_name")}),
                "signals": sum(bool(set(s["regions"]) & regions) for s in intelligence["signals"]),
                "geographies": sum(
                    geography_region(e) in regions
                    for e in berry_entities if e.get("entity_type") == "geography"
                ),
            }
            regional_summaries[key].update(
                {
                    "evidence_count": len(subset),
                    "company_count": len(regional_companies),
                    "variety_count": len(regional_varieties),
                    "notable_companies": [row["entity"]["name"] for row in regional_companies[:3]],
                    "signal_count": len(regional_signals),
                }
            )

        regional_briefings = {}
        for key, regions in region_groups.items():
            regional_actors = [row for row in actors_to_watch if set(row["regions"]) & regions]
            regional_varieties = [row for row in variety_rollup if set(row["regions"]) & regions]
            regional_varieties.sort(key=lambda row: (-row["evidence_count"], row["entity"]["name"]))
            regional_moves = [row for row in recent_movement if set(row["regions"]) & regions][:5]
            regional_signal_rows = [row for row in priority_signals if set(row["regions"]) & regions]
            theme_rows = []
            for theme_label in theme_definitions:
                companies, varieties = set(), set()
                for matrix_row in matrix_rows:
                    cell = next(cell for cell in matrix_row["cells"] if cell["theme"] == theme_label)
                    matches = [a for a in cell["associations"] if set(a["regions"]) & regions]
                    if matches:
                        companies.add(matrix_row["company"]["name"])
                        varieties.update(a["variety"]["name"] for a in matches)
                if varieties:
                    theme_rows.append(
                        {"label": theme_label, "company_count": len(companies), "variety_count": len(varieties)}
                    )
            regional_briefings[key] = {
                "label": regional_summaries[key]["label"],
                "picture": (
                    f"Current public coverage connects {len(regional_actors)} prioritized competitive actors, "
                    f"{len(regional_varieties)} region-attributed varieties and {region_metrics[key]['evidence']} evidence records. "
                    "These are documented connections, not market-share estimates."
                ),
                "actors": regional_actors[:5],
                "varieties": regional_varieties[:8],
                "themes": theme_rows,
                "moves": regional_moves[:5],
                "signals": regional_signal_rows[:5],
                "coverage_gap": (
                    "Records without explicit geography support are excluded from this regional view; public coverage cannot safely answer market share, deployment scale or internal product performance."
                ),
            }

        return {
            "berry_id": berry_id,
            "header_stats": {
                "evidence_count": len(evidence),
                "source_count": len(self._repos.sources.list()),
                "named_evidence_source_count": len(
                    {r.get("source_name") for r in evidence if r.get("source_name")}
                ),
                "last_material_update": last_material_update,
                "signal_count": len(intelligence["signals"]),
                "entity_type_counts": entity_type_counts,
            },
            "signals": intelligence["signals"],
            "priority_signals": priority_signals,
            "assessments": intelligence["assessments"],
            "executive_assessments": executive_assessments,
            "recommendations": intelligence["recommendations"],
            "actors_to_watch": actors_to_watch,
            "intelligence_agenda": intelligence_agenda,
            "strategic_questions": self._repos.strategic_questions.list(),
            "competitive_field": competitive_field,
            "variety_rollup": variety_rollup,
            "geographic_footprint": geographic_footprint,
            "regional_summaries": regional_summaries,
            "regional_briefings": regional_briefings,
            "region_metrics": region_metrics,
            "competitive_themes": competitive_themes,
            "competitive_theme_matrix": {
                "themes": list(theme_definitions),
                "rows": matrix_rows,
            },
            "recent_movement": recent_movement,
            "curated_movement": curated_movement,
            "evidence_coverage": self.landscape_evidence_coverage(berry_id, berry_entity_ids, entities),
        }
