# Entity Linking Precision V1

**Mission date:** 2026-08-23
**Starting canonical:** `396ced0ca89027f70c8fd53a7a5822256e15c311`
**Scope:** deterministic trusted-Evidence query quality; no trusted data mutation

## Root cause and real query path

The live Company and Variety detail route calls
`linked_evidence_for_entity()` and passes that one linked set into the linked
Evidence summary, activity, Recent Intelligence, and Intelligence Timeline.
The Variety detail presenter turns Recent Intelligence into its recent cards;
the trait-based Variety Intelligence section itself is independently safe
because it reads structured `Fact.entity_ids`, not alias text. Company profile
context consumes the same linked set. Facts, Relationships, Signals,
Assessments, Recommendations, lineage, and `variety_footprint()` use structured
IDs or subject/object IDs and do not use this alias primitive.

Before this mission, `entity_alias_recall.py` compiled every Entity name and
alias into one case-insensitive regex with no token boundaries, then searched
`title`, `headline`, `summary`, `excerpt`, and `why_it_matters`. It did not read
publisher article bodies. A raw occurrence in any searched field became an
`alias_recall` link. This caused both semantic collisions and literal
substring defects: `Dina` in `ANDINA`, `Ervin` in `serving`, `Eureka` in
`EurekAlert`, `Bella` in `Marimbella`, `UADA` in `Guadalajara`, and `FFSP` in
`offspring`.

Pending Recent Intelligence uses the separate untrusted `draft_attribution`
path. It was traced but deliberately not changed because acquisition/runtime
draft delivery is another active lane. Global Search is also separate: exact
Entity results expand Intelligence only through structured related IDs. A raw
query may still return an Evidence document as a weak text search result, but
that is document retrieval, not Entity grounding; Search does not share the
faulty primitive and was not redesigned.

The real canonical query `Victoria` confirms that boundary: the Variety is an
exact canonical result (rank 100), its real HortWeek Evidence is title/linked
intelligence (rank 88), and the two Costa documents remain discoverable only as
weaker raw-text document hits (rank 70, `matched_as=text`). They are not added
to Victoria's structured expansion or profile. This is intentional retrieval,
not a false Entity link.

## Victoria reproduction

`variety-victoria` has canonical name `Victoria` and alias `Driscoll's
Victoria`. `ev-costa-ownership-2024` has no Victoria Variety ID and is tagged
only for blueberry. Its `summary` says Costa originated in `Geelong,
Victoria`. The old unbounded, case-insensitive regex matched canonical alias
`Victoria` in `summary`; that alone inserted the Costa record into Victoria's
linked Evidence. Timeline and Recent Intelligence then faithfully displayed
the already-wrong shared input. The real blackberry grounding record,
`ev-hortweek-driscolls-victoria-award`, carries explicit
`entity_ids: ["variety-victoria", ...]` and remains authoritative.

## Linking precedence and rules

The implemented precedence is:

1. **Explicit structured link** — `Evidence.entity_ids` always wins, even if
   text looks geographic, lacks context, or has a conflicting berry tag.
2. **Exact strong identity** — a bounded full-title Variety identity with no
   structured geography, or a bounded Company identity in title/source
   identity.
3. **Contextual alias** — identity-class-specific deterministic fallback.
4. **No link** — text occurrence without sufficient grounding.

All fallback matches expose `link_match_type`, `link_matched_alias`, and
`link_matched_field` on shallow result copies. Trusted records are never
modified.

Variety fallback requires token boundaries, suppresses an alias when it is
inside a different tracked longer Variety name (for example `Eureka` inside
`Eureka Sunrise`), rejects incompatible structured berry tags, and requires
local berry/Variety terminology or a clear registry/portfolio mapping. It
handles straight/curly apostrophes and trademark punctuation deterministically.
Place syntax such as `in Victoria`, `Victoria state`, `Victoria market`, and
`Victoria, Australia` is rejected; canonical Geography names/aliases are used
for the comma-target check. `Geelong, Victoria` is rejected as a single-token
place construction unless independent Variety context exists, and the real
Costa record independently fails the blackberry/blueberry compatibility gate.

