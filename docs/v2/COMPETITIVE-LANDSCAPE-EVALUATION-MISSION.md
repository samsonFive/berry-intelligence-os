# Berry Intelligence OS Competitive Landscape Evaluation

## Purpose and execution order

Build a sourced competitive landscape evaluation feature for the full berry-industry ecosystem. Compare breeders, growers, marketers and technology providers within appropriate peer groups; connect those groups through ownership, licensing, supply and technology relationships. Evaluate capabilities by company, berry and market, with a company-wide overview.

This is a two-stage Codex mission. Stage 1 produces the actual commercial-entity inventory and then generates ready-to-run Perplexity research prompts from that inventory. Johnny runs those prompts manually and returns the results. Stage 2 validates and imports the research, populates the landscape and delivers the application feature.

The repository and its current data were not inspected when this brief was authored. Discover the actual implementation, registry and available interfaces before making changes. Do not treat historical entity counts or example company groupings as current research results.

## Decisions confirmed with Johnny

| Decision | Requirement |
|---|---|
| Entity universe | Full ecosystem, with separate peer comparisons for breeders, growers, marketers and technology providers. |
| Multiple business roles | One canonical entity may participate in several role-specific comparisons. |
| Evaluation | Capability-by-capability ratings with evidence and confidence. No combined overall competitiveness score. |
| Assessment scope | Company × berry × market, plus a company overview. Production origins and destination markets are distinct. |
| Rating behavior | Stable capability rubrics. Changing the selected competitors changes relative peer position, not the underlying capability rating. |
| Research workflow | Codex supplies the entity list first, then generates the Perplexity prompts. Johnny runs them and returns the results. |
| People and hiring | Include key people, job listings, recent hires and relevant leadership changes in entity evaluations. |
| News in every view | Every competitor and landscape view must include a newsfeed-style view of captured articles relevant to the companies, berries and markets under comparison. |
| Initial publication | Show automatic provisional ratings immediately after evidence import and assessment. No analyst approval is required for initial provisional visibility. |
| Analyst control | Johnny can review and correct assessments. Corrections persist and changes remain traceable. |

The defaults below make these decisions implementable. Where a default needs refinement after repository inspection, document the reason; preserve the confirmed behavior.

## Stage 1 — Entity inventory and research handoff

### 1. Inspect and reconcile the real entity universe

Read repository instructions and inspect the canonical entity registry, dossiers, crop/market taxonomy, existing landscapes, evidence/claim model and data imports. Produce an inventory from current records before generating entity-specific research prompts. Reconcile duplicates and aliases using evidence; preserve canonical IDs and existing links.

Inventory fields must include:

- Canonical entity ID, display name, legal name where known, aliases and official domain when established.
- Parent, subsidiary, joint venture, brand and cooperative relationships, distinguishing entity types and unresolved identities.
- Primary and secondary roles, with evidence/status: breeder, grower, marketer, technology provider, nursery/propagator and other relevant ecosystem roles.
- Known berry coverage, production origins and destination markets, including the scope and date of supporting evidence.
- Existing dossier/evidence links, last researched date, gaps and suggested research priority.
- Inclusion status: existing in-scope entity, candidate addition, duplicate candidate, unresolved identity, or out of scope with a reason.

Retain relevant actors such as nurseries, logistics providers and buyers as ecosystem nodes. Give them distinct role/subgroup labels rather than forcing them into an unsuitable core rubric. The initial rated peer groups are the four specified above; add a further rated group only with a coherent, documented capability rubric.

Allow an entity to be both a breeder and a marketer. Do not duplicate it as two companies, double-count a parent's and subsidiary's production, or attribute all group capabilities to every brand. A brand may link to its operating entity while retaining evidence specific to the brand. Distinguish owned operations, contracted growers, licensed production and sourcing relationships.

Use strawberry, blueberry, raspberry and blackberry as the initial crop scope, mapped to the repository's actual identifiers. Research globally and preserve country detail under existing regions. Do not fabricate every possible company/crop/market combination: instantiate supported scopes and record unknown coverage explicitly.

