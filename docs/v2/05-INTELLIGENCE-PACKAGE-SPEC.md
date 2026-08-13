# Intelligence OS — Intelligence Package Specification (V2)

**Status:** Reviewed and accepted, 2026-08-13. This spec's role grew on review: it is now also the mechanism behind Phase 3's migration-safety "freeze and archive" step (`07-IMPLEMENTATION-ROADMAP.md`), not only the long-term downstream-system export contract — a minimal exporter against this spec is built early, in Phase 2 (`10-BACKLOG.md` BL-035), rather than waiting for the full report/API/export UI in Phase 6.

## Purpose

An Intelligence Package is the portable, machine-readable, files-on-disk contract for getting structured intelligence *out of* Intelligence OS — for archival, for downstream AI agents (Copilot-style ingestion), for migration between environments, and as what an API client receives from a bulk-export call. It formalizes a pattern V1 already proved twice, in two different directions:

- **Inbound**, `data/imports/blueberry-public-pilot-2026-08-03/` — an externally-produced, self-validating, manifest-described bundle of entities/evidence/facts/relationships/strategic-questions/signals, with its own `manifest.json`, its own schema-conformance self-check, and a three-gate `--dry-run`/`--apply`/`--approve` importer.
- **Outbound**, `scripts/export_for_review.py` — a narrower, single-purpose precedent that a filtered slice of `data/` can already be serialized to a portable file and later re-applied (`scripts/apply_review_decisions.py`).

The Intelligence Package spec generalizes both into one bidirectional contract: anything V1 or V2 can *export*, a compatible system (including a future version of itself) can *import*, and anything a compatible external producer *builds to this spec* (as the blueberry package already did, informally) can be imported without bespoke one-off tooling.

## Design requirements (from the task)

The package must be suitable for: **archival**, **downstream agents**, **Copilot-like ingestion**, **migration**, and **API clients**. These pull in different directions worth naming up front:

- Archival and migration want **completeness and fidelity** — every field, every internal id, nothing summarized away.
- Downstream agents and Copilot-like ingestion want **self-description and boundedness** — a manifest that says exactly what's in the package and why, sized and chunked sensibly (JSONL, not one giant JSON blob) so an agent with a context window can consume it incrementally.
- API clients want **format choice** — JSON for structure-preserving use, CSV for spreadsheet/BI-tool consumption, JSONL for streaming/line-oriented processing.

The spec below serves all three by keeping the manifest and record shapes identical across formats, and only varying the container (one big JSON tree vs. one-record-per-line vs. flattened tabular).

## Package layout

```
package-name-YYYY-MM-DD/
  manifest.json                 # required — describes everything below
  entities/
    {entity-type}/*.json         # one file per entity, OR
    {entity-type}.jsonl           # one line per entity, per format choice (Section "Formats")
  evidence/*.json | evidence.jsonl
  facts/*.json | facts.jsonl
  claims/*.json | claims.jsonl          # see note below on claims
  relationships/*.json | relationships.jsonl
  assessments/*.json | assessments.jsonl
  signals/*.json | signals.jsonl
  recommendations/*.json | recommendations.jsonl
  strategic-questions/*.json | strategic-questions.jsonl
  source-lineage.json            # required — Section "Source lineage"
  csv/                           # optional, present only for csv-format exports
    entities.csv, evidence.csv, facts.csv, relationships.csv, ...
```

**Note on claims**: per the open decision in `03-DOMAIN-MODEL.md` (D-010) about whether Claim becomes its own schema or remains `fact.classification == "claim"`, this spec defines a `claims/` section either way — if Claim stays a Fact subtype, `claims/` is simply the subset of `facts/` with `classification: "claim"`, materialized separately for consumers who want the FACT/CLAIM split without filtering themselves. The package format does not force that schema decision either way.

## Manifest (`manifest.json`)

Required top-level fields, extending the shape the blueberry import package already used successfully:

```json
{
  "package_id": "berries-full-export-2027-01-15",
  "package_version": "1.0.0",
  "intelligence_os_version": "2.3.0",
  "domain_pack": {"id": "berries", "version": "1.4.0"},
  "generated_on": "2027-01-15T00:00:00Z",
  "generated_by": {"type": "user", "id": "user-jsmith"},
  "workspace_id": "workspace-berries-global",
  "scope": {
    "description": "All published, human-reviewed records for the blueberry berry_id, as of export time.",
    "filter": {"berry_ids": ["berry-blueberry"], "review_state": ["published"]}
  },
  "format": "json",
  "counts": {
    "entity": 162, "evidence": 1263, "fact": 132, "claim": 54,
    "relationship": 204, "assessment": 0, "signal": 6,
    "recommendation": 0, "strategic_question": 9
  },
  "content_hash": "sha256:...",
  "schema_versions": {
    "entity": "2.0.0", "evidence": "2.0.0", "fact": "2.0.0",
    "relationship": "2.0.0", "assessment": "1.0.0", "signal": "2.0.0",
    "recommendation": "1.0.0", "strategic_question": "2.0.0"
  },
  "provenance_completeness": "full",
  "review_state_included": ["published"],
  "notes": "Free-text, human-readable summary of what this export is and any caveats — direct precedent: the blueberry package's own EXECUTIVE-SUMMARY.md."
}
```

