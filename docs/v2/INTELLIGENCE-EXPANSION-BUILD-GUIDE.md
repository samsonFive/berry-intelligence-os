# Berry Intelligence OS — Intelligence Expansion & Technical-Debt Build Guide

**Status:** Governing build guide for the next development phase  
**Recommended repository path:** `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`  
**Scope:** Global competitive-intelligence coverage, variety intelligence, source expansion, market observation, technical-debt reduction, and production-readiness across strawberry, blueberry, raspberry, and blackberry.

---

## 1. Purpose

Berry Intelligence OS has moved beyond the prototype stage. The core platform can now ingest public intelligence, preserve provenance, separate pending from trusted intelligence, group related coverage into Story Threads, propose evidence-backed Signals, and support analyst-controlled review. The platform has also demonstrated that its core domain model is genuinely multi-berry: Blueberry is the original reference vertical, Strawberry is now a usable second vertical, and Raspberry has demonstrated that domain expansion can be largely data/configuration work rather than another architecture project.

The next development phase must therefore stop being organized as a sequence of isolated feature requests. It must be managed as a deliberate expansion program with two equal objectives:

1. **Increase intelligence depth and recall** so the platform captures the global competitive environment a berry-industry intelligence manager actually needs.
2. **Retire accumulated technical debt** so each new source, berry, market, and workflow makes the system more robust instead of more fragile.

The governing product question for this phase is:

> **Can Berry Intelligence OS surface an important competitive change that the analyst did not already know to search for, explain why it matters, show the supporting and contradictory evidence, and make the gap in coverage visible when it cannot?**

---

## 2. Product North Star

The operating loop remains:

**SCAN → READ → UNDERSTAND → DECIDE → PROMOTE → CONNECT → MONITOR**

The intelligence-production stack is:

**Source Item → Evidence → Story Thread → Signal Candidate → Human Review → Signal → Fact / Assessment → Recommendation**

Important boundaries:

- A **Story Thread** is organizational grouping around one event or developing story. It is not a trust layer.
- A **Signal Candidate** is an untrusted proposed pattern across Evidence.
- A **Signal** is a human-reviewed intelligence pattern, not a prediction or Assessment.
- A **Fact** is a trusted atomic proposition supported by Evidence.
- An **Assessment** is analyst interpretation of Facts and/or Signals.
- A **Recommendation** is a proposed action informed by Assessments, Signals, Facts, and Evidence.
- No AI-generated object becomes trusted automatically.
- Source count does not equal source independence.
- A primary-source document proves what that document says or records; it does not automatically prove commercial success, intent, acreage, market share, or strategic outcome.

---

## 3. Four-Berry Scope

The platform must work globally across:

- Strawberry
- Blueberry
- Raspberry
- Blackberry

Berry is **context**, not application architecture. Company, Geography, Variety, Source, Signal, and Assessment must all be queryable across berry boundaries.

### Current maturity direction

- **Blueberry:** original and deepest reference vertical.
- **Strawberry:** second real vertical with companies, breeders, varieties, patents, current sources, Evidence, and Signal participation.
- **Raspberry:** third real vertical and strongest proof of repeatability; recent depth work required no berry-specific application code.
- **Blackberry:** next depth vertical after current generic Story Thread robustness work and the higher-priority global coverage gaps below.

The platform should no longer treat “support all four berries” as the ultimate goal. The real goal is **global competitive awareness across berry, company, geography, variety, source type, and time**.

---

## 4. Expansion Program Overview

The next phase is organized into eleven workstreams.

### Workstream A — Intelligence Recall Benchmark

Build a permanent benchmark of known events that a strong global berry CI program should have captured.

### Workstream B — Mainstream News & Regulatory Intelligence

Close demonstrated gaps in mainstream business press, regional press, litigation, regulation, policy, tariffs, antidumping, labor, food safety, reputation, and executive coverage.

### Workstream C — Variety Intelligence Backbone

Make variety competition and commercial footprint a first-class analytical capability rather than a simple variety catalog.

### Workstream D — Global Variety / Plant-IP Registry Network

Extend the current plant-patent capability into broader global PVR/variety-rights monitoring.

### Workstream E — Retail & Market Observation Intelligence

Capture where varieties actually appear commercially, including retailer, market, origin, price, pack, brand, and observation date where public evidence allows it.

### Workstream F — Insider / Career / Conference Intelligence

Add newsletters, practitioner commentary, career-page/job-posting monitoring, and conference speakers/exhibitors as earlier-signal sources.

### Workstream G — Quantitative Corroboration

Add customs/trade, weather/climate, currency/freight context, and eventually satellite/remote-sensing data.

### Workstream H — Global Competitive Landscape

Evolve the product from berry-specific pages into a globally pivotable intelligence graph across Company, Berry, Variety, Geography, Retailer, Breeder, Source, Signal, and Time.