Present the resolved inventory and unresolved candidates first. Generate the subsequent prompts from a versioned inventory snapshot. No extra permission round is necessary for routine identity reconciliation supported by evidence. Truly unresolved identities remain marked rather than guessed.

### 2. Define the evidence and rubric contracts before generating prompts

Use the capability specification later in this brief to establish a versioned rubric catalogue. The research prompts must collect the observations needed to apply those rubrics, not simply ask Perplexity to rate competitors. Preserve stable entity and capability IDs in the handoff.

Separate:

1. Observed facts or measured outcomes.
2. Company-attributed claims and announced plans.
3. Analyst interpretations and hypotheses.
4. Derived capability assessments.

For each observation, require entity, role, berry, market, origin if relevant, capability/metric, value or concise statement, unit/denominator, applicable period, source URL, source publisher/title/date, supporting passage and stated limitations. Use null/Unknown for missing values. An explicit global or multi-crop claim is different from unspecified scope.

For numerical comparisons, preserve actual versus forecast/target/capacity, area versus volume versus revenue, currency, fiscal/calendar period, production system and fresh versus processing use. Organic share must identify its denominator; it is descriptive information, not automatically evidence of superior competitiveness.

### 3. Generate the Perplexity prompt pack from the inventory

Codex must author the actual prompts after the inventory exists. This brief is a prompt-generation specification, not a completed research prompt for an invented company list.

Deliver a master instruction block plus fully populated entity/batch prompts that Johnny can paste directly into Perplexity. Include entity IDs, names, resolved domains, aliases, applicable roles, known scope, specific research questions and the exact return format. Avoid placeholders that make Johnny manually reconstruct the inventory.

Use manageable batches, normally three to five entities with related roles, or a dedicated prompt for a complex group. Provide a clear run order and coverage checklist. If the actual inventory is large, stage the batches while preserving the full inventory and explicitly showing what remains; do not quietly reduce the task to a handful of companies. Include cross-company reconciliation and gap-follow-up prompts after the profile batches.

Every generated prompt must instruct Perplexity to:

- Conduct deep, multi-pass public-source research as of the execution date; give every listed entity its own coverage, including explicit gaps.
- Resolve identities and corporate relationships before attaching claims. Preserve the supplied entity IDs and flag possible additions separately.
- Research applicable capabilities by berry and destination market, recording growing origins and the nature of access/control separately.
- Distinguish genetic ownership, exclusive or nonexclusive licenses, public germplasm and access through commercial supply relationships. Do not assume that genetic access proves IP ownership.
- Investigate varietal/trait differentiation, commercialization, production and sourcing, supply windows, protected growing systems, postharvest operations, channels/customer access, brands and consumer proposition as applicable to the entity's role.
- Include organic production, sustainability and mechanical/robotic harvesting evidence where relevant. Distinguish research, pilot, commercial deployment and repeat deployment; distinguish fresh-market and processing applications. State shelf-life test conditions rather than repeating context-free performance numbers.
- Research key people, vacancies and recent hires using the people/jobs contract below. Cover current publicly supported roles and a default 24-month hiring/leadership-change window, retaining older context only when it explains a material capability. Confirm any claimed current status as of the search.
- Record value-chain partnerships, named programs, varieties, technologies and applicable geographic rights with dated original sources. Co-mention alone is not a relationship.
- Investigate company-specific exposure to political, economic, social, technological, environmental and legal factors through its actual operating footprint. Identify the relevant origin/market, mechanism, time horizon and supporting evidence; do not copy a generic industry PESTEL paragraph into every profile.
- Prefer original company/partner announcements, breeders/universities, research publications, official records, careers pages and credible reporting. Search relevant local languages. Preserve original names and source titles alongside translations where useful.
- Open the cited pages where possible. Cite original URLs, not only search snippets or Perplexity's answer page. Mark unavailable sources and disagreements. Syndicated copies of one announcement are not independent corroboration.
- Treat promotional claims as attributed claims; never invent revenues, headcounts, customer lists, market shares, volumes or organic percentages to complete a table.
- Produce cited observations and evidence gaps. Do not substitute an unsupported overall ranking, opaque capability score or industry leadership label for evidence.

