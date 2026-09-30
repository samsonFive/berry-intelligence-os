# Application section audit and consolidation recommendations

September 30, 2026. Basis: design checkpoint `153c7d1`, current application routes, templates, service contracts, committed records and an isolated render audit. The user has not used the app enough to establish meaningful usage patterns. Recommendations below are product judgments, not claims about measured adoption.

**Recommendation: consolidate the application's navigation and overlapping workflows before migrating every page to Glasshouse.** Most sections have real implementations. The strongest retirement candidates are duplicate navigation entries and superseded presentation variants, rather than entire intelligence capabilities. Retain the accepted visual language, News Reader, company profile and Explorer work; make the section audit a gate before the broad page migration.

No production section, record, action or route was deleted during this audit. A consolidation recommendation is not approval to discard data or bypass review.

## What was checked

- All **50 entries** in the earlier navigation inventory, including query/anchor variants. That inventory covered the feed-first rail and V2 sidebar but missed the stakeholder navigation's specialist links.
- **Eight additional entry points:** Front Page, Industry Pulse, Ask Berry, Radar, Moves, Whitespace, Search and the developer Design System page.
- **165 route registrations**, including 103 GET handlers and 62 write handlers, inventoried from `app/main.py`. Dynamic handlers such as `/entities/{entity_type}` and `/queues/{dimension}` explain several apparent missing literal routes. Static assets are a mount, not page sections.
- **75 URL variants** rendered against committed data with an isolated empty runtime, plus four operator-only routes rechecked with authoring enabled: **79 checks**, 72 HTTP 200, two expected redirects, four expected read-only denials, and one genuine 404. No outbound network attempt occurred. The four denied operator pages returned 200 in isolated authoring mode.
- Source/template/service review of the page families, state-store boundaries, alternate views, detail pages, comparisons and export/composition entry points. No POST, approval, provider refresh, binary export or operator-runtime action was executed as part of the audit.

The render audit proves that these page variants can render under the stated conditions. It does not prove full workflow correctness, current provider health, useful private queue content, deployment permissions, or visual accessibility on every page. Empty private inboxes and absent live caches are expected in this audit and are not abandonment evidence. Full deterministic tests and public-safety checks passed on the preceding checkpoint; this audit is an additional product/route assessment.

Evidence files: [route registry](../../artifacts/design-sprint/route-audit-inventory.json), [render results](../../artifacts/design-sprint/section-render-audit.json), and the reproducible [isolated audit script](../../scripts/audit_app_sections.py).

## The main findings

### Multiple generations of navigation compete

The feed-first rail, V2 sidebar and stakeholder navigation expose different sets of working features. The first design inventory consequently omitted Ask Berry, Radar, Moves and Whitespace, despite their routes, templates, services and tests. This is a discoverability and inventory problem, not evidence that the omitted pages are dead. Establish one navigation manifest with separate local/operator/public visibility policies before restyling more pages.

### News and reading need one primary home

`/today`, `/news`, `/work-queue`, `/brief`, `/week`, `/saved`, `/queues/reading` and the historical `/` feed all help someone find or consume intelligence. Their data is not identical: live cache, published corpus, publication drafts, analyst decisions and time-based synthesis differ. A single News destination can offer clear views without inventing a merged truth state. Newest-first remains the user's default; a weekly digest or analyst work queue is an explicit alternate view.

`/` without a query already redirects to `/today`. Its separate “Newsfeed” menu entry is a verified redundant destination. With query parameters it still serves the legacy published-evidence feed, so preserve or translate those bookmarks before retiring that renderer. `/today?view=briefing` is another retained older presentation, not the default News path.

### Similar review labels hide different jobs

`/statements` reads feed-first statement decisions; `/review?kind=publication` reviews source publications; `/review?kind=atomic` reviews proposition-level proposals. Source Fidelity checks recovered text/identity. Claim Testing records a testing disposition. Signal Review decides a proposed pattern. These can share a Review home and navigation, but must retain separate stages, source context, permissions and explicit decisions. A confirmed feed statement, a canonical Fact, a published source, a testing Pass and a confirmed Signal are not interchangeable.