### Workstream I — UI V2

Complete the approved application-style shell and then migrate the full product after the current bounded prototype hardening gate is passed.

### Workstream J — Technical Debt & Reliability

Run continuously in parallel with every workstream. Technical debt is now a first-class roadmap item, not cleanup to defer indefinitely.

### Workstream K — Learner Mode / Agronomy, Technology & Consumer Science

Add a connected but semantically distinct explanatory-knowledge layer — plant biology, production systems, pest/disease management, harvest technology, and flavor/consumer science across all four berries — anchored to the same Berry and Variety records the rest of the OS already uses. Full requirement: `docs/v2/feature-requests/LEARNER-MODE.md`. Requirements/governance only as of 2026-08-22; no implementation has started. (Note: the originating feature request named this "Workstream I" — that letter is already assigned to UI V2 above, so this workstream is K, the next free letter, to avoid renumbering an established reference. Full detail in section 12a below.)

---

# PART I — INTELLIGENCE EXPANSION

## 5. Workstream A — Intelligence Recall Benchmark

### Objective

Measure whether the system catches important developments, not merely how many sources it monitors.

### Build a known-event benchmark

Create a curated set of approximately 50–100 strategically relevant events from the previous 6–12 months. It should span all four berries and multiple geographies.

Required categories:

- acquisitions / investments / partnerships
- executive changes
- facility or production expansion
- litigation
- labor controversy
- environmental / sustainability criticism
- food-safety / pesticide / reputation issues
- major investigative or profile journalism
- tariffs / antidumping / trade-remedy actions
- phytosanitary / market-access developments
- patents / PVR filings
- variety launches / licensing deals
- breeding partnerships
- retail variety introductions
- production-region expansion
- major import/export changes
- supply disruption
- important consumer or market trend stories

### Required metrics

For every benchmark event:

- expected discovery date/window
- relevant berry/berries
- relevant companies/entities
- source class that should have caught it
- whether OS detected it
- first detection timestamp
- source that detected it
- whether it was classified direct/adjacent/irrelevant
- whether it entered review
- whether it was threaded correctly
- whether it contributed to a Signal
- reason for any miss

### Primary metrics

- **Recall:** percent of known important events discovered.
- **Timeliness:** delay from public availability to OS discovery.
- **Precision:** percent of surfaced material that is actually relevant.
- **Coverage:** whether important source/entity/region classes are represented.

### Acceptance target

Do not set a fake “95% recall” target initially. Establish a real baseline first. Use the benchmark to drive source expansion.

---

## 6. Workstream B — Mainstream News & Regulatory Intelligence

### Why now

The system has demonstrated misses in precisely the kind of intelligence that a competitive-intelligence manager cannot afford to miss: major mainstream profiles, reputational coverage, litigation, and regulatory/trade developments.

### Coverage classes

#### Mainstream / business press

Priority discovery should include a bounded set of high-value outlets and reliable discovery mechanisms for:

- Reuters
- Associated Press
- New York Times
- Wall Street Journal
- Bloomberg
- major national business press
- major regional/local publications in production and headquarters regions
- relevant investigative journalism

The objective is discovery and metadata capture, not bypassing paywalls.

For paywalled stories, retain only legitimately available metadata/snippets plus URL, publisher, dates, entity matches, classification, and analyst notes.

#### Regulatory / government

Monitor event chains, not isolated documents:

- antidumping / countervailing-duty proceedings
- tariffs and trade remedies
- ITC / Commerce proceedings
- plant-health rules
- pesticide / food-safety decisions
- border / customs / market-access actions
- litigation involving key companies/genetics/IP

A developing regulatory event should become a Story Thread with all primary and secondary documents attached.

### Acceptance benchmark

Known high-value stories already identified by the analyst should be included as benchmark cases. The system should prove it can discover materially similar stories without manual URL seeding.

---

## 7. Workstream C — Variety Intelligence Backbone

### Objective

Make variety competition one of the defining capabilities of Berry Intelligence OS.

A Variety should not merely be a named Entity. The system should support a derived intelligence view that answers:

- who bred it?
- who owns / licenses it?
- which patents/PVRs protect it?
- what public traits are supported by Evidence?
- where is it produced?
- where is it being marketed or sold?
- which retailers/markets expose it?
- when was it first and most recently observed?
- is its commercial footprint expanding, stable, or declining?
- which competitor varieties appear alongside or against it?

### Variety identity

Where public evidence supports it:

- canonical cultivar name
- commercial / brand names
- aliases
- berry
- breeder
- owner
- licensees
- patent / PVR identifiers
- parentage
- breeding program

### Evidence-backed characteristics

Use the generic trait architecture for crop-specific traits rather than adding a field for every berry-specific concept.