Specify this return structure in every prompt:

1. Batch metadata: batch ID, inventory version, research date, included entity IDs and coverage summary.
2. Per-entity concise profile and role/scope table.
3. Capability evidence ledger, with one identifiable observation per row and source IDs.
4. Corporate and value-chain relationship table with type, direction, scope, dates and evidence.
5. Key people table, job-listings table and hiring/leadership-events table.
6. Company-specific external exposures and reported mitigations, where evidenced.
7. Source ledger with original URLs, dates and supporting passages.
8. Conflicts, unknowns, unverified leads and proposed follow-up queries.

Require readable Markdown tables with stable IDs as the baseline. If structured JSON is requested as an additional export, provide a validated schema and allow the Markdown return to be imported when Perplexity does not emit valid JSON. Do not make successful research depend on a huge, perfectly formed JSON response. Preserve numeric values and unknowns faithfully during conversion.

Prompts should contain the public entity inventory and research instructions; exclude credentials and private analyst notes. Do not run Perplexity automatically or spend API credits for this manual handoff. Ordinary source inspection needed to verify identities and later returned citations remains part of Codex's work.

### 4. Stage 1 deliverables and handoff

Deliver the readable entity inventory plus structured inventory, versioned capability/rubric catalogue, ready-to-paste Perplexity prompt pack, coverage checklist and return/import instructions. Suggested repository artifact names are `commercial-entity-inventory`, `capability-rubrics`, `perplexity-research-prompts`, and `research-return-contract`, with formats consistent with the repository.

Then hand the research stage to Johnny. The handoff must explicitly say that research and population are pending returned results. Do not invent findings to make the UI look complete. Independent schema or component groundwork may be prepared within the mission, but evidence-dependent scoring and completion claims wait for returned research. When results arrive, resume Stage 2 rather than regenerating or replacing the inventory without explanation.

## Stage 2 — Import research and implement the landscape

### 5. Validate and persist the returned research

Keep each original research return with its batch ID, inventory version and research date. Parse into candidate records; validate entity IDs, scope, dates, units, relationship direction and source references before assigning ratings. Show a clear import summary with accepted, unresolved, conflicting and failed items. A malformed row must not silently disappear or corrupt the whole batch.

Inspect original sources supporting material capability and people/hiring claims. Distinguish source inspected, source inaccessible, claim explicitly supported, company assertion and conflicting evidence. Perplexity citations are leads to validate, not automatic verification. Unsupported or ambiguous claims may remain as research leads but cannot justify a concrete rating anchor.

Upsert using stable IDs and canonical source identities. Reimporting the same batch is idempotent; a later batch can add evidence or supersede a dated observation without erasing history. Preserve analyst notes, corrections and canonical entity identities. Route unresolved company/person matches to a visible resolution list rather than guessing.

Persist the usable records in the application's actual data model and retrieval/read models. Evidence should be accessible from entity dossiers, relevant landscape cells and existing knowledge-base/workspace interfaces. Preserve the system's existing unverified-claim semantics; a provisional assessment is separate from a claim's verification status.

### 6. Capability catalogue and rating rules

Implement stable, role-specific rubrics. Use a five-level ordinal scale as the initial design default, with a meaningful label and explicit evidence requirements for each capability level. Unknown and Not applicable are separate unscored states. An applicable capability with unknown evidence is not N/A. Lack of public disclosure is not proof of weak capability.

Each capability definition must specify its ID, eligible peer roles, business question, scope, evidence fields, units/periods if numerical, level anchors, sufficient evidence threshold, confidence rules and rubric version. Define the anchors before applying them to companies. Avoid vague scores such as "innovation: 4" with no observable basis.

Use the following catalogue as the starting point. Refine overlapping dimensions during implementation without dropping the information needed for the comparison.

