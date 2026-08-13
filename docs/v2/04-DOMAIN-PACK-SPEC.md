# Intelligence OS — Domain Pack Specification (V2)

**Status:** Planning draft, not accepted.

## Purpose

A Domain Pack is how "domain-specific concepts belong in Domain Packs rather than core application code" (Core Design Principle #7) actually gets implemented. It is a versioned, declarative bundle — not a code plugin in V2 (see "Why declarative, not executable" below) — that tells an activated `Domain` (`03-DOMAIN-MODEL.md`) what to look like and what to watch for.

**Berries is the reference example throughout this document, but every section includes a check against a deliberately unrelated second industry** to keep the spec honest about generality, per the task's own instruction. The check used throughout: **"Enterprise SaaS Competitive Intelligence"** (tracking software vendors, product tiers, integrations, pricing changes, and partnership moves) — chosen because it shares almost nothing concrete with berries (no varieties, no geographies-as-growing-regions, no patents-on-plants) while still being a real, plausible second Domain Pack.

## Why declarative, not executable

A Domain Pack in V2 is data (JSON/YAML + Jinja template fragments), validated against a Domain Pack schema, not arbitrary executable code loaded into the core application process. This is a deliberate scope limit for V2, not an oversight:

- It keeps the security/trust boundary simple — a Domain Pack cannot do anything the core platform doesn't already know how to safely do (no arbitrary code execution risk from installing a pack).
- It matches what's actually needed to prove the Berries/second-domain split (Phase 7, `07-IMPLEMENTATION-ROADMAP.md`) — none of the contribution surfaces below require custom logic, only configuration and templates.
- A pluggable-code Collector or AI-provider extension mechanism is explicitly `LATER` (`02-TARGET-ARCHITECTURE.md` Sections 7-8) — if a genuine need for custom Domain Pack *logic* (not just configuration) emerges, that's a scope decision to make deliberately later, not a default assumed here.

## Domain Pack manifest (shape)

Every Domain Pack is a directory with a manifest and a set of declaration files, mirroring the structure the blueberry import package already proved out (`data/imports/blueberry-public-pilot-2026-08-03/manifest.json` — this isn't a new idea, it's a generalization of a pattern V1 already used once).

```
domain-packs/
  berries/
    manifest.json              # id, version, display name, berry-scope-equivalent
    entity-types.json          # Section 1
    relationship-predicates.json  # Section 2
    taxonomies/                # Section 3
      trait-vocabulary.json
      entity-role-vocabulary.json
    strategic-question-templates.json   # Section 4
    collector-templates.json   # Section 5
    report-templates/          # Section 6
      landscape-view.json
      competitor-profile.json
    filters.json                # Section 7
    visualization-config.json   # Section 8
    seed-data/                  # optional: starter Sources, starter Strategic Questions
```

## 1. Entity types

**What a Domain Pack declares**: the vocabulary of `Entity Type` values valid within its Domain (`03-DOMAIN-MODEL.md`, Entity Type), each with a display label, an icon/color hint for the visual language, and which Traits/Attributes (Section 3) apply to it.

**Berries example** (from `CURRENT-STATE-AUDIT.md`'s verified live data):

```json
{
  "entity_types": [
    {"id": "company", "label": "Company", "traits": ["ownership", "headquarters_country"]},
    {"id": "variety", "label": "Variety", "traits": ["chilling_requirement", "eating_quality", "disease_susceptibility"]},
    {"id": "breeding_program", "label": "Breeding Program", "traits": []},
    {"id": "brand", "label": "Brand", "traits": []},
    {"id": "geography", "label": "Geography", "traits": ["region"]},
    {"id": "patent", "label": "Patent", "traits": ["filing_date", "expiry_date"]},
    {"id": "retailer", "label": "Retailer", "traits": []},
    {"id": "trait", "label": "Trait", "traits": []},
    {"id": "berry", "label": "Berry", "traits": []}
  ]
}
```

**Second-domain check (Enterprise SaaS CI)**: `vendor`, `product`, `pricing_tier`, `integration`, `industry_vertical`, `analyst_firm` (for citing Gartner/Forrester-style sources as a distinct entity type). None of these resemble a berry entity type, and nothing about the *mechanism* above (id/label/traits) assumes anything botanical — it passes.

## 2. Relationship predicates

**What a Domain Pack declares**: which `predicate` values are valid for Relationships within its Domain, each with a subject-type/object-type constraint (so `licenses` between a `company` and a `variety` is valid, but nonsensical pairings can be rejected at review time).

**Berries example**: V1's original 10 (`owns`, `develops`, `licenses`, `distributes`, `grows`, `trials`, `sells`, `carries`, `partners_with`, `operates_in`) plus the six the blueberry import package's own research identified as missing (`03-DOMAIN-MODEL.md`, Relationship section): `exhibits_claimed_trait` (variety → trait), `protects` (patent → variety), `markets` (company → variety/brand), `offers` (nursery → variety), `administers_license_for` (company → variety), `subsidiary_of` (company → company).

**Second-domain check**: `integrates_with` (product ↔ product), `competes_with` (vendor ↔ vendor), `acquired` (vendor → vendor), `certified_by` (vendor → analyst_firm), `bundles` (product → product). Structurally identical mechanism (subject type, predicate, object type, evidence-required) — passes.

## 3. Taxonomies / traits / attributes

**What a Domain Pack declares**: controlled vocabularies for the free-form parts of the core schema that would otherwise drift into inconsistent strings — directly addressing the gap the blueberry import package itself flagged (P-9, entity roles: *"`entity.roles[]` is free strings... unenforceable against free text"*).

**Berries example**: the entity-role vocabulary the import package already proposed (`breeder`, `genetics_owner`, `nursery`, `propagator`, `license_administrator`, `marketer`, `grower_shipper`, `exporter`, `importer`, `cooperative`, `branded_berry_company`, `research_institution`, `university_breeding_program`, `retailer`, `distributor`, `packer`), plus a trait-value vocabulary for things like `chilling_requirement` (numeric + unit) and `eating_quality` (a controlled descriptive scale, since this is currently free-text prose per fact statement — `CURRENT-STATE-AUDIT.md` Section 5).

**Second-domain check**: role vocabulary for Enterprise SaaS CI: `platform_vendor`, `reseller`, `systems_integrator`, `channel_partner`, `industry_analyst`. Trait vocabulary: `deployment_model` (cloud/on-prem/hybrid), `pricing_model` (per-seat/usage-based/flat). Same mechanism, different content — passes.

## 4. Strategic-question templates

**What a Domain Pack declares**: a starter set of `Strategic Question` records (`03-DOMAIN-MODEL.md`) a new Workspace activating this Domain gets pre-seeded with — the enduring questions this kind of market analysis is usually organized around.

**Berries example**: the 9 live strategic questions today, e.g. *"Which organizations appear to be expanding through partnerships, acquisitions, nurseries, licensing networks or commercial plantings?"* and *"Which genetics are becoming available in new countries or production regions through licensing or nursery distribution?"* — these are templates in the sense that a fresh Berries Domain activation would seed with these, editable/extendable per Workspace thereafter.

**Second-domain check**: *"Which vendors are expanding their addressable market through new integrations or channel partnerships?"*, *"Which pricing model changes signal a shift in competitive positioning?"* — same shape (an enduring, evidence-organizing question), different subject matter — passes.

## 5. Collector templates

**What a Domain Pack declares**: starter `Source`/`Collector` configurations (`03-DOMAIN-MODEL.md`) relevant to the domain — which kind of source (RSS, keyword search, and whatever collector types exist per `02-TARGET-ARCHITECTURE.md` Section 7) tends to carry signal for this market, as a starting point an operator customizes rather than building from zero.

**Berries example**: the 120-source registry already built (`CURRENT-STATE-AUDIT.md` Section 6) — 86 reference sources (annual reports, government registries), 33 keyword-search sources (Google News queries like `"blueberry" "licensing agreement"`), 1 live RSS feed (Fresh Fruit Portal's berry-tagged feed) — becomes the Berries pack's shipped starter list.

**Second-domain check**: for Enterprise SaaS CI, starter sources would be vendor press-release RSS feeds, TechCrunch/analyst-firm RSS, and keyword searches like `"[vendor]" "pricing change"` or `"[vendor]" "acquires"`. Same collector *types* (RSS, keyword search), different targets — passes, and directly validates that the Collector framework itself (`02-TARGET-ARCHITECTURE.md` Section 7) doesn't need to know anything about berries to be reused.

## 6. Report templates

**What a Domain Pack declares**: the assembly logic for `Intelligence Product`/`Report` objects (`03-DOMAIN-MODEL.md`) meaningful in this domain — what query to run, what to group by, what to show.

**Berries example**: "Competitor Profile" (one company: its varieties, patents, relationships, recent activity, disputed facts flagged prominently); "Blueberry Landscape" (all companies + varieties for one berry, grouped by geography); "Weekly Digest" (everything published in the last 7 days, grouped by priority/recommendation level) — the last of these directly fulfills `PRD.md`'s "Home / analyst cockpit" module intent, generalized into a reusable template rather than one hard-coded page.

**Second-domain check**: "Vendor Profile" (one vendor: its products, integrations, pricing history, recent activity); "Category Landscape" (all vendors in one product category, grouped by deployment model). Same template *mechanism* (query + group-by + card layout), different subject — passes.

## 7. Filters

**What a Domain Pack declares**: which filter dimensions matter for this domain's list/search views, beyond the always-present core ones (entity type, date range, review state).

**Berries example**: berry (blueberry/raspberry/strawberry/blackberry), region, competitor, geography, source type, priority/recommendation level — V1's actual newsfeed filter set (`app/templates/feed.html`), generalized into declared configuration instead of hard-coded `<select>` options in a template.

**Second-domain check**: pricing model, deployment model, industry vertical, integration category. Same mechanism (a named filter dimension over an Entity/Evidence attribute), different values — passes.

## 8. Visualization configuration

**What a Domain Pack declares**: badge colors/icons per Entity Type and per review-state value (extending V1's existing `.badge-status-*` CSS pattern, `CURRENT-STATE-AUDIT.md` Section 7, into configuration rather than hard-coded classes), and any domain-specific chart/rollup hints for the Intelligence Product layer (e.g., "for Berries, a landscape view defaults to a geography-grouped card layout, not a table").

**Berries example**: the existing visual language (`PRD.md` Section 8) — purple for intelligence/navigation, green for supportive states, orange for commercial attention, blue for reading/informational priority — is already domain-neutral in its color *meaning*, so the Berries pack mostly just maps its own entity types onto these existing semantic colors rather than inventing new ones.

**Second-domain check**: nothing about "orange for commercial attention" requires berries — a SaaS CI pack reuses the same semantic palette. Where domain packs would genuinely differ is icon choice per entity type (a leaf/fruit icon set for varieties vs. a product/integration icon set for SaaS entities) — passes, and reinforces that the *visual language itself* is core, only the entity-specific iconography is per-pack.

## What a Domain Pack does NOT contribute

To keep the Core/Domain-specific boundary honest (`01-PRODUCT-VISION.md` Section 5):

- Core object schemas (Evidence, Fact, Claim, Relationship, Assessment, Signal, Recommendation, Strategic Question shapes themselves) — these are Core, identical across every Domain Pack.
- The review/approval workflow — identical across every Domain.
- The AI provider abstraction or specific AI prompts for structuring — Core (though a Domain Pack may eventually supply domain-tuned prompt *templates* as configuration, a `LATER` extension of this spec, not scoped now).
- Authentication, organization/workspace mechanics, storage, search infrastructure — none of this is Domain Pack surface area at all.

## Validation

Every Domain Pack ships with its own manifest and is validated the same way `scripts/validate_records.py` already validates data today — against a `domain-pack.schema.json` covering the shape of every section above. A Domain Pack that fails validation cannot be activated into a Workspace, mirroring the "validated before any write" discipline the blueberry import package's own `import_package.py` already demonstrated (`--dry-run` before `--apply`).

## Versioning

A Domain Pack is versioned independently of the core platform (semver). A Domain's activation in a Workspace pins to a specific Domain Pack version, so upgrading the Berries pack (adding a new predicate, say) is a deliberate, reviewable, per-Workspace decision — not a change that silently reinterprets existing data. This mirrors Core Design Principle #9's portability requirement applied to configuration, not just storage.