Possible traits include:

- flavor
- firmness
- shelf life
- fruit size
- production window
- disease resistance
- harvest system
- fruiting / flowering habit
- protected-culture relevance
- chill / climate requirements
- yield where public data is credible

Marketing language must not silently become trusted Fact.

### Commercial footprint

Track observations by:

- country
- production region
- retailer
- marketer
- grower / packer where visible
- season
- brand
- date first observed
- date most recently observed

### Derived competitive status

Possible display-derived states:

- newly filed
- emerging
- commercially observed
- expanding geographically
- repeatedly observed
- mature
- declining / displaced

Do not promote these states into trusted Facts without supporting review/evidence.

---

## 8. Workstream D — Global Variety / Plant-IP Registry Network

### Objective

Move from US plant-patent monitoring to a global variety-rights intelligence network.

Target registry families over time:

- USPTO plant patents
- UPOV
- CPVO / European plant variety rights
- UK plant breeders’ rights / applicable national registries
- Australian PBR
- high-value national systems for major berry production / genetics markets where accessible

### Data relationship

A Variety should be able to link to multiple filings/rights across jurisdictions without becoming duplicate Variety entities.

Example conceptual relationship:

`Variety → USPP / CPVO / UPOV / AU PBR / national filing`

### Monitoring behavior

Registry activity should feed:

- company Recent Intelligence
- Variety page
- Story Threads
- Signal candidates
- Watches
- global IP activity filters

It must retain the existing discipline that a filing/grant does **not** prove commercialization, acreage, revenue, success, or strategic intent.

---

## 9. Workstream E — Retail & Market Observation Intelligence

### Objective

Create a structured observation layer for where varieties and competitor products actually appear commercially.

### Observation model requirements

A market observation may include:

- observation date
- retailer
- retailer country / market
- berry
- variety
- brand
- marketer
- grower / packer where visible
- country of origin
- package size
- price
- promotion
- package claims
- source URL / image
- online vs physical observation
- observer / acquisition method
- confidence / review state

### Important principle

A retail observation is **Evidence of an observed commercial listing or package**, not automatically proof of scale, total distribution, or commercial success.

### Initial pilot

Use one high-observability market first. UK retail is a strong candidate because variety names are often visible in commercial listings/packaging, regardless of whether that disclosure is legally mandatory for strawberries.

Potential public retailer targets should be evaluated for terms, accessibility, stability, and variety disclosure.

### Future manual workflow

Allow analyst-submitted store/package observations, potentially including a photo. The system may propose retailer, berry, variety, brand, origin, pack size, price, and date; human approval remains required.

---

## 10. Workstream F — Insider / Career / Conference Intelligence

The older Insider & Alternative Data feature request remains directionally useful but parts of it have been overtaken by the current architecture: patents, corroboration links, source independence, Signal formation, and multi-berry support already exist. Do not create duplicate trust fields or parallel schemas.

### Insider newsletters / practitioner sources

Evaluate and onboard only when there is a stable, permitted discovery path. Candidate classes include:

- produce-industry newsletters / Substacks
- ag-tech investment commentary
- practitioner / association-adjacent blogs
- data-driven industry blogs such as Agronometrics-style reporting

### Career / job-posting monitoring

High-priority source class because job postings can provide clear, timestamped signals about:

- geography expansion
- breeding/genomics investment
- new commercial capabilities
- organizational buildout
- senior leadership hiring

Prefer company career pages and permitted public feeds over brittle third-party scraping.

### Conferences

Monitor:

- speaker lists
- exhibitor lists
- programs
- abstracts
- session titles
- sponsor lists

Uses:

- entity discovery
- new-company discovery
- emerging technology/genetics topics
- market/geography prioritization
- upcoming strategic activity

### Social / informal sources

Treat as a weaker evidence class unless the post is a direct statement by an identifiable primary actor.

Do not add a second “Signal Confidence” field. Use the existing model:

- source authority
- information confidence
- verification state
- evidence links
- source independence
- Signal confidence
- does_not_prove
- human review

No automated evasion of access controls, private groups, or platform restrictions.

---

## 11. Workstream G — Quantitative Corroboration

### 11.1 Customs / trade data — first quantitative priority

Build berry-aware import/export intelligence using authoritative or licensed datasets.

Track where possible:

- volume
- value
- origin
- destination
- monthly/quarterly trend
- YoY change
- seasonality
- unit-value movement

Trade data should connect directly to qualitative Evidence and Signals.

Example:

`trade coverage says supply is expanding`  
`+ customs volumes independently rise`  
`→ stronger, independently corroborated Signal`

### 11.2 Weather / climate

Tie monitored production geographies to meaningful anomalies rather than generic weather feeds.

Potential signals:

- freeze
- excessive rainfall
- drought
- heat
- hurricane / cyclone
- El Niño / La Niña-related anomalies

Do not turn every weather event into intelligence. Relevance depends on monitored production geography and crop timing.

### 11.3 Currency / freight

Context layer for international export economics:

- relevant FX pairs
- reefer / shipping indices where legitimately available
- port / logistics disruption

Use as explanatory context rather than primary Evidence of company behavior.

### 11.4 Satellite / remote sensing — later

Evaluate only after trade + weather + retail observations prove useful.

Satellite work introduces:

- licensing/API cost
- geospatial data models
- imagery processing
- field/geography normalization
- acreage-confidence methodology
- potentially substantial UI requirements

Treat as a separate investment decision, not a default feed.

---

## 12. Workstream H — Global Competitive Landscape

The long-term product must support pivots across:

- Company
- Berry
- Variety
- Geography
- Retailer
- Breeder
- Source
- Story Thread
- Signal
- Time

Examples:

### Company view

`Planasa → Strawberry → varieties → UK observations → patents → Spain production → current Signals`

### Geography view

`United Kingdom → Raspberry → varieties observed → retailers → breeders → new entrants → Signals`

### Variety view

`Malaika → breeder → rights → geographies → retailer observations → Story timeline → Signals`

This is the desired end state of the competitive landscape, rather than four isolated berry dashboards.

---

## 12a. Workstream K — Learner Mode / Agronomy, Technology & Consumer Science

Full requirement, citations, and product design detail: `docs/v2/feature-requests/LEARNER-MODE.md`. This section is a durable summary and pointer, not a replacement — read the feature request itself before implementing any part of this workstream. Formalized 2026-08-22 as requirements/governance only; no implementation has started.

### Why this workstream exists, and how it differs from Competitive Intelligence

Every other workstream in this guide (A through J) answers Competitive Intelligence's question: **"What is changing, who is doing it, and what does it imply?"** Learner Mode answers a different question: **"How does the crop work, why do production decisions matter, and why do consumers prefer what they prefer?"**

Learner Mode is connected to, but semantically distinct from, Competitive Intelligence. It is a parallel, toggleable explanatory layer anchored to the same Berry and Variety entities the rest of the OS already uses — not a second app, not a duplicate entity model, and not a trust shortcut into Signals or Assessments (see Core Rules below).

### The five pillars

1. **Plant Biology & Agronomy** — root/cane/crown anatomy, primocane vs. floricane, chill requirements, soil/pH chemistry, per berry.
2. **Pest, Disease & Cross-Cutting Process** — IPM, biological controls, regional pest/disease guides, protected-culture/substrate systems.
3. **Harvest Technology & AgTech** — robotic harvesting, machine vision, sensing; an explicitly fast-moving research area requiring ongoing monitoring, not a static reference.
4. **Taste & Consumer Science** — Brix/acidity, VOC profiles, aroma chemotypes, texture, consumer sensory panels. This is its own pillar, not a generic trait section folded into Plant Biology — it is the specific bridge connecting a variety's breeding decisions to why consumers actually prefer it, closing the loop back into market/competitive data.
5. **Visual Content Sourcing** — diagrams (extension-sourced, mechanism-teaching), photography (reality-grounding), and video (process/motion-dependent), each carrying real source/license/attribution requirements. Visual content is not decorative; it is subject to the same source-provenance discipline as text content.

### Knowledge classes (the operating distinction Learner Mode requires)

Unlike Competitive Intelligence's single Evidence trust model, Learner Mode content spans four classes with materially different stability and review needs:

- **Foundational knowledge** (relatively stable) — crop biology, root/cane/crown anatomy, primocane/floricane, dormancy/chill concepts, basic flavor chemistry concepts. Slow review cadence.
- **Regional production practice** (must carry geography/production-system context) — spacing, pruning, trellis, fertility, irrigation, frost protection, plasticulture, substrates, harvest practice. Never universalized across geographies.
- **Current technical guidance** (needs freshness/review) — IPM, pesticide recommendations, disease management, biological controls, robotics, sensing, emerging production technology.
- **Consumer/sensory observations** (dated research outputs) — Brix/acidity, VOC profiles, aroma chemotypes, texture, sensory panels, consumer-preference studies. Retain date/event context; track as a trended data point, not a single static fact.

### Core rules

