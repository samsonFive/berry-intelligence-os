# Radar Data Quality & Scope-Tag Audit V1

Do not redesign Radar. Do not change Change/Scenario matchers for these
defects. Incorrect persisted Radar metadata is repaired at the resolver
that wrote it.

## Inka root cause

`dev-d92892285194` — "Inka's Berries operates a new blueberry packing plant
in Ica" — was stored as `geography-spain` / VARIETY_LAUNCH.

Path:

1. Source: blueberriesconsulting.com article about a packing plant at the
   Salvador farm in Ica, Peru (Exa query `radar:exa:production-expansion`).
2. Title names Ica and blueberry; it does not name Spain or Peru.
3. Snippet mentions Bloom Fresh as "a Spanish firm that acquired 66% of
   the genetics business" and a "new variety" under development.
4. `EntityResolver.resolve(title + snippet)` ran `COUNTRY_GEOGRAPHY`
   including `\bSpain|Spanish\b`. "Spanish" became `geography-spain`.
5. Ica was not in the country list, so Peru was never stored.
6. `VARIETY_LAUNCH` is checked before `PRODUCTION_EXPANSION`, so
   snippet "new variety" beat title "packing plant".
7. Radar cache persisted those tags. Change Engine correctly trusted the
   stored geography and presented a Peruvian packing plant as a direct
   European development.

Dogfood Phase 5 (PR #251 era) stripped parenthetical asides so Spain
dropped, but Ica still did not map to Peru — the live item became
untagged rather than correctly Peruvian. This mission keeps that
parenthetical strip and adds place aliases, nationality provenance,
title-strong event types, cache rehydrate, and an operator audit.

No company catalog, variety catalog, or relationship hop wrote Spain.
Inka's Berries is not in the company entity catalog, so `company_ids`
stayed empty. Blueberry came from the word "blueberry" in the title.

## Provenance

Each Radar development may carry `tag_provenance`: `{field, value, origin,
span, text_field}`.

Origins this mission can distinguish:

| Origin | Meaning | Stored as direct geography? |
|---|---|---|
| `explicit_text` | Country noun or location adjective in title/snippet | Yes |
| `inferred_place` | Closed place alias (Ica→Peru, Huelva→Spain) | Yes |
| `nationality_mention` | "Spanish firm / Chilean company / Dutch partner" | No |
| `stale_cache` | Pre-audit row with no provenance | Review candidate |
| `curated` | Reserved; not written automatically | Yes if present |

Not present on Radar today, and not invented here: inherited geography,
manually curated geography, company-derived geography, variety-derived
geography. Company and geography catalogs must not widen berry or
geography scope.

## Audit rules

`app/services/emerging_radar/tag_audit.py` emits review candidates:

- `nationality_vs_place` — nationality adjective stored as direct geo while
  a place/country names a different location
- `title_country_conflict` — stored geo ≠ title/snippet country nouns
- `missing_inferred_place` — title place alias missing from stored geo
- `stale_unprovenanced` — stored geo with no provenance
- `event_type_title_strong` — title is packing/patent/PBR/legal/… and
  stored type came from snippet wording
- `berry_not_in_text` — stored berry not named in title/snippet (manual
  review; not auto-dropped)

Deterministic repair (in-memory on Radar/Ask Berry OS cache read):

- Drop nationality-only direct geos; add explicit/inferred places
- Reclassify title-strong event types
- Never drop a title country noun
- Never auto-drop a berry, company, or variety
- GET `/collection-ops` never writes the cache

## Operator surface

`/collection-ops#radar-tag-quality` lists candidates: record, suspect
field, stored value, evidence-derived value, why flagged, provenance,
deterministic vs manual review. `/radar/{id}` shows tag provenance on
the development. No standalone data-quality app.

## False-positive safeguards

- "Spain" / "Spanish harvest" / Huelva stay Spain
- Planasa Huelva and Atlantic Blue Spain+Peru genetics remain available
- Hortifrut MBO Americas text does not become Europe
- UN M49 with no crop/country nouns stays untagged
- Zara strawberry does not inherit blueberry
- Raspberry patents stay raspberry
- Place aliases are a closed two-row list (Ica, Huelva)