Every field above is either directly copied from, or a generalization of, a field the blueberry import package's own `manifest.json` already demonstrated works (`package`, `berry_scope`, `generated_on`, `generated_by`, `schemas_validated_against`, `counts`, `evidence_status_on_import`). `content_hash` and `schema_versions` are the two genuinely new additions, needed because V2 has to support packages moving between different versions of the platform over time — V1 never needed this since there was only ever one version of the schema.

**`review_state_included`** matters for trust: a Copilot-like downstream consumer needs to know immediately whether it's looking at fully-vetted, human-approved intelligence, or a package that deliberately includes `in_review`/AI-proposed content for a different purpose (e.g., a human reviewer's own working export). Default exports include `published` only; anything else requires an explicit, logged request.

## Record shapes

Every record in every section is the same JSON shape the live API/database would return for that object (`03-DOMAIN-MODEL.md`), unchanged by being exported — this is the whole point of keeping JSON as the interchange contract (Core Design Principle #8) even once PostgreSQL is the operational store. No package-specific transformation or renaming happens; a record pulled from Postgres and a record read from a package file are structurally identical.

Two additions to every record, present only in the export (not in the live database row, since they're derived):

- `_package_ref`: the record's id, restated, for consumers that flatten/reformat and lose the file-path context.
- `_lineage_depth`: how many hops from this record back to a Source (0 for Evidence itself, which *is* a Source reference; increasing for Fact → Evidence → Source, Assessment → Fact → Evidence → Source, etc.) — a cheap, precomputed convenience for a downstream agent that wants to reason about "how far removed from primary evidence is this claim" without walking the graph itself.

## Source lineage (`source-lineage.json`)

A dedicated file, separate from the per-record `evidence_ids`/`fact_ids` back-references already present on every object, because the task explicitly calls out "source lineage" as its own required section — and because a flattened, denormalized lineage index is exactly what a downstream agent or Copilot-style consumer needs to avoid re-deriving the `Recommendation → Assessment/Signal → Facts → Evidence → Source` chain (`03-DOMAIN-MODEL.md`) from scratch by walking every record.

```json
{
  "chains": [
    {
      "recommendation_id": "rec-...",
      "assessment_or_signal_ids": ["sig-..."],
      "fact_ids": ["fact-...", "fact-..."],
      "evidence_ids": ["ev-..."],
      "source_ids": ["source-..."]
    }
  ],
  "orphan_check": {
    "facts_without_evidence": [],
    "relationships_without_evidence": [],
    "assessments_without_facts": []
  }
}
```

`orphan_check` exists specifically to make provenance-loss (`09-RISK-REGISTER.md`) machine-detectable at export time, not just an aspiration — an empty result on every array is itself evidence the export is trustworthy; a non-empty result is a hard signal something upstream let a record through without its required chain intact, and per Core Design Principle #3 that should never happen for `published` content.

## Formats

| Format | Best for | Shape |
|---|---|---|
| **JSON** | Archival, migration, anything wanting to preserve full structure and re-import losslessly | One file per record under each `{type}/` folder (mirrors V1's `data/` layout exactly — deliberately, so migration *to* Postgres and export *back out* of it round-trip through the identical file shape) |
| **JSONL** | Downstream agents, Copilot-like ingestion, streaming processing | One `{type}.jsonl` file per record type, one JSON object per line — bounded, line-oriented, easy to chunk for a context-window-limited consumer without parsing a whole tree first |
| **CSV** | API clients wanting spreadsheet/BI-tool consumption | One `{type}.csv` per record type, array/object fields flattened or JSON-stringified into a single column with a documented convention (never silently dropped) — CSV is explicitly the lossy option, and the manifest's `format: "csv"` plus a `csv_flattening_notes` field make that loss legible rather than silent |

All three formats share the same `manifest.json` shape and the same `source-lineage.json` — only the record containers differ.

## Validation

An Intelligence Package validates the same way `scripts/validate_records.py` already validates live data — against the same schemas (`schemas/*.schema.json`, versioned per `manifest.schema_versions`) — plus package-specific checks: manifest completeness, `content_hash` matches actual content, `orphan_check` in `source-lineage.json` is empty for any `published`-scoped export. A package that fails validation is not importable, mirroring the blueberry import package's own `validate_package.py` precedent and the "validate before any write" discipline `import_package.py` already enforces.

## Import (the other half of the contract)

Symmetric with export: an Intelligence Package can be **applied** back into a Workspace using the same three-gate discipline V1's `import_package.py` already proved (`--dry-run` reports what would happen and writes nothing; `--apply` writes as `in_review`/not-yet-trusted; `--approve` is the explicit human gate that promotes to `published`), generalized from a one-off script into the standard, repeatable import path for any Domain — this closes the gap the blueberry import package's own `proposed-schema-enhancements.md` (P-11) flagged as *"the biggest structural gap... no way to bring a curated, externally-produced dataset into the repository"* other than by hand.