| Peer group | Capability families | Evidence to request and distinguish |
|---|---|---|
| Breeders | Breeding/program capability; trait differentiation; commercialization; genetic control/access; licensing and deployment reach | Named programs and varieties, measured trial results, releases/adoption, relevant IP or license rights, active territories and commercial partners. |
| Growers | Production capability; supply-window coverage; origin flexibility; growing-system capability; postharvest capability; operating resilience | Actual production versus targets, origins and crop calendars, owned/contracted operations, protected/substrate systems, handling practices and outcomes, evidenced mitigations and constraints. |
| Marketers | Supply continuity; sourcing network; channel/market access; product and consumer proposition; commercial deployment | Monthly market-facing availability, evidenced supplier arrangements, customer/channel presence, programs and brands, commercial listings and supported quality/consumer evidence. |
| Technology providers | Technical maturity; validated crop applicability; deployment/adoption; integration and delivery capability; relevant IP/access | Research versus field/operational validation, commercial pilots versus repeat deployments, tested versus intended crops, customer/partner evidence, delivery footprint and applicable rights. |

People, hiring, financing and partnerships provide evidence or directional context for relevant capabilities. Do not reward vacancy volume or headcount by itself. Financial resilience can only be assessed where comparable financial evidence supports a defined rubric; otherwise show the available observations and gaps.

Useful additional raw fields include production area/volume, supply months, market presence, organic mix, certifications, technology adoption, named traits, consumer propositions and cold-chain arrangements. Display facts where numerical ranking would be misleading. Owning more of the value chain is not inherently superior for every business model: preserve the access/control model separately from demonstrated capability.

For example, a market-specific annual supply-coverage rubric may use documented months: level 1 = 1–3 months, 2 = 4–6, 3 = 7–9, 4 = 10–11, 5 = 12. Label this as coverage rather than overall supply quality; volume, reliability and service performance require separate evidence. Missing coverage remains Unknown. Use this only where period, crop and destination are established; do not infer twelve months from a generic claim of a global presence.

A technology-maturity rubric should distinguish concept, controlled validation, relevant operational trials, documented commercial deployment and repeated deployment. Write concrete anchor requirements adapted to the technology type. Do not collapse a company with several programs into the maturity of its most advanced program across every crop/market.

Rating calculation or assessment must use the versioned anchors and cited evidence. If AI assists interpretation, persist its rationale and make the mapping to an anchor inspectable; selecting a different comparison cohort must never trigger an arbitrary rescore. Numeric fact extraction, model suggestions and deterministic rubric application should be separable wherever practical.

### 7. Confidence, provisional visibility and analyst corrections

Each assessment records entity, peer role, berry, market, capability, rating or unscored state, rationale, supporting/contradicting evidence, assessment date, rubric version, confidence and review status.

Confidence describes evidence support for that scoped rating. Use a transparent High/Medium/Low scheme as an initial default: consider source directness, independence, recency, scope fit, methodological detail and agreement. This is an evidence assessment, not an LLM's self-reported probability. A strong rating can have limited confidence; a modest rating can be well supported. If evidence cannot select an anchor, use Unknown rather than a speculative low-confidence number.

Once validated imported evidence supports an assessment, automatically display it as Provisional. Johnny can inspect the rationale/sources, mark it reviewed, correct its scope or rating, append an explanation and restore automatic assessment where desired. Initial provisional visibility is explicitly authorized and must not be blocked behind a manual publication queue.

Maintain separate automatic and analyst decision histories. Analyst overrides take priority and survive imports, source updates and classifier reruns. New evidence can update unreviewed provisional assessments; changes affecting reviewed or overridden assessments should appear as a new proposal or evidence-update indicator while preserving the analyst decision. Record whether a change reflects new capability evidence, a corrected observation or a revised rubric.

Expose evidence age and stale/conflicting status. Define freshness by field: a job vacancy needs a recent observation, whereas an old but still applicable IP relationship may need a different review interval. Aging alone must not silently turn an unknown capability into a low score. This mission does not create an external scheduled research task.

### 8. Key people, vacancies and organizational changes

Include a People and Hiring section on entity profiles and a comparable timeline/filter view across selected peers. Research key executives, breeders/scientists, technology leads, commercial leaders and regional heads. Track relevant public professional experience and documented responsibilities without attempting to build unrelated personal profiles.