### Monitoring is fragmented across interests and notifications

Following uses the roster/company context; Watches uses typed watchlist state; Monitoring presents tagged intelligence plus alerts/health; Watchtower derives actionable notifications from watched developments and other inputs. The existing Alerts menu item is only an anchor in Monitoring. Consolidate the entry points into one Monitor home with Watches and Alerts views, while preserving each alert's origin and review history. Favorites, tiers, lists, following, muted entities and notification rules need explicit migration mappings; they must not silently become synonyms.

### Reporting deserves one home with distinct output types

Executive Readout is a read-only synthesis. Manager Brief Pack composes selected objects; Saved Brief Packs stores the selection and re-resolves it against current data. Reports supports editable, sourced, AI-assisted draft work. Market Snapshot preserves an Explorer scope and export. War Room adds a scoped meeting workspace and session notes. Put these under Reports and Briefings, with obvious choices such as Prepare a meeting, Build a brief, Write a report and Create a market snapshot. Do not collapse a live brief, editable draft and dated export into an indistinguishable document.

### Settings is currently informational

The Settings template has no settings form, input, select or textarea. It describes defaults, shortcuts and coverage and links to Research Ops/Guide. It also describes rank-first sorting, which conflicts with the accepted newest-first experience. Move the explanatory content to Help and provide Settings only for actual editable preferences. This is the clearest mislabeled thin surface, not proof of a failed underlying service.

### A broken canonical-statement link needs repair

`/facts/fact-agrovision-peru-scale` returns 404 and there is no `/facts/{id}` GET handler in the inspected application. Timeline/commercial-position helpers contain links with this shape. The preview had also copied this shape for linked statements. This turn repaired its 174 statement source URLs to supporting Evidence pages. Production links need a separately tested repair or a deliberate canonical statement detail route; do not confuse them with feed-first `/statements` IDs. This is a concrete navigation defect, not a reason to delete Statements.

## Recommended destination structure

This is a proposed organization for review, not an implemented navigation change.

| Destination | User job | Included views or tools |
| --- | --- | --- |
| News | Read the latest relevant coverage | Newest-first feed, Trusted/Unreviewed, Saved/Reading, weekly digest, overlay Reader; advanced publication triage links to Review |
| Map Explorer | Understand where activity happens | News coverage, growing/operating regions, market figures, geographic profiles, snapshot handoff |
| Companies | Understand and track organizations | Company directory, favorites/tiers/lists, profiles, People tab, portfolio, compare; preserve non-company entity types through directory filters |
| Varieties | Understand cultivars and their footprint | Directory, profile, Growing regions, traits, rights, competition, commercial observations, compare; identity repair stays operator-only |
| Learn | Build domain understanding | Concept library and linked educational content; stays top-level as requested |
| Intelligence, under More | Investigate developments and form judgments | Landscape, Radar, Moves, observed concentration/coverage, Statements, Signals, Assessments, strategic questions, recommendations, Ask Berry |
| Monitor, under More | Track changes in chosen subjects | Following/watch interests, typed Watches, Alerts/Watchtower; explicit notification controls |
| Reports and Briefings, under More | Prepare and communicate findings | Executive readout, brief builder/library, report drafts, market snapshots, meeting workspace |
| Operations, under More | Run and inspect the intelligence pipeline | Collection, source health/configuration, coverage, review workbench, quality/identity tools; advanced/operator access only |
| Help and Settings | Understand the app and adjust real preferences | Guide, shortcuts, glossary links, editable preferences; developer component gallery excluded from ordinary navigation |

Varieties as a primary destination is a recommendation for this audit, not a silent amendment to the accepted five-item prototype navigation. An alternative is a clearly visible Companies/Varieties switch inside Entities. Decide that placement before migrating the directory family.

## Every existing section and its recommended disposition

“Combine” means share an entry point or coherent set of views. It does not mean merge stores or discard unique behavior. “Retire entry” preserves compatibility routes until their consumers are migrated.