- Learner Mode reuses existing Berry / Variety / Geography / Source / Evidence objects. Do not create duplicate Berry or Variety records for Learner Mode.
- Learner knowledge is not automatically Competitive Evidence or a Signal. Learner content may explain why a Signal matters but must not automatically increase Signal confidence.
- Every substantive technical claim retains provenance. Regional production guidance must not be universalized. Variety-specific agronomic claims require variety-specific evidence.
- Marketing flavor claims (e.g. "extra sweet," "intensely aromatic") remain distinct from measured chemistry/sensory evidence — a claim is not substantiated merely because it appears in a press release.
- Consumer-panel results retain date/event context (e.g. the CNR-IBE Macfrut sensory study is a dated, recurring event, not a timeless fact).
- Time-sensitive guidance requires review/freshness semantics; core plant biology can have a much slower review cadence (see knowledge classes above).
- Visual assets require source/license/attribution metadata. Do not copy third-party visual assets unless the license explicitly permits it.
- The OS-wide glossary should eventually support terms such as primocane, floricane, plasticulture, chill hours, IPM, Brix, VOC, and aroma chemotype.
- "Explain this" links should eventually connect Competitive Intelligence surfaces into the relevant Learner Mode topic.

### Roadmap boundary: Learner Mode vs. Variety Intelligence vs. Weather Intelligence

These three are easily conflated and must stay distinct:

- **Variety Intelligence** (Workstream C, `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md`) = competitive identity, rights, market footprint, commercial observations. It answers "who owns/sells/observes this variety."
- **Weather Intelligence** (Workstream G, `docs/v2/WEATHER-CLIMATE-CONTEXT-V1.md`) = quantitative environmental observation/context. It answers "what were the real measured conditions in this production region."
- **Learner Mode agronomy** (this workstream) = explanatory knowledge of *why* weather/conditions matter biologically, and *why* production decisions are made the way they are. It answers "why does a frost event threaten this crop at this growth stage" — the biological reasoning Weather Intelligence's own quantitative readings do not attempt to supply.

Do not merge these three into one concept. A future Variety detail page may link out to a Learner Mode Growing Profile; Weather's own production-region weather readings may someday be cited by a Learner Mode agronomy explanation of frost risk; but the entity models, trust semantics, and update cadences of all three stay separate.

Two further boundaries worth stating explicitly, since they are easy to conflate in practice: **trait architecture** (the existing generic trait-entity mechanism used by Variety Intelligence, e.g. `trait-fruiting-habit`, `trait-flowering-habit`) is a Variety-scoped, evidence-linked competitive attribute, not a Learner Mode content object — a future Learner Mode agronomy page may *reference* an existing trait entity by name (e.g. explaining what "primocane fruiting habit" means biologically) without creating a parallel trait system. **Commercial Observations** (`commercial_observation`, Variety Intelligence Backbone) record a specific retail listing at a point in time and are unrelated to Learner Mode's Taste & Consumer Science pillar, which records sensory-panel/VOC research findings, not retail listings — a variety's page may show both side by side without either one substituting for the other. Source monitoring for Learner Mode (university extension guides, peer-reviewed journals, trade-fair sensory panels) would be a new, distinct source class from every existing Competitive Intelligence source class, when a future mission builds it — not a repurposing of existing trade-press/regulatory sources. Landscape (currently unmigrated, see AGENTS.md) is out of scope for this workstream entirely; no future Learner Mode mission redesigns Landscape.

### Initial build sequence (roadmap only — do not execute)

- **Phase K.1** — Learner Mode architecture + agronomy/source audit.
- **Phase K.2** — Blueberry + Raspberry knowledge pilot. Blueberry stresses woody-perennial/root/pH/chill concepts; raspberry stresses cane biology/trellis/primocane-floricane concepts — the two together cover the broadest foundational-knowledge surface with the fewest crops.
- **Phase K.3** — Glossary + "Explain this" integration.
- **Phase K.4** — Strawberry + Blackberry expansion.
- **Phase K.5** — Ongoing Emerging Technology / Sensory Research monitoring (Pillars 3 and 4 are explicitly not static reference material).

This sequence is a plan, not an authorization — no phase begins until a future mission is explicitly scoped to build it.

---

# PART II — TECHNICAL DEBT & PLATFORM HEALTH

## 13. Technical Debt Is Now a First-Class Workstream

Technical debt must be cleared continuously from this point forward.

The platform has evolved rapidly through many real-data and production iterations. That has been productive, but the next phase will multiply source classes, entities, geographies, and workflows. Unmanaged debt will compound quickly.

Every substantial feature mission must therefore include a **Debt Check** and every 2–3 feature sprints should include a dedicated debt/reliability sprint.

---

## 14. Technical Debt Categories

### TD-1 — Hardcoded domain assumptions

Continuously search for:

- blueberry-only route/copy assumptions
- hardcoded berry IDs
- hardcoded source counts
- hardcoded entity counts
- stale fixture counts
- berry-specific scoring bonuses
- region-specific assumptions presented as global

Recent multi-berry work has already demonstrated the value of this audit.

### TD-2 — Runtime/config synchronization

Ensure canonical trusted configuration/data and runtime-local operational state remain deliberately separated.