People records must retain a stable identity, name, employer/entity link, role/title, function, applicable program/crop/market where evidenced, current or historical status, effective dates when available, observation date and source links. Distinguish employees, directors, advisors and external collaborators. A former role on an old biography is not proof of current employment. Resolve same-name individuals before merging records.

Job records must include employer/entity, original careers/ATS URL, requisition ID where available, title, function, location/remote scope, seniority, relevant skills/technologies, crop/program if explicit, published date if known, first/last observed dates, observed status and supporting text. Preserve unknown headcount; one posting may concern more than one vacancy, and identical reposts may concern the same opening. Deduplicate by stable job identity and posting history, not title alone.

Hiring/leadership events record person, organization, event type, new and previous professional role where sourced, announced versus effective date, geographic/program scope and original evidence. Keep a vacancy, an announced hire and a completed role change as distinct records that may be linked when evidence supports the connection. A removed or expired posting does not prove a hire was made.

Connect people and hiring signals to relevant capabilities and show the reasoning. Hiring an automation specialist may indicate investment intent; it does not establish deployed automated harvesting. Job volume can be distorted by source coverage, seasonal recruiting and reposts, so show observation coverage and distinguish unique observed postings from total employee growth. Absence of observed vacancies is an information gap, not evidence that a company is inactive.

The default research window is current public roles/vacancies plus 24 months of hiring and leadership events, editable for follow-up research. Job and role status is last observed, not guaranteed live. Support importing later manual Perplexity returns and capturing relevant existing news articles into this timeline without duplicating the underlying sources.

### 9. Comparison, strategic maps and company overview

Integrate into the existing competitor/entity and Landscape Explorer navigation. Reuse shared entity, variety, crop and market identities; provide one coherent data model and linked views.

Required views:

- Capability matrix: select a peer role, berry, market and companies; inspect scoped capability cells with rating, confidence, provisional/reviewed status, evidence age and raw values where available. Clicking a cell opens its rubric, rationale and evidence, with review/correction actions.
- Company overview: summarize roles, capabilities, operating model, supply/access relationships and berry/market coverage. Show which scopes support each summary and what remains unknown. A maximum score in one market or an average over sparse data must not become an unsupported global score.
- Strategic group plot: selectable axes using compatible scoped metrics/capabilities. Offer supply-window coverage versus genetic control/access where appropriate, with clear axis definitions. Use categorical positioning when a control/access model has no defensible numerical ordering. Do not hardcode companies into "global titan" or other clusters from the supplied background.
- Value-chain relationship view: connect breeders, nurseries, growers, marketers, technology providers and relevant supporting actors. Preserve edge type, direction, scope, dates, direct evidence and hypotheses as distinct. Reuse existing hypothesis styling and exclude speculative links from demonstrated-capability scoring.
- External-exposure view: company-specific PESTEL exposures linked to operating origins, markets, dependencies and supporting evidence; keep exposure and demonstrated mitigation separate. Source and date policy claims. A headquarters location alone does not establish operating exposure.
- People and Hiring view: key people, current observed jobs and dated organizational changes, with relevant capability/program links.
- News and Evidence feed: a captured-article feed available inside every competitor and landscape view, as specified below.

Relative peer position must be calculated per capability only among eligible records with compatible role, crop, market, period and rubric version. Show the cohort definition, size, coverage and ties. Unknown/N/A records do not silently become bottom-ranked companies. For small or poorly covered groups, show the compared observations and coverage instead of a spurious percentile. Do not label a selected-cohort position as a ranking of the entire industry.

Changing selected competitors changes the peer comparison and feed scope but not an existing capability rating. Retain assessment history so the user can distinguish evidence updates, actual observed capability developments and methodology changes. Never combine the ratings into an overall competitiveness leaderboard.

Allow saving a comparison and exporting a cited matrix/landscape snapshot through existing facilities. Preserve selected entities, role/crop/market filters, assessment dates, rubric versions, statuses and source list. If a briefing is generated, retain distinctions between reported facts, provisional assessments, hypotheses and analyst conclusions. Reuse the living-workspace capture and narrative functions where implemented.

### 10. Captured newsfeed in every competitor and landscape view