| Existing section and route | What it actually does or what the audit found | Recommendation |
| --- | --- | --- |
| News `/today` | Default feed-first experience, cached live source items, explicit acquisition, Reader and analyst decisions. | **Keep primary.** Integrate other reading views around it; preserve newest-first and explicit freshness. |
| Following `/following` | Company roster/watch context with entity navigation; separate from typed watchlist state. | **Combine** under Monitor and company filters after following/favorite/tier semantics are reconciled. |
| Saved `/saved` | Feed-first saved-item board. | **Combine** into News → Saved/Reading; preserve saved decisions and originals. |
| Entities `/entities` | Roster-oriented directory including candidates and optional registries. | **Combine** with Companies directory, retaining verification and other entity-type filters. |
| Variety Database `/entities/variety` | Real variety workspace with competition/observation modes and canonical records. | **Keep.** Core directory, not a zombie; connect Growing regions and comparisons. |
| People `/people` | Derived professional profiles, mentions and social-coverage context. | **Embed** in company profiles as requested. Preserve person IDs/links and multi-company affiliations; remove global menu entry only after parity. |
| Statements `/statements` | Feed-first statement-review index, using private decision state. | **Keep function; combine access** in Intelligence/Review with clear statement type and review state. Do not relabel as canonical Facts. |
| Landscapes `/landscapes` | Default cross-berry competitive overview; alternate feed-statement view exists. | **Keep one Landscape home.** Reconcile the alternate view as an explicit lens, not a second unlabeled landscape. |
| This week `/week` | Digest by varieties/crop and current stored inputs, with a separate edition mode. | **Combine** under News → Weekly digest, retaining synthesis rather than substituting a seven-day filter. |
| Learn `/learn` | 27 committed concepts; browse/search plus concept detail and linked intelligence. | **Keep top-level.** Educational content is distinct from reviewing source claims. |
| War Room `/war-room` | Scoped meeting preparation composed from existing tools, with session notes. | **Move/rename** under Reports and Briefings → Meeting workspace. Preserve notes and scoped handoffs. |
| Watchtower `/watchtower` | Derived notifications for watched changes, with alert decisions. | **Combine** with Monitor → Alerts; retain notification identity and provenance. |
| Research Ops `/research-ops` | Lane/cache/coverage and Reader diagnostics, provider configuration availability. | **Combine entry** into Operations overview; keep useful diagnostic panels, hide implementation vocabulary from daily reading. |
| Settings `/settings` | Informational text, no editable settings controls in its template. | **Replace misleading entry** with actual preferences; move current content to Help and correct stale defaults. |
| How it works `/guide` | Explanatory guide. | **Keep as Help**, reconcile with Settings copy and current operating workflow. |
| Morning Brief `/brief` | Per-analyst triage and since-last-brief context; viewing marks brief-seen state. | **Combine** as a News briefing view. Preserve seen-state behavior; avoid invisible side effects when previewing a digest. |
| Live Intelligence `/work-queue` | Published/pending intelligence feed, attribution, decisions and Reader. | **Combine presentation** with News/Review; preserve advanced triage instead of duplicating a second daily homepage. |
| Review Operations `/review-ops` | Bounded review sessions, progress and queue status. | **Keep inside Operations → Review**, not daily News navigation. |
| Reading Queue `/queues/reading` | Priority/read-completion queue using analyst queue state. | **Combine UI** with Saved/Reading, preserving saved vs unread vs priority vs completed states. |
| Pending Review `/pending` | Publication candidates ready for triage/review. | **Combine entry** with Publication review as a fast-review view; keep full review detail available. |
| Signal Review `/signals/review` | Human review of proposed patterns/candidates. | **Keep distinct review stage** inside Review; share catalog context and source reader. |
| Assessments `/assessments` | Authored interpretation over intelligence, with create/edit/detail. | **Keep** under Intelligence. Sparse content does not make this redundant with Signals. |
| Strategic Questions `/strategic-questions` | Persistent research questions linked to intelligence and watch interests. | **Keep** under Intelligence/Ask Berry; a saved question is not a transient search. |
| Monitoring queue `/queues/monitoring` | Tagged intelligence, watched items, signals/candidates and operational alert context. | **Combine** into Monitor with explicit alert categories. |
| Alerts `/queues/monitoring#alerts` | Anchor within the preceding page, not an independent application. | **Retire duplicate menu entry** in favor of Monitor → Alerts tab/deep link. |
| My Watches `/watches` | Typed watchlist for company, variety, geography, berry, question and move type. | **Keep as Monitor → Watches.** Retain subject types and seen-state. |
| Source Health `/sources` | Existing health workspace and source inventory/configuration modes. | **Keep inside Operations**, with health and configuration separated by permissions. |
| Companies `/entities/company` | Canonical company catalog; overlaps roster-oriented `/entities` but uses different population/context. | **Combine into one directory** with explicit catalog/candidate coverage; preserve both identities. |
| Variety coverage `/varieties/coverage` | Coverage/identity completeness for the variety universe. | **Embed** as a Varieties coverage view with operator diagnostics in Operations. |
| Variety identity review `/varieties/candidates` | Candidate/identity adjudication; correctly denied in read-only mode. | **Keep operator-only** under Operations → Data quality. |
| Entity identity integrity `/entities/identity` | Identity/redirect audit; correctly denied in read-only mode. | **Keep operator-only** alongside variety identity, preserving distinct entity actions. |
| Map Explorer `/explorer` | Geographic selection, evidence investigation and snapshot workflow. | **Keep primary.** Statistics and region layers are additive context with separate scope semantics. |
| Geographies `/geographies` | Geographic directory with linked detail pages. | **Embed access** in Explorer; retain country/region profile URLs and evidence context. |
| Landscape `/entities/berry` | Generic Berry records catalog, not the current competitive Landscape. | **Retire misleading menu label.** Keep records/profile routes accessible through berry context or Landscape. |
| Competitor Landscape `/competitors` | Filtered competitor coverage using existing domain adapters. | **Combine** into Landscape/Companies → Compare or coverage lens after checking filter/data parity. |
| Executive Readout `/readout` | Read-only synthesis of trusted developments and interpretations for communication. | **Move** into Reports and Briefings → Executive view; retain trust labels and honest empty states. |
| Manager Brief Pack `/brief-pack` | Composes selected canonical objects into a presentation; URL can carry selection. | **Keep builder** under Reports and Briefings. |
| Saved Brief Packs `/brief-packs` | Library of saved selections, resolved against current data on reopening. | **Combine** into the same Briefs library. Label live briefs separately from historical exports. |
| AI-Assisted Reports `/reports` | Draft report library/workspace with source packets and export. | **Keep** under Reports and Briefings; drafting is not an approval/trust action. |
| Intake `/intake` | Explicit manual source/file entry into reviewable drafts. | **Keep** as Operations → Add source material, available contextually from News. |
| Publications `/review?kind=publication` | Source-publication review within the workbench. | **Keep stage**, combine queue navigation with Pending and review sessions. |
| Claims `/review?kind=atomic` | Source-centered atomic proposition proposals and decisions. | **Rename for clarity** inside Review; keep distinct from source-publication and Claim Testing decisions. |
| Source fidelity `/source-fidelity` | Recovered-body authenticity/identity checks with consequential actions. | **Keep distinct quality step** inside Operations; do not fold into proposition approval. |
| Collection Operations `/collection-ops` | Existing collection-run status, failures and explicit bounded run action. | **Keep tab** in Operations; opening the page must not collect. |
| Coverage Assurance `/coverage-assurance` | Reconciles intended/known/collected/excluded coverage; operator-only. | **Keep tab** in Operations; distinguish missing coverage from healthy quiet sources. |
| Claim testing `/queues/testing` | Testing disposition on tagged published claims/evidence. | **Keep** under Review/Intelligence as appropriate; Pass does not create a Fact. |
| Signal catalog `/signals` | Stored Signals with detail/create flows; currently six proposed records. | **Keep** in Intelligence, with Signal Review adjacent. Do not call proposed signals confirmed. |
| Newsfeed `/` | Default redirects to News; query-bearing requests retain a historical published feed. | **Retire duplicate entry**, preserve/translate filtered bookmarks before retiring renderer. |
| Commercial positions `/queues/commercial_position` | Company-grouped evidence inventory, not a Position object or score. | **Embed** as Companies/Intelligence commercial view; preserve classifications and evidence links. |
| Recommendations `/recommendations` | Action proposals connected to Assessments and decisions. | **Keep** under Intelligence/Reports, distinct from evidence and interpretation. |