Protect against:

- once-only volume seeding
- stale source configuration
- missing entity files in deployed runtimes
- module invocation/path differences between dev and Docker
- root-owned/git-object permission drift
- executable-bit deployment failures
- runtime paths silently falling back into containers

Every deployment-path fix must have an automated regression test where practical.

### TD-3 — Performance / repeated scans

Profile and reduce expensive request-time operations such as:

- repeated full repository scans
- Story Thread recalculation
- Signal annotation
- reverse entity-link lookup
- Reader relationship resolution
- source-health aggregation

Use repository/query-service seams and safe caching rather than UI spinners as the first response to latency.

Never cache analyst trust/review state in a way that makes decisions stale.

### TD-4 — Candidate / proposal lifecycle hygiene

Preserve:

- opaque IDs
- archive stale candidates instead of reassigning decisions
- 410 for retired candidate references
- 404 for unknown candidates
- inbox candidates never leak into static/public output
- exact-ID review state only

Do not allow regenerated AI proposals to inherit analyst decisions heuristically.

### TD-5 — Data quality / lineage

Continuously audit:

- mistagged berries
- stale aliases
- duplicate entities
- unresolved assignees
- incorrect variety/company relationships
- missing publication dates
- captured_date being mistaken for published_date
- trusted records with newly discoverable entity associations

Prefer non-mutating derived recall over bulk rewriting of trusted Evidence.

### TD-6 — Source normalization / deduplication

Continue improving conservative detection for:

- canonical URL variants
- redirect wrappers
- publisher vs syndicator URLs
- title suffixes
- reprints across several days
- same origin under variant publisher labels

Never merge merely because titles/entities are vaguely similar.

### TD-7 — Story Thread robustness

Maintain conservative event grouping.

False separation is preferable to false merge, but real company-primary / variety-primary coverage should thread when a strong shared event identity exists.

Story Thread membership must not itself increase Signal confidence.

### TD-8 — Signal calibration

Keep a real audit sample for Signal candidates.

Track:

- precision overall
- precision among high-confidence candidates
- false source-independence merges
- false separations
- patent overinterpretation
- limited spoken-media evidence
- generic trait/entity contamination

Signal rules should be calibrated with real evidence, not synthetic examples alone.

### TD-9 — Test brittleness

Replace avoidable hardcoded global counts with invariant-based tests where possible.

Examples:

Bad:
`assert len(entities) == 184`

Better where semantics allow:
`assert required_entities <= entity_ids`

Counts should remain hardcoded only when the count itself is intentionally contractual.

Also remove environment-specific artifact paths from tests when they are not actually part of product behavior.

### TD-10 — Frontend consistency

UI V2 should systematically retire:

- three unrelated card systems
- three filter languages
- pill overuse
- duplicate semantic colors
- disappearing mobile nav
- Scanner vs Feed naming mismatch
- legacy Bootstrap/global CSS regressions

Do not perform a blind all-page reskin. Migrate by component/page sequence after prototype approval.

### TD-11 — Dependency hygiene

Current V2 rule:

- Bootstrap 5 is permitted as the shell dependency.
- Mirbal is a design/layout reference, not a framework dependency.
- Mooli is reference-only; do not import its Bootstrap 4/jQuery stack.
- Do not add chart/calendar/editor/plugin libraries until a real product requirement needs them.

Audit Python and JS dependencies periodically for:

- unused packages
- duplicated functionality
- old pinned versions
- security/maintenance concerns

### TD-12 — Documentation drift

The following must stay aligned with canonical behavior:

- `PROJECT-STATUS.md`
- `AGENTS.md`
- domain-pack manifests
- architecture/domain-model docs
- deployment docs
- this Expansion Build Guide

Agents should update docs when a mission materially changes system behavior, but documentation updates must not be used as a substitute for working code/tests.

---

## 15. Technical Debt Register

Create and maintain:

`docs/v2/TECHNICAL-DEBT-REGISTER.md`

Suggested fields:

| Field | Meaning |
|---|---|
| ID | `TD-###` |
| Area | runtime / data / source / frontend / tests / performance / etc. |
| Description | concrete issue |
| Evidence | bug, profiling result, real-data example |
| Impact | user/product/operations consequence |
| Severity | critical / high / medium / low |
| Compounding risk | how much worse it gets as scale increases |
| Owner lane | Cursor / Claude / either |
| Fix class | quick / sprint / architecture |
| Status | open / in progress / resolved / accepted |
| Introduced / observed | date or canonical SHA |
| Resolved | PR/SHA |
| Regression test | test path / none |

### Debt rules

- Production bug discovered during a mission → register if not fixed immediately.
- Known issue mentioned in a completion report → register unless intentionally accepted.
- No “we’ll remember this later” debt.
- Critical/high debt that threatens trust, data loss, deployment reproducibility, or source correctness blocks feature expansion.
- Medium/low debt can be scheduled, but must be visible.