This is a mandatory integration requirement, including existing relevant views, not merely a new standalone news page. Inventory the current competitor/entity detail, comparison and landscape routes. Add a reusable newsfeed component or directly accessible feed tab/panel within each view and deliver a route-by-route verification checklist. It should be readily visible and usable alongside evaluation work, with an appropriate layout on narrow screens.

The default source is the application's existing captured news archive. Reuse canonical article records and the normal reader. This feed is distinct from the manual Perplexity research handoff; do not initiate paid web/deep-research jobs merely because a user opens a comparison. Newly imported research sources may join the feed through the established article-capture process when appropriate, with provenance and dates intact.

The feed inherits the current comparison context and updates when selected companies, berry or market change. Relevance must support:

1. Company coverage: articles concerning any of the selected entities, with applicable berry/market scope. Selecting several companies must not require every company to appear in the same article. Offer a useful way to focus on one selected company or shared/multiple-company coverage.
2. Market context: articles relevant to the selected berry and destination market even if no selected company is named. Make these recognizable as market context and allow a company-only filter.
3. Connected developments: cross-geography or enabling developments with an explicit relevant variety, program, technology/IP platform or commercial relationship. Explain the connection. Do not use a broad parent-company mention as proof that an unrelated foreign-market story affects the selected market.

Offer All relevant, Company coverage and Market context filters, or equivalent clear controls. Distinguish operating origin from destination market. Do not fabricate crop/market relevance for articles whose scope is unknown; label global/unspecified context appropriately and keep unrelated material out of the default results.

Display title, image where already available, publisher, publication date, short excerpt, matched companies/markets and existing tags. Explain why each result is included. Sort by actual publication date by default and allow date filtering. Preserve event and first-seen dates separately so an old source newly captured does not look like today's development. Do not silently inherit a Today-only filter from another part of the app.

Deduplicate canonical articles and group syndicated copies using existing newsfeed behavior. Search/filter the full accessible archive before pagination, not only loaded cards. Retain state when opening an article and returning. Reuse the newsfeed Tags behavior, including All/Any semantics within the tag filter group; selected company matching uses its own explicit semantics above.

Actions must include reading in-app, opening the original source and saving/featuring/capturing into a workspace where those capabilities exist. Linking a passage as evidence for a capability should preserve the original article and claim status. Display existing links to relevant assessments or hiring events where available. Ordinary vacancies need not appear as news articles; keep job records in People and Hiring, with article-based hiring announcements discoverable in both views.

As ingestion adds matching captured articles, update the feed through the existing refresh mechanism without disrupting the current reading position. New coverage may flag an assessment for reconsideration, but it does not silently override analyst-reviewed ratings or rewrite saved comparison narratives.

Use honest empty states: no captured matches, incomplete article indexing, and a retrieval failure are different states. Offer clearing/widening filters or an explicit research action when available. Do not fill an empty feed with unrelated stories or fabricated demo news.

### 11. Data integrity and integration boundaries

Extend the existing storage and services rather than creating a detached comparison database or duplicate entity registry. Minimum logical records include entity roles, scoped observations, evidence sources, relationship edges, people/employment observations, jobs/status history, hiring events, capability definitions, assessments/revisions/overrides, research batches and saved comparisons. Adapt these concepts to the repository's actual schema.

Use separate, explicit values for Unknown, Not applicable, global scope and unspecified scope. Retain parent/group relationships without inheriting all facts automatically. Make evidence and import links portable so users can trace any displayed cell back to the original returned research and its cited public source.

Coordinate with the Gene Editing Landscape, Search and Research Quality, Newsfeed Tags, and Analyst Living Workspaces work where present. The shared newsfeed component and canonical tags must work across existing and new competitor/landscape surfaces. Preserve source-selection boundaries for reports; a linked feed is not permission to silently add every feed result into a selected-source briefing.

Durable edits, import jobs and assessment updates must respect existing authentication, authorization, revision guards and backend persistence. Make retries idempotent, retain clear success/error states and handle concurrent manual edits without overwriting them. Use existing provider configuration and model budget controls for source checking and assessment assistance; do not create a new recurring research subscription.