Company matching remains intentionally less restrictive. Bounded legal names,
multi-word trade names, exact title/source identities, distinctive names, and
short names used in direct corporate grammar remain recallable without needing
the literal word “company.” Boundaries remove `Berry Blue` from `Blueberry
Blue`, `UADA` from `Guadalajara`, and `FFSP` from `offspring`. A bare ambiguous
single word such as lowercase ordinary-noun `chambers` is not enough. Analyst
`why_it_matters` comparisons do not receive the looser multi-word shortcut,
preventing a comparison with Mountain Blue from grounding eight unrelated
OZblu patent records.

## Corpus audit and reviewed measurement

`scripts/audit_entity_linking.py` reads only canonical published Evidence; it
never reads `inbox/`. Its private/internal JSON output lists ambiguous actual
aliases, every corrected pair, reviewed false-positive classes, and legitimate
matches retained. The versioned reviewed sample is
`benchmarks/entity-linking-precision-v1.json`.

- Audited: all 64 Varieties and all 51 Companies.
- Historical fallback pairs: 52 Variety + 93 Company.
- Current fallback pairs: 18 Variety + 98 Company.
- Likely false positives corrected by full-corpus review: 34 Variety + 21
  Company = **55**.
- Newly recovered legitimate Company pairs: **26**, all Driscoll's records
  whose curly apostrophe was missed by the old straight-apostrophe regex.
- Reviewed measurement: 38 labeled pairs, 22 Varieties, 10 Companies, all four
  berries.
- Precision estimate: **65.79% before → 100% after** (25 TP / 13 FP before;
  25 TP / 0 FP after).
- Recall estimate: **100% before → 100% after** on the reviewed sample.

Ambiguity classes actually observed include geography (`Victoria`), ordinary
words (`Cargo`, `Chambers`), person names (`Jewel`/Cindy Jewell), substrings
(`Dina`, `Ervin`, `Bella`, `Berry Blue`, acronyms), longer tracked Variety
names (`Eureka Sunrise`), and incidental analyst comparisons. Actual retained
fallbacks include Sentinel title/summary references, the OZblu code/name
portfolio mapping (Bella, Bonita, Dina, Elaina, Julieta, Magica, Magnifica,
Olivia), the CFIA Carlotta/Rosita register entries, Arana, Blue Manila, Blue
Maldiva, and established Company recall such as SanLucar and USHBC.

## Shared-consumer and static proof

Because the fix is in the shared live primitive, Victoria's unrelated Costa
record disappears together from linked Evidence, activity, Recent
Intelligence, and Timeline. The profile regression test asserts the legitimate
HortWeek blackberry Evidence remains while the Costa ownership headline does
not render. Variety Intelligence continues using structured Fact linkage and
never included the Costa record; the shared fix changes its surrounding Recent
Intelligence rather than creating a page-specific exception.

Static entity pages intentionally remain more conservative: structured
`entity_ids` only. Before this mission, the outer static profile used direct
IDs while `entity_synthesis_context()` silently recomputed fuller live alias
recall for Recent Intelligence, making one static page internally inconsistent.
The static builder now supplies its already-computed structured-only set into
the shared synthesis function. Static and live therefore intentionally differ
in recall policy but are internally consistent; both remain trusted-only and
static never reads pending drafts.

## Performance

Matched patterns and longer-Variety/Geography patterns are compiled once per
Entity query, not per Evidence record. A controlled median of three warm
TestClient requests on the exact starting canonical versus this branch:

| Profile | Before | After |
|---|---:|---:|
| Planasa Company | 1.5875 s | 1.5781 s |
| Victoria Variety | 1.9565 s | 1.8671 s |
| Sentinel Variety | 2.0905 s | 1.7937 s |

The live route now also reuses its first linked set in synthesis instead of
scanning it twice. No per-page NLP, AI, embeddings, semantic search, or RAG was
added.

## Remaining boundary

Body-only mentions remain intentionally outside trusted alias recall because
the current primitive searches curated Evidence summary fields, not retained
publisher bodies. Subnational places not represented in the 19-record
canonical Geography catalog rely on deterministic syntax plus berry/Variety
context rather than a complete world gazetteer. Short single-token Company
names still require deterministic corporate grammar when they have no stronger
legal identity. These are recall/coverage limits, not permission to restore
raw occurrence grounding; they are recorded as TD-091.