---

## 16. Dedicated Debt Sprint Cadence

After every **2–3 substantive feature/data sprints**, run a focused debt/reliability sprint.

A debt sprint should include:

- open-debt review
- profiling top slow routes/jobs
- flaky/brittle test review
- stale/dead code search
- unused dependency review
- hardcoded-count/domain search
- deployment-path smoke from clean environment
- runtime/config sync verification
- static leakage check
- permission/volume ownership check
- source-health audit
- duplicate/entity-quality audit
- docs/status drift audit

The goal is not perfection. The goal is preventing compounding complexity.

---

# PART III — COVERAGE MANAGEMENT

## 17. Intelligence Coverage Roadmap

Maintain this guide plus a live coverage matrix rather than relying on conversation memory.

Recommended repository file:

`docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`

At minimum track capability maturity:

| Capability | Blueberry | Strawberry | Raspberry | Blackberry | Global Status |
|---|---|---|---|---|---|
| Trade press | | | | | |
| Mainstream news | | | | | |
| Company newsrooms | | | | | |
| Regulatory | | | | | |
| Patents | | | | | |
| PVR / rights registries | | | | | |
| Variety knowledge | | | | | |
| Retail observations | | | | | |
| Insider newsletters | | | | | |
| Jobs/careers | | | | | |
| Conferences | | | | | |
| Customs/trade data | | | | | |
| Weather/climate | | | | | |
| Satellite | | | | | |
| Agronomy knowledge (Learner Mode) | | | | | |
| Pest/IPM knowledge (Learner Mode) | | | | | |
| Harvest/AgTech knowledge (Learner Mode) | | | | | |
| Taste/consumer science (Learner Mode) | | | | | |
| Licensed visual learning (Learner Mode) | | | | | |

Status vocabulary:

- NONE
- PILOT
- PARTIAL
- OPERATIONAL
- STRONG

Do not use “Operational” to imply comprehensive coverage.

---

## 18. Geographic Coverage Matrix

Track **Berry × Geography × Intelligence Type**.

Priority geographies should emerge from actual company/production/market evidence, but expected important regions include the US, Mexico, Peru, Chile, UK, EU production/retail markets, Morocco, South Africa, Australia/New Zealand, and relevant Asian markets.

Example dimensions:

- News
- Company coverage
- Variety/IP
- Retail observation
- Production
- Trade
- Regulation
- Weather risk

This matrix is how the project should identify the next blind spot rather than expanding randomly.

---

## 19. Entity / Competitor Coverage

Each strategically important tracked company should eventually have a coverage profile:

- berries
- geographies
- current sources
- company newsroom
- mainstream-news discovery
- patents/PVR
- varieties
- Story Threads
- open/confirmed Signals
- retail observations
- jobs/careers
- conference presence
- newest meaningful intelligence date
- source-health gaps

Classify company coverage:

- STRONG
- MODERATE
- WEAK

This should be based on actual coverage paths and freshness, not number of historical Evidence records.

---

# PART IV — DELIVERY SEQUENCE

## 20. Recommended Near-Term Sequence

### Gate 0 — Complete current in-flight work

- UI V2 hardening / Company-profile proof
- Story Thread primary-subject robustness

Do not interrupt active branches unless they conflict with a critical production fix.

### Sprint 1 — Mainstream News + Regulatory Recall Benchmark

Deliver:

- known-event recall benchmark
- mainstream/general-business discovery V1
- regulatory event-chain monitoring V1
- measured recall baseline

### Sprint 2 — Variety Intelligence Backbone

Deliver:

- richer variety-derived views
- breeder/owner/license/IP relationships
- trait normalization
- commercial-footprint model design
- global registry coverage audit

### Sprint 3 — UK Retail Observation Pilot

Deliver:

- Market Observation model/service
- one-market retailer pilot
- analyst review workflow
- variety/retailer/market linkage

### Sprint 4 — Variety Competition UX

Cursor-led after real observation data exists.

Deliver:

- Variety competitive page
- geography footprint
- retailer observations
- breeder/IP timeline
- related Signals
- comparison/filter workflow

### Sprint 5 — Insider + Jobs + Conferences

Deliver:

- small stable newsletter set
- career-page/job monitoring V1
- conference entity-discovery V1

### Sprint 6 — Customs / Trade Data V1

Deliver:

- berry-aware trade series
- geography linkage
- quantitative Evidence
- Signal corroboration proof

### Later

- weather/climate
- freight/currency
- social/manual-assisted layer
- satellite/remote sensing

### Blackberry depth

Blackberry can run in parallel when agent capacity is available because Raspberry has demonstrated that berry-depth expansion is now predominantly domain/data work.