Implement in reviewable increments: inventory/contracts/prompts; validated import and scoped storage; provisional scoring/corrections; comparison and ecosystem views; people/hiring and feeds; export and integrated verification. All required features remain part of Stage 2 completion. Do not substitute mock-only data or mark the overall mission complete at the research-handoff checkpoint.

## Acceptance and delivery

### Stage 1 acceptance

1. An inventory derived from the actual registry appears before generated entity-specific prompts, with stable IDs, multi-role classification, parent/brand distinctions and unresolved candidates.
2. Ready-to-paste Perplexity prompts contain actual inventoried entities, role-relevant questions, company/berry/market scope, people/jobs/hire requirements and original-source citation instructions.
3. The return format is importable, preserves unknowns and dates, and supports human-readable Perplexity output without requiring manual re-entry of every fact.
4. Johnny receives a clear run order, coverage checklist and return instructions. Codex has not automatically run the manual Perplexity stage or claimed pending research as complete.

### Stage 2 acceptance scenarios

| Scenario | Required demonstration |
|---|---|
| Returned research import | Import a real returned batch and inspect accepted records, source checks, conflicts and unresolved mappings. Reimport without duplicates. |
| Ecosystem coverage | Show real sourced records from all four rated peer groups when returned research supports them; explicitly report missing groups rather than invent data. |
| Multi-role entity | One canonical company appears in its applicable peer groups with appropriate rubrics and no duplicate identity. |
| Scope separation | A blueberry capability in one market does not become a raspberry capability or a different-market rating without evidence. |
| Provisional visibility | Supported assessments appear immediately as Provisional with evidence, rationale, confidence, date and rubric version. |
| Unknown and N/A | Missing evidence stays Unknown; structurally irrelevant capabilities use N/A; neither is treated as a low numeric score. |
| Stable ratings | Change the selected peer cohort; underlying capability ratings remain identical while compatible peer positions update. |
| Analyst correction | Override a rating, then import conflicting/new research and run assessment again; preserve the override and expose the new evidence/proposal. |
| People identity | Inspect a current/historical professional role with source and observation dates; demonstrate disambiguation rather than merging by name alone. |
| Hiring signals | Deduplicate a reposted job, retain status history, and show that vacancy disappearance is not counted as a completed hire or deployed capability. |
| Maps and exposure | Plot only supported or explicitly marked unknown/hypothetical positions and relationships; inspect evidence and relevant crop/market/origin scope. |
| Feed in every view | Verify every inventoried competitor and landscape route has an in-view captured-article feed or directly accessible feed panel/tab. |
| Feed relevance | Compare two entities and one berry/market; retrieve articles on either company and labeled market context, exclude unrelated stories and explain relevant connected developments. |
| Feed context changes | Change company, berry, market, date or tags and observe correct full-archive filtering/pagination; article navigation preserves comparison state. |
| New captured news | Ingest a matching article and observe it in the corresponding views using the normal refresh path; preserve true publication date and deduplicate repeated ingestion. |
| Cited export | Save/export a comparison and verify its scope, sources, dates, provisional/reviewed statuses and rubric versions remain visible. |
| Historical changes | Distinguish a new observation, changed capability evidence, revised rubric and analyst override in assessment history. |
| Failure recovery | Handle incomplete research, inaccessible citations, failed background jobs and stale edits honestly without inventing scores, articles or source verification. |

Use focused unit/integration tests for scope keys, rubric anchors, peer eligibility, correction precedence, identity resolution, job deduplication, import idempotency and feed matching. Use browser verification of the actual workflow and existing shared-reader behavior, including narrow-screen and keyboard use. Separate deterministic fixtures from the real returned-data demonstration.

Stage 2 delivery must include a focused PR/branch, working preview, migrations/import instructions, coverage counts and gaps by role/crop/market, relevant tests, the feed route checklist and a short walkthrough. Show a real company comparison, cell evidence, a preserved analyst correction, people/hiring signals and captured articles relevant to that comparison. Follow the existing release process; this brief calls for a reviewable implementation and does not itself authorize production deployment.
