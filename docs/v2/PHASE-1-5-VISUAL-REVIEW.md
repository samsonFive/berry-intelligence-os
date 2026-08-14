# Intelligence OS V2 — Phase 1.5 Visual Acceptance Review

**Status:** Written 2026-08-13, against commit `14f12e7` on `v2/intelligence-os` (working tree verified clean before capture — only the two pre-existing, unrelated untracked files `.claude/scheduled_tasks.lock` and `blueberry-public-pilot-2026-08-03.zip` present). **This document records observations only. No implementation change was made or is authorized by this document** — every suggested improvement below is a recommendation for a future task to accept, reject, or schedule, not an instruction already acted on.

**Screenshots:** `docs/v2/phase-1.5-visual-review/*.png` (24 files, listed inline below each screen's notes). Captured with Playwright driving the actual running dev server (`uvicorn app.main:app`) against real, live application data — not mocked, not the static build.

---

## 1. Blueberry Landscape (`/landscapes/berries/blueberry`)

Screenshots: `landscape-01-header-attention.png`, `landscape-02-movement-competitive.png`, `landscape-02b-competitive-field-top.png`, `landscape-03-variety-landscape.png`, `landscape-04-geo-coverage.png`

- **Intended to answer:** "What is the state of the blueberry market according to everything this platform has structured so far — what deserves my attention, what changed, and what does the platform not yet know?"
- **Strongest visual/UX element:** The header stat strip (483 evidence / 135 sources / 8/4/2026 freshness / 6 signals / 32 companies / 40 varieties) immediately followed by the italic disclaimer sentence ("This reflects what has been collected and structured so far, not a complete census..."). It's the single clearest anti-overclaiming device on the page — a viewer cannot read the header as "here is the whole market."
- **Most confusing element:** The "Competitive field" table's `INTELLIGENCE` column is a mix of stacked badges (SIGNAL/ASSESSMENT/REC.) with no consistent alignment — for rows with zero touches it's simply blank, and for rows with all three it wraps to two lines and visually crowds the row height compared to its neighbors (see `landscape-02b-competitive-field-top.png`, British Columbia Investment Management Corporation's row). Not incorrect, just visually uneven.
- **Information hierarchy:** Largely obvious — the page follows its own documented order (attention → movement → competitive field → varieties → geography → coverage/limitations), and each section has a one-line subhead explaining its purpose before showing data. A first-time viewer would not need the source code to understand what each section is for.
- **Trust/provenance sufficiently visible:** Yes. Every Signal/Assessment/Recommendation carries its status/confidence/priority badge inline in the briefing list; every evidence card under "Recent meaningful movement" carries its source type and date; the closing "Evidence coverage & limitations" section is a genuine, separate trust readout, not folded into the header stats where it would be easy to skim past.
- **Record counts mistaken for competitive importance:** Not observed. The Competitive field and Variety landscape tables are both alphabetically sorted (verified — "Advanced Berry Breeding" through "University of Florida"; "Arana" through "Twilight"), and the section subhead states directly: *"Counts are coverage indicators — how much this dataset documents about each company — not a strength ranking."* This is the one place the design most explicitly guards against a real risk, and it holds up visually.
- **Missing data presented honestly:** Yes, in two concrete places. The Geographic footprint table includes an **"Unclassified"** region row (China, 4 companies, 0 evidence) rather than silently dropping a geography that doesn't map onto the four-region taxonomy. The Evidence coverage section states "3 Varieties with ≤1 evidence record" as its own stat rather than hiding thin coverage inside an aggregate.
- **Desktop/tablet layout issue:** Yes, a real one — see Section 6 (Responsive findings) below. The Competitive field table's rightmost columns (Geographies/Evidence/Intelligence) run off the visible tablet-width content column with only a truncated "BRA" visible for the Brands header; the horizontal scroll affordance (`overflow-x:auto`) exists in the CSS but nothing in the UI signals to a tablet user that the table continues sideways.
- **Suggested improvement:** Give the Competitive field/Variety landscape tables a visible horizontal-scroll cue (e.g. a subtle right-edge gradient or "scroll for more →" hint) at narrow widths, since the current `overflow-x:auto` wrapper is functionally present but not discoverable. — **LATER / POLISH**
- **Suggested improvement:** Normalize the Intelligence-column badge stacking in wide tables (fixed-height row or a compact numeric summary with a hover/expand for detail) so rows with 0 vs. 3 intelligence touches don't visually distort row height. — **PHASE 4 / INTELLIGENCE PRODUCTIONIZATION**

---

## 2. Company intelligence — Costa Group Holdings Pty Ltd (`/entities/company/company-costa-group-holdings`)

Screenshots: `company-costa-01-overview-intelligence.png`, `company-costa-02-portfolio-network.png`, `company-costa-03-strategic-questions.png`, `company-costa-04-facts-evidence.png`, `company-costa-05-linked-evidence.png`

- **Intended to answer:** "What is this organization doing in the blueberry market, how is its position changing, and what evidence supports that understanding?"
- **Strongest visual/UX element:** The "Intelligence touching this record" section sitting directly under the identity block, before "Recent activity." A reviewer sees all 4 Signals + 1 Assessment + 1 Recommendation touching Costa in one glance, with status/confidence badges, before scrolling into the raw chronological feed — this is the single clearest evidence that BL-027's stated goal ("closes the no-portfolio-rollup gap") was actually achieved, not just claimed.
- **Most confusing element:** The generic "Attributes" `<dl>` block on the Variety page pattern also shows up here in spirit — on Costa's page it's fine (Headquarters/Country/ABN/Ownership/Former Listing/Entity Name Change Date are all genuinely useful, human-readable). The more concrete confusion is on `company-costa-02-portfolio-network.png`: the relationship row **"Costa Group Holdings Pty Ltd develops Costa Variety Improvement Program"** reads slightly oddly in English (a company "developing" a program, rather than "operating" or "runs" one) — this is an honest, unaltered rendering of the recorded `develops` predicate (company → breeding_program), not a bug, but it's the one sentence on the page a first-time reader might have to reread.
- **Information hierarchy:** Obvious. Status/roles/regions → Intelligence touching this record → Recent activity → Description → Attributes → Portfolio & network → Strategic questions → Trust summary → Facts → Linked evidence — this is a coherent "what/what matters/what changed/why/evidence/go deeper" progression, matching the Core UX principle stated in the Phase 1.5B brief.
- **Trust/provenance sufficiently visible:** Yes, strongly. `company-costa-04-facts-evidence.png` shows CLAIM/FACT badges with confidence levels inline on every fact statement, and a disputed low-confidence claim ("The stated age of Costa's blueberry breeding effort is inconsistent across sources...") is directly visible in the captured range — disputed status is not buried.
- **Record counts mistaken for competitive importance:** Not observed on this page — it's a single-entity view with no ranking mechanism to misuse.
- **Missing data presented honestly:** Not directly tested by this entity (Costa has rich data on every dimension), but the same pattern verified on the Landscape and Variety pages (empty-state text rather than hidden sections) applies here by construction — same template.
- **Desktop/tablet layout issue:** Yes — the sidebar does not collapse at ~820px width (see Section 6). At tablet width the sidebar (`tablet-company-costa-01.png`) still occupies roughly 30% of the viewport, and heading text ("Costa Group Holdings Pty Ltd") wraps awkwardly close to the content-column edge.
- **Suggested improvement:** Reword the relationship template so a company→breeding_program `develops` edge renders as "operates" or "runs" rather than literally "develops," without touching the underlying predicate value or the company→variety `develops` case (which reads correctly as-is). — **LATER / POLISH**
- **Suggested improvement:** Raise the sidebar-collapse breakpoint from 800px to ~900px, or make it fluid, so real tablet widths (768–834px, the actual iPad portrait range) get the mobile-collapsed layout instead of falling just above the current threshold. — **MUST FIX BEFORE PHASE 2** (this is a pre-existing V1 CSS breakpoint, not something Phase 1.5 introduced, but Phase 1.5's new sections make the page taller and the cramped-sidebar problem more visible; cheap, isolated, one-line CSS fix, no data/schema implications)

---

## 3. Variety intelligence — Blue Manila (`/entities/variety/variety-blue-manila`)

Screenshots: `variety-blue-manila-01-identity.png`, `variety-blue-manila-02-trait-profile.png`, `variety-blue-manila-03-breeding-ip-intelligence.png`, `variety-blue-manila-04-relationships-evidence.png`

- **Intended to answer:** "Why does this variety matter competitively — what is it, what does the owner claim about it, what has been independently verified, and what does the platform's interpretive layer say about it?"
- **Strongest visual/UX element:** The Trait profile table's "Source of claim" column. Five rows, and the honesty is immediate: four "OWNER/MARKETER CLAIM" badges and one "UNRESOLVED" badge (the conflicting 13°/14° Brix figures) — a reviewer does not need to read the underlying JSON to know that *zero* of Blue Manila's published performance figures are independently verified. This is the single clearest realization of BL-028's stated goal in the whole review.
- **Most confusing element:** The generic "Attributes" section directly above "Trait profile" (`variety-blue-manila-02-trait-profile.png`) prints raw internal ids as visible values — `Breeding Program Id: breeding_program-planasa-blueberry`, `Patent Id: patent-uspp031345p2` — immediately followed, one section later, by "Breeding program & IP" which resolves those exact same two ids into clean names and working links (`Planasa blueberry breeding programme`, `USPP031345P2`). The same two facts appear twice, once as a raw id and once resolved — a reviewer's first reaction on hitting the raw-id `Attributes` rows is "is this a bug?", even though it self-resolves one section later.
- **Information hierarchy:** Obvious overall, with the one caveat above. Identity → Intelligence touching this record → Recent activity → Description → Attributes → Trait profile → Breeding program & IP → Portfolio & network → Strategic questions → Trust summary → Facts → Linked evidence.
- **Trust/provenance sufficiently visible:** Yes — this page has the strongest provenance signaling of any screen reviewed, between the Trait profile badges and the Recent activity feed showing "disputed" directly next to the conflicting-Brix claim.
- **Record counts mistaken for competitive importance:** Not applicable — single-entity page, no ranking.
- **Missing data presented honestly:** Yes, in two ways verified directly: (1) the linked Signal's own detail page (`signal-detail-02-evidence.png`) shows "No facts linked" under "Supporting facts" even though it has 5 supporting evidence items — the platform states plainly that no Fact object formalizes this Signal yet, rather than fabricating a placeholder; (2) the pattern verified on `variety-arana` in `tests/test_synthesis_views.py` (no trait data → "No structured trait data recorded" empty-state, no patent number → "no patent number recorded") is the same honest-absence pattern this template uses everywhere.
- **Desktop/tablet layout issue:** Same sidebar-collapse issue as Company (Section 6); the Trait profile table itself held up reasonably at tablet width in spot-checks (5 rows × 4 columns is narrower than the 7–8-column Landscape tables), though it wasn't captured at tablet width directly in this pass.
- **Suggested improvement:** Suppress the raw `breeding_program_id`/`patent_id`/`patent_number` keys from the generic Attributes `<dl>` specifically when a resolved link for them already renders in "Breeding program & IP" below (a small template-level de-duplication, not a data change). — **PHASE 4 / INTELLIGENCE PRODUCTIONIZATION** (cosmetic, not blocking, but worth fixing before this becomes the production Variety view)

---

## 4. Intelligence object detail pages

### 4a. Assessment — `assessment-financial-capital-entering-berry-genetics-ownership`
Screenshots: `assessment-detail-01.png`, `assessment-detail-02-lineage.png`

- **Intended to answer:** "What does the platform's human analysis conclude from the underlying Facts, and how confident is that conclusion?"
- **Strongest visual/UX element:** The rationale text itself models exactly the discipline the eyebrow line promises ("INTERPRETATION, NOT A FACT") — it explicitly states its own limits ("This should be read as a directional pattern across a small number of large, visible transactions (n=3), not a market-wide census") rather than overclaiming. That's a content strength surfaced by the layout, not a layout trick.
- **Most confusing element:** None significant found — the page is short, linear, and unambiguous (Confidence/Reviewer/Created → Rationale → Linked strategic questions → Linked entities → Supporting facts → Supporting evidence → Counterevidence).
- **Information hierarchy:** Obvious.
- **Trust/provenance sufficiently visible:** Yes — confidence (MEDIUM) is in the metadata block at the very top, and Counterevidence gets its own dedicated section rather than being mixed into Supporting facts.
- **Record counts mistaken for competitive importance:** Not applicable.
- **Missing data presented honestly:** Not directly tested (this Assessment has full data on every field), but by construction the same template renders empty-states elsewhere.
- **Desktop/tablet layout issue:** Not captured at tablet width for this page; no reason to expect a different result from Company/Landscape given the same base template.
- **Suggested improvement:** None.

### 4b. Recommendation — `recommendation-treat-costa-driscolls-as-structurally-linked`
Screenshots: `recommendation-detail-01.png`, `recommendation-detail-02-lineage.png`

- **Intended to answer:** "What action is being proposed, why, and what does it trace back to?"
- **Strongest visual/UX element:** The full lineage is visible on one screen without scrolling past the fold twice — Linked assessments → Linked signals → Linked strategic questions all stacked directly under the rationale, each with its own type badge (ASSESSMENT/SIGNAL). A reviewer can verify `Recommendation → Assessment/Signal → Facts → Evidence → Source` by eye, which is the entire point of this object existing.
- **Most confusing element:** None significant found.
- **Information hierarchy:** Obvious.
- **Trust/provenance sufficiently visible:** Yes — Priority (MEDIUM) and Action type ("Escalate To Commercial Review") sit directly under the title, and the rationale itself explicitly disclaims overreach ("not a claim that the two organizations have merged, integrated operations, or now act as one").
- **Record counts mistaken for competitive importance:** Not applicable.
- **Missing data presented honestly:** Not directly tested.
- **Desktop/tablet layout issue:** Not captured at tablet width.
- **Suggested improvement:** None.

### 4c. Signal — `sig-financial-owners-taking-positions-in-berry-genetics`
Screenshots: `signal-detail-01.png`, `signal-detail-02-evidence.png`

- **Intended to answer:** "What pattern has been observed across multiple sources, and what would confirm or falsify it?"
- **Strongest visual/UX element:** The four-part Observation / Why it might matter / What would confirm it / What would falsify it structure, all populated with real, specific text (not boilerplate) — this is the strongest single piece of evidence in the whole review that the imported Signals carry real analytical content, not just a title and a status.
- **Most confusing element:** "Reviewer: Not yet reviewed" sits directly under "Proposed by: research-agent/blueberry-public-pilot-2026-08-03" with no visual distinction from the rest of the metadata block — a first-time viewer could misread "Not yet reviewed" as itself a data-quality warning requiring action, when it's simply an accurate, expected state for an imported-but-unreviewed Signal (all six are `reviewer: null` by design, per Phase 1.5A).
- **Information hierarchy:** Obvious.
- **Trust/provenance sufficiently visible:** Yes — Strength (moderate) is in the header metadata, and "PROPOSED" appears both in the eyebrow line and as a badge everywhere this Signal is referenced elsewhere in the app (Landscape, Costa's page), so its unconfirmed status travels with it consistently.
- **Record counts mistaken for competitive importance:** Not applicable.
- **Missing data presented honestly:** Yes — "No facts linked" under Supporting facts (see Section 3 above) is shown plainly rather than omitted or implied.
- **Desktop/tablet layout issue:** Not captured at tablet width.
- **Suggested improvement:** Consider a lighter visual treatment or a one-word explanatory note for "Not yet reviewed" (e.g. "Not yet reviewed — imported from the blueberry pilot package") so it doesn't read as an anomaly. — **LATER / POLISH**

---

## 5. Responsive check summary

Screenshots: `tablet-landscape-01.png`, `tablet-landscape-02.png`, `tablet-landscape-03-competitive-field-table.png`, `tablet-company-costa-01.png`, `tablet-company-costa-02.png` (viewport 820×1180, chosen as "approximately tablet width" per this task's instruction — close to iPad portrait's 768–834px range)

Two concrete, reproducible issues found, both pre-existing in the CSS (not introduced by Phase 1.5B, but made more visible by Phase 1.5B's new, taller pages):

1. **Sidebar does not collapse at tablet width.** `app/static/app.css`'s existing mobile rule is `@media(max-width:800px){ .sidebar{display:none} ... }`. At 820px (a realistic tablet width, and above the 800px threshold), the full ~240px sidebar remains, leaving roughly 580px for content — workable, but visibly cramped, and header text wraps closer to the edge than at desktop width. **MUST FIX BEFORE PHASE 2** — cheap, isolated, no data/schema implications, and it affects every page in the app, not just Phase 1.5B's new ones.
2. **Wide tables (Competitive field, Variety landscape — 7–8 columns) overflow the tablet content column with no visible scroll affordance.** `tablet-landscape-03-competitive-field-table.png` shows the "BRANDS" column header truncated to "BRA" at the right edge; `overflow-x:auto` is present in the wrapping `<div>` so the table *is* horizontally scrollable, but nothing in the UI signals that to a user — it simply looks cut off. **PHASE 4 / INTELLIGENCE PRODUCTIONIZATION** — specific to the new Landscape tables Phase 1.5B introduced; a real UX gap but not urgent enough to block Phase 2 (a repository/storage-layer task), since it's presentation-only and doesn't affect data correctness.

No other tablet-specific issues were found — text reflow, card layouts, and badge wrapping all held up correctly at 820px width in every screen captured.

---

## 6. Structural findings — current impact and resolution timing

Both findings were already identified, without being resolved, in `docs/v2/PHASE-1-5-PROTOTYPE-FINDINGS.md`. This section restates their *current, observed impact* (from actually looking at the running pages, not just the code) and states — as a recommendation only, not a decision made here — when each should be resolved.

### 6a. Assessment/Recommendation lack an explicit domain-scope field

**Current impact, observed directly:** None visible today. Every Assessment/Recommendation/Signal shown across every screenshot in this review is genuinely about blueberry, and the Landscape's transitive entity-intersection workaround produces a correct result in every case checked (Costa/Driscoll's/Hortifrut/Planasa are all real blueberry entities). The gap is latent, not currently observable, because this deployment has exactly one populated berry (`berry-blueberry`) and only one Assessment/Recommendation exist in total — there is no live case where the approximation could produce a wrong answer yet.

**Recommendation on timing:** **During Phase 2**, not before it and not deferred past it. Reasoning: Phase 2's own stated goal is "define repository interfaces... plus whatever rollup/query patterns Phase 1.5 found necessary" (`07-IMPLEMENTATION-ROADMAP.md`) — this is exactly that kind of query pattern, and it's cheaper to design the interface with domain-scope as a first-class concern than to retrofit it after the interface ships. It does **not** need to happen *before* Phase 2 starts (nothing currently breaks), and waiting until Phase 3/4 would mean building a second berry or domain's worth of data on top of an approximation known to be unsafe at that scale.

### 6b. Fictional V1 seed records mixed with genuine intelligence records, no structural flag

**Current impact, observed directly:** None visible on any Phase 1.5 screen in this review — the Landscape's hard-coded `SEED_FIXTURE_ENTITY_IDS`/`SEED_FIXTURE_EVIDENCE_IDS` exclusion list works correctly today (verified: no "Example Blue," "Example Genetics," or similar fictional record appears in any Landscape screenshot). The impact is entirely forward-looking: any *future* query, report, or export that doesn't know about this specific hard-coded list will include the fictional records as if real, with no structural signal telling it not to.

**Recommendation on timing:** **Before Phase 3 (PostgreSQL migration), not before Phase 2 and not "later."** Reasoning: this is fundamentally a data-hygiene problem, not an architecture problem — Phase 2 (repository interfaces over the *existing* JSON files) can reasonably keep re-using the same hard-coded exclusion list Phase 1.5B introduced, since Phase 2's own acceptance criteria only require behavior parity with today, not new correctness guarantees. But Phase 3 explicitly requires "100% of the 1,882 live V1 records... exist in Postgres with zero data loss" — loading eight fictional records into the permanent operational store, indistinguishable from real intelligence, is exactly the kind of one-way mistake Phase 3's own "zero data loss, bounded, sequential" migration philosophy exists to prevent. It should be resolved (either a real `is_seed_data` field, or physically relocating the eight records out of `data/`) as part of Phase 3's Step 1 ("freeze and archive a complete, validated Intelligence Package") — cleaning it up there is a natural checkpoint, and doing it earlier (during Phase 2) is also acceptable if convenient, but doing it *no later than* Phase 3 Step 1 is the actual requirement.

---

## 7. Summary of all classified suggestions

| # | Suggestion | Screen | Classification |
|---|---|---|---|
| 1 | Sidebar collapse breakpoint too low for real tablet widths (800px vs. ~768–834px) | All pages (site-wide CSS) | **MUST FIX BEFORE PHASE 2** |
| 2 | Wide Landscape tables overflow tablet width with no visible scroll cue | Blueberry Landscape | PHASE 4 / INTELLIGENCE PRODUCTIONIZATION |
| 3 | Intelligence-column badge stacking causes uneven row heights in wide tables | Blueberry Landscape | PHASE 4 / INTELLIGENCE PRODUCTIONIZATION |
| 4 | Raw entity ids (`breeding_program_id`, `patent_id`, `patent_number`) duplicate the resolved "Breeding program & IP" section one scroll below | Variety (Blue Manila) | PHASE 4 / INTELLIGENCE PRODUCTIONIZATION |
| 5 | "develops" predicate reads oddly for company→breeding_program edges specifically | Company (Costa) | LATER / POLISH |
| 6 | "Not yet reviewed" on imported Signals could be misread as a warning | Signal detail | LATER / POLISH |
| 7 | Assessment/Recommendation domain-scope gap | Structural (Section 6a) | **DURING PHASE 2** |
| 8 | Fictional seed-data mixed with real records, no structural flag | Structural (Section 6b) | **BEFORE PHASE 3** |

No suggestion in this document has been implemented. All are recommendations for a future task.

---

## 8. Smoke-test note

Every page captured returned a successful render with no server-side errors (`preview_logs` checked clean before, during, and after the full capture session) and no console errors attributable to the pages themselves. This confirms the screenshots reflect commit `14f12e7`'s actual behavior, not a stale or broken state. No test files were added or modified, and no existing test baseline was touched, per this task's explicit scope.