## Additional sections missing from the first inventory

| Section and route | Finding | Recommendation |
| --- | --- | --- |
| Front Page `/news` | Separate edition-oriented news renderer over existing evidence and pending inputs. | Consolidation candidate for News → edition/briefing view; compare with `/today` before retiring it. |
| Industry Pulse `/industry-pulse` | Cached external-discovery status and newsroom/provider context; operator-only in current routing. | Operations → Discovery/coverage; do not silently make its private data public. |
| Ask Berry `/research` | Question/scope interface to existing intelligence plus explicitly requested live research. | Keep prominent contextual access under Intelligence; preserve provider/data-export boundaries. |
| Radar `/radar` | Emerging developments derived from stored/provider cache, with details and live-refresh route. | Intelligence → Developments; unify reading/handoff components with News, not its derived state with source articles. |
| Moves `/moves` | Company move classifications derived over Radar developments, including company detail. | A company-focused lens under Intelligence/Companies; preserve derivation and source identity. |
| Whitespace `/whitespace` | Observed concentration versus low activity/low coverage, plus scoped report handoff. | Landscape → Coverage and concentration. Rename to avoid suggesting that absent data proves an opportunity. |
| Search `/search` | Cross-object global search, also available in an overlay/API. | One persistent global search; keep full results route, avoid a competing silo. |
| Design System `/design-system` | Developer fixture/component gallery. | Keep developer-only and exclude from normal product navigation; it is not a customer feature to redesign. |