---

# PART V — AGENT OPERATING RULES

## 21. Before Every Mission

Every coding agent must:

1. `git fetch origin`
2. determine actual canonical
3. inspect active PRs/branches relevant to its lane
4. avoid relying on stale SHA/context from prompts
5. identify overlap with the other active agent
6. read this guide plus `AGENTS.md` and current `PROJECT-STATUS.md`
7. classify the mission as:
   - product/UI
   - acquisition
   - domain depth
   - intelligence reasoning
   - technical debt
   - deployment/reliability

---

## 22. Definition of Done

A feature/data mission is not done merely because code exists.

As applicable, completion requires:

- real-data proof
- full test suite
- `validate_records.py`
- `build_static.py`
- static leakage check
- `git diff --check`
- production/runtime smoke
- no trust-gate weakening
- no destructive trusted rewrite
- documentation update
- debt register update for unresolved findings
- canonical merge
- canonical-only deployment

For source work additionally report:

- sources attempted/succeeded/failed
- scanned/new/duplicate
- direct/adjacent/irrelevant
- drafts created
- idempotent second-pass proof where applicable
- source health
- known misses

For domain work additionally report:

- companies
- varieties
- Evidence
- patents/PVR
- Story Threads
- Signals
- geographies
- new generic code required
- berry-specific hacks required

Target for berry-depth work: **zero berry-specific architectural hacks**.

---

## 23. Trust & Evidence Rules

Non-negotiable:

- No AI auto-publishes trusted Evidence.
- No Signal Candidate automatically becomes a trusted Signal.
- Confirming candidate review state is not Signal publication.
- A Signal does not automatically create an Assessment.
- An Assessment does not automatically create a Recommendation.
- Pending/untrusted records never leak into public static output.
- Paywalls/access controls are not bypassed.
- Social/informal sources use the existing authority/confidence/verification model rather than a parallel trust system.
- Source authority is not claim confidence.
- Claim confidence is not Signal confidence.
- Signal confidence is not Assessment confidence.
- Reprints are not independent corroboration.
- Patent/PVR activity does not prove commercialization or strategy.
- Market Observation proves an observation, not market scale.
- Learner Mode content is explanatory knowledge, not a trust shortcut into Signals or Assessments — it may explain why a Signal matters but must not automatically increase Signal confidence (Workstream K, `docs/v2/feature-requests/LEARNER-MODE.md`).

---

## 24. UI V2 Rules

Until the V2 prototype gate is approved:

- do not migrate the entire UI
- Bootstrap 5 is the only approved vendor shell dependency
- Mirbal is reference material, not a runtime framework
- Mooli is reference-only
- preserve custom Intelligence OS semantics
- Feed overlay Reader must retain keyboard/focus behavior
- mobile must have real navigation
- berry is context, not visual costume

After V2 approval, migrate pages in controlled order with regression screenshots/tests.

---

# PART VI — SUCCESS CRITERIA

## 25. What Success Looks Like

Berry Intelligence OS should eventually be able to surface a development such as:

> A competitor begins filing new genetics IP, a named variety starts appearing in retailer listings in a new market, a hiring pattern suggests regional commercial buildout, an industry newsletter references expansion, and trade data begins moving in the same direction.

The OS should:

1. discover those individual observations independently
2. retain source/provenance and uncertainty
3. group same-event coverage without collapsing unrelated activity
4. distinguish reprints from independent origins
5. connect the observations to the correct Company, Variety, Berry, Geography, and Retailer
6. propose a Signal only when evidence supports a pattern
7. show what the Signal does and does not prove
8. allow the analyst to form an Assessment
9. preserve counterevidence and what would change the view
10. make remaining coverage gaps visible

That is the standard for the next phase.

---

## 26. Immediate Repository Actions

Add this document at:

`docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`

Then create:

1. `docs/v2/TECHNICAL-DEBT-REGISTER.md`
2. `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`

Update `AGENTS.md` with a short pointer such as:

> **Expansion phase:** Before planning new acquisition, domain-depth, variety, alternative-data, or UI V2 work, read `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`. Unresolved platform debt must be recorded in `docs/v2/TECHNICAL-DEBT-REGISTER.md`; source/domain expansion should update `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`.

Update `PROJECT-STATUS.md` to name this guide as the governing roadmap for the post-foundation expansion phase.

---

## 27. First Mission Under This Guide

After current in-flight work lands, the first major mission should be:

**Mainstream News + Regulatory Coverage Recall Benchmark V1**

because demonstrated real-world misses currently pose a larger intelligence-quality risk than adding another source category or deepening Blackberry immediately.

The first technical-debt pass should run as part of that same mission and create the initial debt register from all known unresolved issues surfaced in recent agent completion reports.
