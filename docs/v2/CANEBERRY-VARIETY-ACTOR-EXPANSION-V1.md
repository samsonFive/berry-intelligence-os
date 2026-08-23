# Caneberry Variety + Actor Expansion V1

**Mission:** Evidence-grounded Variety/actor identity expansion (2026-08-22, branch `feature/caneberry-variety-actor-expansion-v1`), directly following Blackberry/Raspberry Vertical V1 (live recall: raspberry 9/9, blackberry 7/9, but blackberry's Variety catalog was 1 entity/0 breeding programs/0 CPVO filings) and Evidence Berry Tagging Backfill V1 (raspberry Evidence 191->218, blackberry 146->167, catalog depth unchanged by design).
**Scope discipline:** build the graph from evidence already earned. No new source added, no UI redesigned, no trust semantics changed.

## 1. Canonical caneberry Variety inventory (before)

| | Raspberry | Blackberry |
|---|---|---|
| Varieties | 12 | 1 (Victoria) |
| Breeding programs (dedicated entity type) | 0 | 0 |
| CPVO-referencing evidence | 4 | 0 |
| US plant patents (trusted `patent_filing`) | -- | 0 |

Existing raspberry Varieties (Amalia Rossa, Baridi, Crimson Night, Crimson Treasure, Double Gold, Kwanza, Malaika, Rafiki, Sarafina, Shani, Zawadi, plus a seed fixture) were already reasonably grounded, but a direct audit found most carried only 1 evidence record each and one -- Malaika -- had a real, trusted, already-berry-tagged article (from Evidence Berry Tagging Backfill V1) sitting completely unlinked.

## 2. Candidate set built from trusted Evidence (not from the 3 given examples alone)

Systematically searched all raspberry/blackberry-tagged trusted Evidence for `variety`/`cultivar` mentions (12 hits), then read every one in full rather than trusting the title:

| Candidate | Berry | Trust state of grounding evidence | Disposition |
|---|---|---|---|
| Yosemite (Planasa) | Blackberry | **Untrusted draft only** (`inbox/evidence/ev-media-8aa83a0a3b75e8aaa3d9`, still `awaiting_publication_review`) | **Not created.** A real variety, verified via real trade press in a prior mission, but its only Evidence has never passed the human publication-review gate -- creating a trusted-corpus Variety entity grounded in an unreviewed draft would violate the same evidence-grounding discipline every existing entity meets. |
| Ervin (NC State) | Blackberry | Trusted, published | **Created.** |
| Ponca (University of Arkansas) | Blackberry | Trusted, published | **Created.** Found via systematic search, not one of the 3 given examples. |
| Ouachita (University of Arkansas) | Blackberry | Trusted, published | **Created.** Found via systematic search. |
| Rejoice / BK 6-13 (PSG) | Blackberry | Trusted, published (2 independent sources) | **Created** as a brand (Rejoice, platform) + variety (BK 6-13, the one named selection under it), mirroring the existing BluGenix/Eterna precedent rather than force-fitting the whole platform into one cultivar identity. |
| Malaika (ABB / Onubafruit) | Raspberry | Already exists; new Onubafruit evidence trusted, published | **Enriched**, not created -- see Section 3. |
| "New raspberry variety from Mexico" | Raspberry | Trusted, but the stored summary is truncated mid-sentence with no variety name given | **Not created.** Insufficient evidence -- exactly the "trial code / no identity support" case this mission was told to reject. |

A second real, incidental finding while auditing: `ev-20260806173539-9f2f-...` ("Herriot, a luscious new strawberry...") carried `berry_ids: ['berry-raspberry']` despite its own text naming strawberry throughout, and its `submitted_by` field traces to a source literally named "Raspberry variety license" -- a real, pre-existing tagging error inherited from the original bulk-seed process's source-bucket-based tagging, not something Evidence Berry Tagging Backfill V1's empty-only backfill rule could have caught. Corrected (`berry-raspberry` -> `berry-strawberry`) since it directly polluted this mission's own candidate search. A second suspicious case (`ev-abb-varieties`, tagged `berry-blueberry` while its own summary says "raspberry cultivars only... No blueberry cultivar appears") was investigated and found to be **intentional, not an error**: it is a deliberately-tagged "negative evidence" record from an earlier blueberry-scoped pilot mission, proving Advanced Berry Breeding is *not* a blueberry breeder -- its `berry_ids` represents the category the evidence is making a claim about, not its content species, and its own `fact_ids`/`tags` (`negative-evidence`, `scope-correction`) confirm the intent. Left untouched; only added as a further evidence link on `variety-malaika` (it already grounded 5 sibling raspberry varieties).

## 3. Identity resolution

- **Malaika**: already a canonical Variety entity. A real, trusted, backfill-tagged evidence record (`ev-20260806173853-c7ff-...`, Onubafruit's Spanish plantings) was sitting with `entity_ids: []` -- linked to `variety-malaika` and a newly-created `company-onubafruit`. This is a real, second, independent licensed-grower relationship for the same ABB Elite Raspberry Collection variety (The Summer Berry Company already held the Portugal relationship) -- both preserved as separate `grows` edges, no forced single grower.
- **Yosemite**: real variety, correctly *not* created this mission (Section 2).
- **Ervin**: no existing entity under any name; created clean.
- No duplicate identity was created for any candidate -- every new entity was checked against `data/entities/companies/`, `data/entities/varieties/`, and `data/entities/brands/` by name and known alias before creation (confirmed via direct `grep`/`ls`, not assumed).

## 4. Actor / organization grounding

| Organization | Status before | Action | Grounding |
|---|---|---|---|
| NC State University | Did not exist under any name | **Created** (`company-nc-state-university`) | 1 trusted evidence record, real `develops` relationship to Ervin |
| Onubafruit | Did not exist | **Created** | 1 trusted evidence record, real `grows` relationship to Malaika |
| University of Arkansas | **Already existed**, already had `breeder` role and already referenced Ouachita's own evidence in its own `evidence_ids` -- the actor was present, the Variety-level graph connection was missing | Enriched: 2 new `develops` relationships (Ponca, Ouachita), Ponca's evidence added to the university's own `evidence_ids` | Real |
| Plant Sciences Genetics (PSG) | Already existed | Enriched: 2 new relationships (`owns` Rejoice, `develops` BK 6-13) | Real |
| G-Berries, FruitMasters (flagged in a prior mission) | Not needed by any grounded Variety this mission | **Not created** | No real, currently-evidenced Variety identity required either actor this mission; creating them now would be exactly the "company to improve matching" anti-pattern this mission forbids. |

## 5. Relationship roles preserved

Every new relationship uses the existing `predicate` enum (`develops`, `owns`, `grows`, `operates_in`) and keeps breeder/owner/licensee/marketer/grower distinct -- confirmed live on `/entities/variety/variety-malaika`: **BREEDER** Advanced Berry Breeding B.V.; **GROWER** Onubafruit, The Summer Berry Company (two separate real grower relationships, not collapsed); **OWNER/RIGHTS HOLDER**, **LICENSEE**, **MARKETER**, **DISTRIBUTOR** all correctly show "--" (not fabricated). No actor was given a role the evidence does not support.

## 6. CPVO impact -- measured, not assumed

A bounded dry-run (`python scripts/monitor_cpvo_registry.py --dry-run --json`, 140 real queries against every tracked Variety's name/aliases, including the 4 new blackberry entries) found:

- **BK 6-13, Ervin: 0 CPVO hits** (a 2026 US commercial release and a very recent NC State release are not expected in the EU register).
- **Ouachita, Ponca: 1 real, berry-relevant hit each -- both new.**

Applied for real (`python scripts/monitor_cpvo_registry.py --json`, same bounded mechanism, writes only untrusted drafts): **`review_ready: 2`**, both created as `status: draft` in `inbox/evidence/` (`ev-cpvo-cpvo-1e923ddc1c182018` = Ouachita, `ev-cpvo-cpvo-8ac7b2bd779acb96` = Ponca), both real **CPVO Community Plant Variety Right filings under `Rubus subg. Rubus`** -- the correct genus for blackberry, not a false-species match. Neither was linked to the trusted Variety entity; both remain untrusted pending the existing human publication-review gate, per this mission's own trust-boundary rule.

**This is the direct, measured proof Section 6 asked for**: adding 2 evidence-grounded blackberry Varieties immediately unlocked 2 real CPVO registry matches that were structurally unreachable before (CPVO's query mechanism is seeded from tracked Variety names -- with 0 tracked non-Victoria blackberry varieties before this mission, it could not have found these).

## 7. US plant patent cross-check

A bounded dry-run of the existing phrase-query patent watchlist (`"blackberry plant named"`, `publication_after: 2023-01-01`) found 15 real raw blackberry-plant-patent hits, all already known (Driscoll's DrisBlackThirty-series, Celestial, thunderhead, APF-404T/409T, MEF-2022.1, HFG B2008T/B1902T, A-2718T). **None correspond to Ervin, Ponca, Ouachita, or BK 6-13.** This is an honest negative, not a gap to force-fill: Ponca and Ouachita were both released in **2003**, well before the watchlist's own 2023 publication-date floor, so a real historical US plant patent for either (if one exists) is structurally outside this bounded mechanism's current reach -- a real, separate limitation from CPVO absence, not evidence the varieties are unprotected. Ervin/BK 6-13 (2026) are within the window but returned no match, consistent with either no public patent filing yet or a different exact commercial name in any filing. CPVO absence for BK 6-13/Ervin and patent absence for Ponca/Ouachita are two structurally different kinds of "not found," and this mission reports them as such rather than treating either as proof of no IP protection.

## 8. Trait evidence

Only explicitly-supported traits were added, each tied to its exact source and stated as qualitative when no figure was given (mirroring the existing Malaika/Eterna convention): Ervin's "flavor-packed" description (NC State's own release), Ponca's "pinnacle of flavor" (Southwest Times Record), Ouachita's "thornless" (stated directly) plus its real 2003 Outstanding Fruit Cultivar Award. No trial/geography scope was universalized -- each `package_note` states plainly that grounding is single-source where that is true, and no quantitative figure was invented where none was reported.

## 9. Blackberry: before / after

| | Before | After |
|---|---|---|
| Varieties | 1 (Victoria) | **5** (Victoria, Ervin, Ponca, Ouachita, BK 6-13) |
| Breeding programs (dedicated entity) | 0 | 0 (unchanged -- NC State and Onubafruit were modeled as `company`, matching the existing convention that breeder orgs generally live as Company entities, e.g. University of Arkansas, PSG, ABB; no case required the separate `breeding_program` entity type) |
| `develops`/`owns` relationships | 1 (Driscoll's develops Victoria, pre-existing) | **5** (+ NC State->Ervin, UAr->Ponca, UAr->Ouachita, PSG->Rejoice, PSG->BK 6-13) |
| CPVO-referencing evidence | 0 | **2** (untrusted drafts, Ouachita + Ponca) |
| Patent links | 0 | 0 (real, bounded check found none within reach -- Section 7) |
| Commercial observations | 0 | 0 (none found in trusted Evidence for any new variety; not fabricated) |

Blackberry's Variety-catalog depth materially improved (1 -> 5) exactly where real trusted evidence already supported it, and no further. Parity with raspberry's 12 was never attempted or claimed.

## 10. Raspberry: before / after

| | Before | After |
|---|---|---|
| Varieties | 12 | 12 (unchanged -- no new raspberry Variety identity was found with sufficient trusted-evidence support; the one candidate found, "new raspberry variety from Mexico," failed the identity-support test) |
| Malaika's own evidence_ids | 4 | **5** (+ Onubafruit/Spain) |
| Malaika's own relationship_ids | 2 | **3** (+ Onubafruit `grows`) |
| New raspberry-side actor | -- | Onubafruit (grower, Spain) |

Raspberry needed materially less work, exactly as the mission anticipated -- its catalog was already close to fully grounded; the one real gap found and closed was a missing evidence link on an existing entity, not a missing entity.

## 11. Search / alias proof (live-verified, port 8002, this worktree's own code)

- `/search?q=Onubafruit` -> exactly 1 Company result ("Onubafruit," `TRUSTED`), correctly cross-linked to Variety (Malaika), Geography (Spain), and 2 Intelligence hits. No duplicate rows.
- `/search?q=PSG` -> resolves to "Plant Sciences, Inc. (alias match)" as the single Company result, correctly distinct from the separate `PENDING`-labeled "PSG expands Rejoice..." draft intelligence hit (an untrusted item from a prior mission, correctly never presented as trusted because it matched).
- No alias produced a duplicate Company or Variety row in either search.

## 12. Variety UI proof (live-verified)

`/entities/variety?berry=berry-blackberry`: "Showing 5 of 64 varieties" -- BK 6-13, Ervin, Ouachita, Ponca, and Victoria all render with correct breeder links, correct "No filings recorded" state (accurate -- the 2 real CPVO hits are untrusted drafts, correctly not shown as filings on a trusted view), and correct recent-evidence snippets. The company/breeder filter dropdown lists "North Carolina State University" and "Onubafruit" in correct alphabetical position among 50 existing companies. `/entities/variety/variety-malaika` correctly shows two separate `GROWER` entries (Onubafruit, The Summer Berry Company) under one role bucket, a `BREEDER` entry for ABB, and empty (not fabricated) `OWNER/RIGHTS HOLDER`, `LICENSEE`, `MARKETER`, `DISTRIBUTOR` rows. The Network graph renders both real `grows` edges separately. `/entities/variety?view=compete&berry=berry-blackberry` loads without error.

**One real, small code fix was needed, and is itself a genuine finding**: `app/services/variety_workspace.py`'s `present_competition()` set `blackberry_thin = berry_id == "berry-blackberry"` -- an unconditional flag, true whenever the selected berry context is blackberry, regardless of actual Variety count. This is a real, previously-undiscovered hardcoded-bias case that Blackberry/Raspberry Vertical V1's own portability audit could not have found, because it only becomes observable once blackberry's real Variety count changes -- which this mission is the first to do. The full pytest suite surfaced it directly: `tests/test_variety_workspace.py::test_index_route_does_not_call_footprint_or_compete` and `::test_context_bar_filters_variety_index` both asserted `"(thin)"` must appear for blackberry, which stayed true even after this mission's real data made blackberry genuinely not thin (5 varieties). Fixed to `berry_id == "berry-blackberry" and len(berry_varieties) <= 1` -- now count-driven, matching the exact `<=1` threshold `berry_inventory()` already used elsewhere in the same file, and will correctly render the "honestly thin" copy again if blackberry's real count ever drops back to <=1. Both affected tests, plus a third (`test_competition_needs_a_berry_and_shows_blackberry_thin`, renamed to `test_competition_needs_a_berry_and_blackberry_thin_is_count_driven`), were updated to assert the new, real, correct behavior rather than the stale hardcoded expectation. This confirms the platform's existing Variety Intelligence surfaces are otherwise genuinely data-driven -- the one exception found was itself closed by this mission, not merely documented.

## 13. Commercial Positions compatibility

`/queues/commercial_position` loads without error against the expanded entity/relationship graph. None of this mission's new/modified Evidence carries a `priority.commercial_position.level` above `none` (untouched by this mission), so nothing new appears there yet -- correct, since Commercial Positions is tagged-Evidence-driven and this mission did not tag anything for commercial-position review. No Position schema, logic, or architecture was touched.

## 14. Static / private safety

The 2 new CPVO drafts and the pre-existing Yosemite draft remain in `inbox/evidence/` (gitignored, never read by `build_static.py`). `scripts/build_static.py`'s own leak self-check was run after every real data change and passed clean (no unpublished draft id or title in `generated/`). Only the entities/relationships/evidence-field changes this mission made to already-**trusted**, already-published records were built into the static snapshot.

## 15a. Canonical-runtime promotion proof (production, 2026-08-23 UTC)

Deployed via the documented `docs/v2/CANONICAL-DATA-PROMOTION-RUNTIME-SYNC-V1.md` runbook, not manual runtime copying -- this mission's own real, mixed workload (7 new entities, 8 new relationships, 9 updates to already-existing trusted records) is exactly the case that mechanism exists for.

- **Backup**: created and verified via `scripts/runtime_backup.py` before any mutation -- `berry-runtime-20260823T044323Z.tar.gz`, archive SHA-256 `2d2703d993fca5db4dbafffc9dad3522ddf5963db2530eb636665f0ba094249f`, scope `data`+`inbox`, state `created_and_verified`.
- **Container rebuild + automatic startup sync**: `docker compose ... up -d --build` (real code change in `variety_workspace.py` required a rebuild, not just a data sync). Startup log: `"NEW": 15, "files_added": 15` -- all 7 new entities + 8 new relationships promoted automatically, byte-for-byte, with zero manual file copying, exactly matching the "new records remain automatic at startup" contract.
- **Explicit dry-run** (`python -m scripts.sync_trusted_data --canonical-sha 4022395...`): `"SAFE_CANONICAL_UPDATE": 7` of the 9 modified-existing records. `"CONFLICT": 57` and `"RUNTIME_DIVERGED": 18` matched the exact pre-existing legacy counts already documented in the runbook's own prior production proof -- confirming this mission introduced no new conflicts of that class.
- **Explicit apply** (`--apply-safe-updates --verified-backup ...`): `"updated_count": 7`, `"incomplete_transaction": false`. A JSON audit report was persisted under `inbox/operations/promotions/`. Verified live: `variety-malaika.json`'s runtime copy now carries the real Onubafruit evidence/relationship; `company-plant-sciences-genetics.json`'s runtime copy now carries both new relationships.
- **2 of the 9 modified-existing records did NOT qualify for automatic safe promotion**: `company-university-of-arkansas.json` and `ev-20260806173540-a6ec-new-year-round-premium-blackberry-platfo.json`, both classified `CONFLICT` with reason `"existing differing record has no last-promoted baseline"` -- these two files predate the promotion mechanism's own baseline tracking (part of the same bootstrap-era class TD-076 already documents) and their runtime copies were confirmed, by direct inspection, to simply be the *stale, pre-this-session* content (University of Arkansas's runtime copy still lacks the `breeder` role and evidence added in an earlier mission), not independently-diverged real production data. Per this mission's own explicit instruction ("do not manually copy files into production unless the canonical mechanism explicitly fails, and the failure is reported first"), and because the mechanism did **not** fail here -- it correctly and safely declined an unbaselined case exactly as designed -- these two files were **left un-reconciled** rather than force-copied. This is not consequential to the live graph: `rel-university-of-arkansas-develops-ponca` and `rel-university-of-arkansas-develops-ouachita` (the relationship records themselves) were already promoted automatically as new files, confirmed present at `/app/runtime/data/relationships/`, and the Variety detail pages resolve breeder relationships by querying the relationships store directly rather than through the Company entity's own cached `relationship_ids` list (confirmed in Section 12) -- so Ponca and Ouachita correctly show University of Arkansas as breeder in the live app regardless. The University of Arkansas entity's own profile page not yet showing the `breeder` role/updated `relationship_ids` is a real, minor, honestly-reported gap requiring a future deliberate reconciliation pass, not a broken relationship.
- **Post-deployment verification**: internal `/healthz` returned 308 (HTTPS redirect, expected for plain HTTP), public `https://intel.johnnyaceii.com/healthz` returned 200. `scripts/collection_status.py` ran cleanly, reporting normal scheduled-pipeline state with one pre-existing, unrelated source failure (a 403 from a third-party feed, not caused by this mission).

## 15b. Technical debt

Read fresh via `git show origin/v2/intelligence-os:docs/v2/TECHNICAL-DEBT-REGISTER.md` immediately before writing (TD-076 confirmed highest; no concurrent mission had added TD-077+). No new debt was manufactured. This mission's own findings (Yosemite's trust-gate block, the 2003 patent-watchlist blind spot, the Herriot mistag) are each either already resolved in-mission (Herriot) or are real, honest, structural facts reported in-line rather than framed as new unresolved debt requiring a registry entry -- none met the bar of "a real limitation someone will hit again unknowingly."