The navigation preservation inventory is expanded with these entries. The prototype menu is intentionally not expanded during this audit; the next IA decision should reduce fragmentation rather than add another group of links.

## Detail and alternate surfaces that must survive consolidation

| Surface | Required preservation |
| --- | --- |
| Company living dossier and `?view=legacy` | Current living dossier already calls `build_company_backbone`; the older architecture report's missing-backbone finding is not current evidence here. Compare linked relationships, portfolio, facts and history before retiring the legacy view. |
| Company/variety Compare; company Portfolio | Keep comparison selection, role distinctions and canonical entity IDs. They are contextual tasks, not extra top-level destinations. |
| Variety `?view=compete` and `?view=observations` | Preserve trait/rights/competition views separately from commercial observations; retailer location is not Growing region. |
| Landscape per-berry and `?view=feed` | Preserve cross-berry and berry-scoped exploration. Clearly label feed statement coverage versus canonical synthesis. |
| Geography detail | Keep source-linked country/region intelligence and links from statistics/maps. |
| Evidence, Intelligence Reader, Story Thread | Reuse the Reader presentation while preserving public Evidence, private pending items and thread identity. A group of reprints is not independent corroboration. |
| Review detail/batch/session and `/review-ops/publications` | The durable publication read-model/rehearsal route is a migration surface with its own gating, not a third production approval queue to advertise. Preserve the authoritative command path and compatibility until migration is complete. |
| Explorer snapshot and PDF; report workspace/PDF; Brief presentation | Preserve scope and provenance through composition/export. Binary exports were not executed in this section audit. |
| Live refresh routes, company Pulse, attachments, APIs, forms, login | They are actions/detail/infrastructure endpoints, not proposed navigation sections. The route registry preserves the inventory; do not invoke acquisition merely to test page rendering. |

## Zombie page assessment

**Confirmed navigation redundancy:** Newsfeed's no-query redirect; Alerts as an anchor; the legacy Berry catalog mislabeled Landscape; separate access to Brief creation and its saved-library family. These are candidates to remove from the main menu once the intended home exists.

**Thin or misleading surface:** Settings has explanatory copy but no preferences UI. Replace or relabel it before applying a polished settings design.

**Conditional retirement candidates:** older Today briefing, Front Page, legacy filtered feed, legacy company profile, feed-oriented Landscape and the publication-review rehearsal/read-model surface. They have working code or migration purpose. Retire only when parity and current ownership are established; do not infer abandonment from the word legacy alone.

**Not established as zombies:** Radar, Moves, Whitespace, War Room, Learn, Statements, Signals, Assessments, Recommendations and specialist review tools. They have identifiable jobs and implementations. Committed data currently includes 1,269 published Evidence records, 176 active and 10 disputed Facts, six proposed Signals, five active Assessments, four active Recommendations, nine active Strategic Questions and 27 learning concepts. These counts describe stored records, not adoption, quality or complete industry coverage. Empty private reports/queues in a clean runtime are not meaningful abandonment evidence.

No empirical abandonment verdict is justified without a representative real workflow or usage history. Since the user has barely used the app, the better acceptance exercise is to perform a few complete jobs and see which surfaces are necessary, not require the user to defend features by remembered usage.

## Implementation order and decision gates

1. **Freeze broad page reskinning.** Keep approved prototype refinements, but use this audit to select page families before migrating them.
2. **Approve the destination map and terminology.** Decide top-level Varieties versus a visible directory switch; agree on News, Monitor, Intelligence, Reports and Operations jobs. Rename misleading labels before layout work.
3. **Document state mappings before combining workflows.** Feed saves vs reading dispositions; favorites/tiers/lists vs watches/mutes; feed statements vs canonical Facts; notifications vs signal review; live brief selections vs report drafts/exports. Preserve identifiers, history and privacy.
4. **Repair verified broken links and establish one navigation manifest.** Preserve old URLs with redirects/query translation where valid, and retain permission/static-build exclusions. Verify the `/facts/...` consumers before choosing their replacement.
5. **Run five end-to-end acceptance jobs:** read/save/revisit an article; follow a company and see a relevant change; inspect a variety and its growing-region evidence; turn a reviewed finding into a brief/export; review a source and a proposition without conflating their decisions. Add a Learn concept detour from a relevant variety/story. Use realistic sparse and unavailable states.
6. **Migrate one family at a time.** Start News/Reader and directory/Explorer, then Monitor and Reports, then Intelligence and Operations. Retire redundant menu entries only after the retained workflow is demonstrated. Review Learn as a distinct primary experience.

Each retirement needs a named replacement, behavior/data checklist, bookmark migration, role/public-build checks, tests for state continuity, and an accessible path for the less frequent specialist task. No production pages should be removed merely because the prototype does not display them.

## Source references

- Navigation: `app/services/feed_first.py::NAV`, `app/templates/_v2_sidebar.html`, `app/templates/_stakeholder_nav.html`; [updated inventory](DESIGN-NAVIGATION-INVENTORY.md).
- Default/legacy feed: `app/main.py::home`, `_feed_first_today`, `today_page`; state distinctions in `app/services/feed_first.py`, `analyst_queue.py`, `watchlist.py`.
- Statements/review: `app/main.py::statements_page`, `review_queue`, `source_fidelity_queue`, `priority_queue`, `signal_candidate_review`, `publication_review_readonly_page`.
- Dossiers: `app/main.py::_feed_first_company_response`, `entity_detail`; `app/services/entity_dossier.py`, `company_workspace.py`, `variety_footprint.py`.
- Specialist purpose: `app/services/watchtower/__init__.py`, `war_room/__init__.py`, `research_desk.py`, `competitive_moves/__init__.py`, `whitespace_radar.py`, `executive_readout.py`, `brief_pack.py`, `saved_brief_packs.py`.
- Settings: `app/templates/feed_first_settings.html`. Broken Fact links: `app/queries/timeline.py`, `app/services/commercial_positions.py`; reproduced in the render results.
- Governing limits: [expansion guide](INTELLIGENCE-EXPANSION-BUILD-GUIDE.md), [design mission](IMMERSIVE-DESIGN-MISSION.md), [design review audit](DESIGN-REVIEW-AUDIT.md), `AGENTS.md`. Older architecture/status documents were checked against current code rather than assumed current.
