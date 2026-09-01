# Berry Intelligence OS — Architecture & Product Readiness Audit (2026-09-01)

**Author:** Claude (this audit). **Scope:** read-only investigation of `origin/v2/intelligence-os` as of `2c8c039` / the in-flight Continuous Newsroom Intake V1 merge. No code changes accompany this document beyond itself.

**Mandate:** answer, without defending prior work, whether Berry Intelligence OS is genuinely on a path to a best-in-class competitive-intelligence SaaS product, given what's available to build with in 2026.

---

## 1. Executive verdict

Berry Intelligence OS has built something genuinely uncommon: a trust-boundary discipline that is enforced in code, not just policy — draft/review/publish state machines, an append-only review-event audit trail, an AI boundary where every LLM call site is named and structurally prevented from writing trusted state, and a deduplication/provenance model precise enough to tell a Google News wrapper URL from its real publisher. That discipline is real engineering, not a slide.

It has also spent a large fraction of its build effort re-solving problems the market already sells solved — RSS discovery, article body extraction, wall/paywall detection, sitemap parsing, dedup — while the two things that would make a customer choose this over "just use Perplexity" (a deep, reviewed, berry-specific knowledge graph, and continuously fresh coverage) are both structurally present but nowhere near mature: 6 Signals and 5 Assessments sit on top of 1,269 Evidence records, and `source`/`person`/`product` are declared entity types with **zero real records**. The trust *mechanism* is production-grade; the trust *graph* it's supposed to protect is still a prototype.

**Verdict: the architecture is not wrong, but the sequencing was.** Trust infrastructure and bespoke collection were built to a high standard before the knowledge graph they exist to protect had enough mass to need protecting. The last four missions (Front Page, Industry Pulse, Perplexity activation, Newsroom Intake) finally close the *ingestion* freshness gap and prove the team can course-correct fast. But a live read of production (Appendix A, below) shows the freshness gap was never primarily an ingestion problem: discovery finds new items every day, yet the newest **published, trusted** Evidence in production has a real-world source date of 2026-08-06 — 26 days stale — because 1,710 Publication drafts are sitting in Publication Review against exactly 3 ever published, backed by a grand total of **one** recorded review decision in production history. Whether this becomes best-in-class depends on the next 90 days going into review throughput and graph depth (Signals/Assessments, entity coverage, identity resolution), not another retrieval provider integration — the funnel data below makes this not a judgment call but a measured fact.

---

## 2. Strongest parts of current architecture

- **The trust state machine is real, not decorative.** `draft → in_review → published` for Evidence; a five-state adopted machine for Signal (`proposed/monitoring/confirmed/refuted/retired` plus human-decision states `disputed/deferred/dismissed`); `active/superseded/withdrawn` for Assessment. Every transition is a named function, not a status-field mutation scattered across routes.
- **Append-only review-event audit trail** (`app/services/review_events.py`), content-hash-addressed, deliberately excludes draft text, and — tellingly — refuses to compute publish/reject rate analytics until ≥30 decisions across ≥2 days exist. That's a system honest about its own immaturity rather than one that overclaims from thin data.
- **The AI boundary is enforced by code path, not convention.** `complete_untrusted_json` is named to make misuse obvious and is called from exactly two places, both human-reviewed surfaces. The separate Perplexity extraction path for Atomic Evidence has a model-identity gate that fails closed. No Evidence/Signal/Assessment record in this corpus was ever auto-published by an LLM.
- **Chronology honesty.** `captured_date` is never allowed to masquerade as `published_date` anywhere in the pipeline — enforced at the schema-adjacent level (`FORBIDDEN_FRESHNESS`) and now, as of this session, extended into the Front Page's own historical-backfill handling.
- **Deduplication is identity-based, never fuzzy-merged.** A Google News wrapper URL is resolved to its real publisher before comparison; two records are never silently collapsed on title similarity alone. This is the single most reusable piece of infrastructure in the codebase — every new provider (Perplexity, and now NewsCatcher/CatchAll) plugs into the same `identity_key`/`find_duplicate_article` primitives instead of inventing its own.
- **Geography and coverage modeling is genuinely deterministic.** Region containment (`geography_hierarchy.py`), Coverage Assurance's COLLECTED/KNOWN-NOT-COLLECTED/UNKNOWN-SOURCE-IDENTITY/INTENTIONALLY-EXCLUDED reconciliation, and the recall-taxonomy classifier (`recall_audit/classify.py`) are all explainable, no-invented-score systems — a real, if narrow, moat candidate (Section 10).
- **Fast course-correction under real pressure.** Four missions in one day (Front Page → Industry Pulse → Perplexity activation → Newsroom Intake) closed a real, diagnosed product gap (fresh discovery trapped in diagnostic metadata, never reaching the homepage) end-to-end, each with real production acceptance data, not just passing tests.

---

## 3. Weakest parts

- **The graph is thin where it matters most.** 6 Signals, 5 Assessments, against 1,269 Evidence. `source`, `person`, `product` entity types exist in schema and nowhere in data. Variety parentage/lineage is not modeled at all — bibliographic breeding lineage sits as unstructured prose inside `summary` fields on 30 patent/PVR records, unqueryable.
- **Identity resolution is barely exercised.** The redirect mechanism has exactly one real entry (a single Planasa duplicate). At least two known, documented, unresolved identity gaps sit in the debt register (Allberry B.V./Advanced Berry Breeding B.V.; USDA-ARS as an unlinked patent assignee) — this is exactly the kind of gap a competitor with a mature entity-resolution product (e.g. a knowledge-graph vendor) would exploit as a wedge.
- **Single-operator trust model.** `BIOS_MODE=authoring` is one flat boolean; there is no reviewer-role concept anywhere in `session_auth.py`. This works for dogfood. It does not scale to a real SaaS customer team without becoming the first hard blocker.
- **Bespoke acquisition surface is large and growing.** RSS fetch/normalize, sitemap parsing (including a just-added `news:` XML-extension parser), article body extraction with wall detection, podcast feed resolution via manual iTunes-lookup archaeology — all hand-built and hand-maintained, when Firecrawl/Bright Data/Apify sell exactly this as commodity infrastructure with better uptime guarantees than one engineering team can offer.
- **No notification/alerting layer at all.** Watchlists only update `last_seen_at` on explicit page open; no email, no digest, no push. For an intelligence product, "you have to remember to check" is a real retention risk.
- **Coverage Assurance / Collection Ops read as internal tooling, not product.** Both are gated behind the same flag as raw Intake, tucked into a collapsed 11-item "System" nav group. Fine for an operator; a customer-facing "why is my coverage what it is" surface doesn't exist yet.
- **No pagination anywhere.** Every list surface uses a hard cap (`limit=48`, etc.) with no page 2. Acceptable at 1,269 Evidence records; will not survive 10x growth without real work.
- **Relationship ontology has drifted from its own schema.** 16 predicates declared in the domain pack, only 11 enforced by `relationship.schema.json` — 5 are effectively dead on arrival at validation time. Small, but exactly the kind of drift that compounds silently.

---

## 4. What should have been done differently

Structured-data authoritative registries (USDA PVPO, UPOV PLUTO, USPTO, CPVO — see Section 8) and a real multi-provider discovery bake-off should have happened **before**, not after, building the trust-review-audit machinery around a single Google-News-only discovery channel. The team spent real engineering effort hardening a pipe that was, until today, structurally guaranteed to be behind ordinary Google search — because the Front Page/homepage that would have exposed that gap to a real user didn't exist until this session either. Product-facing surfaces (a homepage that answers "what's happening now") should have preceded, not followed, four rounds of collection-relevance/dedup/cadence optimization on a backend nobody outside the team could see the output of. The org effectively built a very good filing cabinet before building the front door.

---

## 5. Buy vs. build assessment

| Capability | Current state | Verdict |
|---|---|---|
| Article body fetch/extract | Bespoke (`article_acquisition.py`, trafilatura) | **Keep, cautiously.** It's URL-agnostic, well-tested, and already integrated into dedup/completeness. Firecrawl/Bright Data buy value is real but marginal until acquisition volume/reliability becomes a bottleneck — it isn't yet. |
| News discovery | Google News RSS (free) + Perplexity (paid, additive) | **Buy more.** NewsCatcher/APITube (already bake-off-tested per PR #212) and Exa are the next real evaluation — see Section 6. |
| Structured registries (PVR, patents) | Hand-built adapters per registry (CPVO, patent_monitor, now USDA PVPO XLSX/UPOV PLUTO/USPTO ODP/BigQuery bake-off) | **Keep building bespoke, but bounded.** These are genuinely low-volume, high-authority, publicly-licensed government/IGO datasets with no good aggregator — this is legitimate build territory, not a buy gap. |
| Sitemap/RSS parsing | Bespoke | **Keep.** Commodity-simple, already correct, not worth outsourcing. |
| Social/community listening | Absent | **Buy when built at all** — a licensed provider (Section 9), never a scraper. |
| Vector/semantic search over the corpus | Absent | **Buy or adopt an existing embeddings API** rather than build — not yet needed at 1,269 records, will be needed well before 50,000. |
| Alerting/notification | Absent | **Build** — this is workflow, not commodity, and is close to the actual trust/review loop. |
| Entity resolution / identity | Bespoke, conservative, immature | **Keep building bespoke.** A generic identity-resolution SaaS would not understand "breeder vs. licensee vs. marketer" role distinctions that are this product's actual value; this is core IP, not infrastructure. |

---

## 6. Recommended discovery stack

**Keep:** Google News RSS as the free, unconditional baseline (32-query matrix). It is not competitive alone, but it is free and already well-integrated.

**Keep, expand cautiously:** Perplexity as the semantic catch-net — production-proven this session (0% URL overlap with Google, ~23% qualify rate on Perplexity hits vs ~0.5% on Google's raw volume in the live acceptance run). This is the strongest single piece of evidence in this audit that a second provider is worth paying for.

**Evaluate next, in this order:**
1. **NewsCatcher/APITube-class aggregator** (bake-off adapter already exists per PR #212, not yet activated) — these aggregate hundreds of news APIs behind one interface; if the CatchAll bake-off numbers hold up the same way Perplexity's did, this closes the "mainstream media" gap (Section E) more cheaply than building direct Reuters/Bloomberg/AP integrations.
2. **Exa** — semantic/neural search with strong recency filtering; complementary to Perplexity rather than redundant, worth a real bake-off run (the adapter exists, per `app/services/industry_pulse/exa.py`, but has never been run against paid credentials).
3. **Bright Data SERP/Firecrawl** — hold. These solve an acquisition problem (Section 7), not a discovery problem; do not activate until a specific acquisition failure rate justifies the spend.

**What should become provider-neutral (already is, keep it that way):** the `DiscoveryProvider` protocol, `qualify_hit`/`QualificationIndex`, `dedupe_hits`/`identity_key`, `classify_hit`. Every one of these already accepts an arbitrary provider name string with no special-casing — this is correctly built for a 5th, 6th, 7th provider.

**What should be retired:** nothing yet. Every existing provider adapter (Google, Perplexity, Exa, Firecrawl, Bright Data, CatchAll) is either live or dormant-but-cheap-to-keep; none costs meaningfully to leave in place unused.

---

## 7. Recommended acquisition stack

Keep `article_acquisition.py`'s bespoke fetch/extract as the default path — it is well-integrated with `source_completeness` classification and dedup, and trafilatura-based extraction is genuinely competitive with paid alternatives for plain article HTML. The one acquisition problem worth buying rather than building: **JS-rendered/anti-bot-hardened publishers** (The Packer's own homepage already returns HTTP 403 to non-browser fetches — TD-107 in this session's own findings). This is exactly Firecrawl/Bright Data's sales pitch. Recommendation: do not integrate broadly; add a narrow, explicitly-scoped Firecrawl fallback *only* for the specific handful of publishers already known to block plain fetches (The Packer, and any future case), gated the same way `PerplexitySearchProvider` is (explicit env flag, credential-gated, isolated failure).

---

## 8. Structured-data architecture

Real, valuable government/IGO datasets with clean licensing already have adapters as of PR #212 (USDA PVPO XLSX, UPOV PLUTO operator-export parser with a hard 100-record cap, USPTO ODP, bounded Google Patents BigQuery) — none are activated in the live path yet ("bake-off adapters without activating paid production paths," per that PR's own scope). CPVO and USPTO plant-patent monitoring were already live before this session (`patent_monitor`, `cpvo_registry`).

**Missing structured layers:**
- **National PBR registries beyond CPVO/USDA/UPOV-PLUTO** — South Africa's DALRRD and UK's PVRO have reference Source entries (per this session's earlier Variety Universe Expansion work) but no structured feed, only manual reference.
- **PatentsView/USPTO Open Data Portal as a first-class structured source**, not just query-string construction on an existing client — the BigQuery Patents adapter is bounded and SQL-gated (`LIMIT` required), appropriately cautious, but not yet wired to actually populate the variety-lineage gap identified in Section 3.
- **Company registries** (e.g. OpenCorporates-class company registration/ownership data) — entirely absent. This would directly strengthen the "Company/brand/product" distinction that Section 3 found to be effectively two-way, not three-way, in practice.

**Recommendation:** do not build a general company-registry integration speculatively. Do build the missing link between the already-built BigQuery Patents adapter and the variety-lineage gap — that's the highest-leverage structured-data work available, because the raw data (patent assignee/inventor chains) already exists in an adapter that's built but disconnected from the entity graph.

---

## 9. Media/social architecture

**Specialist media** (per this session's own required production audit): Fruitnet and FreshPlaza are actively collected via real, live-verified `article_rss` feeds. **The Packer has no article/news collector at all** — only its podcast (TD-107). **FreshPlaza is double-registered** as two Source records against the identical feed URL (TD-108). Italian Berry and BlueberryBreeding were onboarded in this session's own earlier work. HortiDaily is on a site-wide RSS Source per PR #212. No verification was performed this session on EastFruit, Produce Report, or Perishable News specifically — flagged as an open item, not a confirmed gap.

**Mainstream media**: no direct Reuters/Bloomberg/NYT/WSJ/FT/AP/BBC integration exists. The realistic path is not one-by-one direct deals (cost- and licensing-prohibitive for this stage) but a NewsCatcher/APITube-class aggregator (Section 6) that already licenses mainstream sources in bulk.

**Social/weak-signal**: correctly absent today. The provider/provenance model built this session (`pulse_provenance.providers: list[str]`, any provider name string, `DiscoveryProvider` protocol) is generic enough that a future licensed Reddit/LinkedIn provider could normalize into the exact same discovery layer without rewriting Publication ingestion — this was verified architecturally, not just asserted, during Continuous Newsroom Intake V1. The missing piece for social specifically is not plumbing but a **new, explicit, non-Publication trust state** ("COMMUNITY/CHATTER — UNVERIFIED") distinct from FRESH/UNREVIEWED, since unverified chatter is a different epistemic category from a professionally-published, professionally-attributed article — deliberately not built yet, correctly deferred.

---

## 10. SaaS defensibility

**What prevents "we'll just use ChatGPT/Perplexity internally"?** Today, honestly: not much, yet — because the graph (Section 3) is too thin to be a moat on its own. The real, defensible moat candidates, in order of actual strength:

1. **The trust/review/provenance pipeline itself**, as a workflow a customer's own analysts would have to rebuild from scratch to get the same auditability — this is the strongest real moat, because it's process IP, not data IP, and process IP compounds with usage.
2. **Deterministic, explainable coverage/recall auditing** (Coverage Assurance, the recall-taxonomy classifier) — a genuinely unusual thing to have built; most competitors selling "AI research" have no equivalent honesty mechanism at all, let alone one with a documented 9-class miss taxonomy.
3. **Accumulated Signals/Assessments over time**, once the graph actually deepens — currently 6 and 5 respectively, i.e. not yet a moat, but the *right* moat to be building.
4. **Reviewed provenance** (captured-vs-published honesty, publisher-vs-provider attribution) — a real quality signal a generic LLM wrapper cannot offer, because it has no persistent state to attach honesty guarantees to.

**Wishful, not yet real:** "proprietary historical graph" and "source coverage" — both are true in kind but not yet in scale; a competitor starting today with a modern discovery stack (Exa + NewsCatcher + Perplexity) could match current *discovery* coverage in weeks. What they could not match in weeks is the review/audit workflow and its accumulated decision history — which is exactly why Section 16/17's roadmap prioritizes graph depth over further discovery breadth.

---

## 11. Cost / scaling

**Current dogfood**: near-zero marginal cost. Google News RSS is free; Perplexity (if the recurring `industry_pulse_intake` pipeline is enabled) is ~120 queries/day at ~$0.005/query ≈ **$0.60/day, ~$18/month** — a real but genuinely trivial recurring cost at this stage.

**At 10 customers**: discovery cost does not scale per-customer (one shared corpus, one shared discovery run) unless per-customer private-data overlays are added — the architecture already supports this shape (one collection pipeline serving many viewers) better than a per-tenant-scrape model would. Acquisition/storage cost stays flat. The real cost driver at 10 customers is **support/review labor**, not infrastructure — the single-operator trust model (Section 3) becomes the actual bottleneck before compute does.

**At 100 customers**: pagination (Section 3) becomes mandatory, not optional. A general caching layer (currently `lru_cache` + one minute-granularity freshness cache, no Redis) becomes necessary. If AI-assisted enrichment volume grows with customer-driven report requests, `complete_untrusted_json` call volume becomes a real, trackable cost line for the first time — currently negligible.

**Enterprise workloads**: private/internal customer-data overlays (explicit product-north-star requirement #7) are not architected at all yet — no tenant isolation model exists anywhere in the schema or `app/session_auth.py`. This is the single largest pre-enterprise gap, larger than any discovery-provider decision.

**Vendor lock-in risk**: low today by design — every retrieval provider sits behind the same `DiscoveryProvider` protocol, swappable by construction (proven three times over: Google→Perplexity→CatchAll bake-off, all without touching qualification/matrix code). The one real lock-in risk is `perplexity_search`'s underlying gateway client if it were ever deeply coupled elsewhere — it currently isn't.

---

## 12. Security / licensing risks

- **News API/RSS terms of service**: Google News RSS's own terms restrict programmatic use in ways this project has not had independent legal review of — the "respect robots.txt, never build around a wall" discipline (Section 2, TD-059) is a strong *ethical* posture but is not the same thing as a *legal* clearance. Flag for counsel before any commercial (non-dogfood) use.
- **UPOV PLUTO / USDA PVPO data licenses**: PR #212's own scope note ("do not productize PLUTO as a derived SaaS database") shows the team already recognizes this risk, but no written license-terms audit exists in the repo. Flag for counsel: redistributing UPOV PLUTO-derived data as part of a paid SaaS product likely requires a review PR #212's engineering-level caution does not substitute for.
- **Article body storage/redistribution**: the "body-free" principle (Section 2) is a real mitigant for the Source Universe/Coverage registry specifically, but full article bodies ARE stored on Publication drafts and trusted Evidence (`article.paragraphs`) — redistributing that content to paying customers (vs. using it only for internal review) is a copyright question that needs explicit legal sign-off before any customer-facing "read the original article here" feature ships bodies rather than links.
- **Social data (future)**: any licensed social provider will carry its own re-use/redistribution restrictions (e.g. platform ToS on displaying user-generated content) — flag for counsel *before* Section 9's social work begins, not after.
- **No centralized licensing policy document exists.** Constraints are currently scattered as per-source `notes`/`exclusion_reason` fields. Recommend consolidating into one governed `LICENSING.md` before any paid customer contract is signed.

---

## 13. Technical debt (highlights; full register in `docs/v2/TECHNICAL-DEBT-REGISTER.md`, currently TD-001 through TD-108)

- **TD-107**: The Packer has no article/news collector, only its podcast.
- **TD-108**: FreshPlaza double-registered as two Source records against the same feed.
- **TD-106**: Front Page dedup only clusters on shared URL/evidence_ids, not entity overlap (deliberately deferred, not urgent).
- **TD-105**: Google News RSS catch-net query yield is global-heavy, not regionally balanced (actively being worked concurrently as of this audit).
- **Relationship predicate schema drift** (Section 1): 5 of 16 domain-pack predicates unenforced by the JSON Schema.
- **hortifrut.com claimed by two different Source records** (pre-existing TD-104) — same duplicate-registration pattern as TD-108, suggesting this is a systemic onboarding-process gap, not two isolated incidents.
- **No pagination anywhere** (Section 3) — not yet in the TD register; should be added before the next data-volume-driving mission.
- **Single flat `authoring_mode` boolean** as the entire trust/permission model — the largest unaddressed architectural debt for multi-user readiness, and also not yet in the TD register.

---

## 14. Top 20 missing capabilities for a top-tier intelligence platform

1. Multi-role/multi-reviewer trust model (today: one flat boolean).
2. Notification/alerting (email/digest/push) — today: none.
3. Vector/semantic search over the accumulated corpus.
4. Variety breeding-lineage as structured, queryable relationships.
5. Real pagination on every list/search surface.
6. Tenant isolation for private/internal customer-data overlays.
7. A governed licensing/ToS policy document, reviewed by counsel.
8. Mainstream-media coverage (via an aggregator, not one-by-one deals).
9. A non-Publication "COMMUNITY/CHATTER — UNVERIFIED" trust state for future social ingestion.
10. Entity resolution actually exercised at scale (today: 1 real redirect).
11. Company registry / ownership-structure data.
12. Scheduled/recurring report delivery (today: pull-only, no push).
13. A customer-facing (not just operator-facing) coverage-transparency surface.
14. Signal/Assessment volume proportional to Evidence volume (today: ~1:200).
15. `person` and `product` entity types actually populated, or removed from the schema.
16. A real caching layer beyond `lru_cache` + one freshness cache.
17. API access for customers to query the graph programmatically (currently zero API surface beyond the app itself).
18. Historical trend/time-series views over Signals and Assessments (currently point-in-time only).
19. A benchmarked, published retrieval-quality metric (the recall-taxonomy work is close but internal-only).
20. Export formats beyond PDF (structured JSON/CSV export for a customer's own BI tooling).

---

## 15. Keep / Refactor / Replace / Add / Stop

**KEEP**: trust/review state machines; append-only review-event audit trail; AI boundary architecture; `DiscoveryProvider`/qualification/dedup provider-neutral core; geography hierarchy; Coverage Assurance's deterministic reconciliation; bespoke article acquisition (trafilatura-based); government/IGO structured-data adapters (CPVO, patent_monitor, the new PVPO/PLUTO/USPTO/BigQuery bake-off).

**REFACTOR**: `authoring_mode` into a real role model before any second real user exists; relationship-predicate schema to match the domain pack (or vice versa); the two duplicate-Source patterns (FreshPlaza, hortifrut.com) into one onboarding-time uniqueness check so a third never happens; **the Publication Review queue itself** — not its trust semantics, which are correct, but its throughput. Appendix A's read of live production shows this is the single highest-leverage refactor in the entire system: 1,710 pending drafts against 3 ever published and one recorded review decision is not an architecture defect (the review gate is doing exactly what it was designed to do — hold unreviewed content back) but it is a capacity defect large enough to make the entire discovery/qualification investment moot. KEEP the gate; REFACTOR the queue into something a single operator can actually clear — triage-by-confidence, bulk actions for clearly-stale backlog, or a deliberate policy decision to bulk-archive the >14-day-stale majority of the queue rather than reviewing it item by item.

**REPLACE**: nothing wholesale. No current subsystem is bad enough to throw away; several (variety lineage, identity resolution, notification) are simply not built yet, which is an ADD, not a REPLACE.

**ADD**: NewsCatcher/APITube or Exa activation (whichever bake-off wins); variety-lineage relationships fed from the already-built BigQuery Patents adapter; a notification/alerting layer; real pagination; a tenant-isolation model; a governed licensing document.

**STOP BUILDING**: further bespoke acquisition-layer work (RSS/sitemap edge cases) beyond what's already solid — this is commodity territory with diminishing returns; further discovery-provider bake-offs beyond the two already queued (NewsCatcher/CatchAll, Exa) until the graph-depth work in Section 16 has actually happened — more discovery breadth does not fix a 6-Signal graph.

---

## 16. Next 30 days

1. **Clear or deliberately triage the Publication Review backlog** (Appendix A) — 1,710 pending drafts against 3 ever published is the single highest-leverage fix available, and it is not an engineering task, it is an operating decision: either commit real review hours against it, or make an explicit, logged policy call to bulk-archive the >14-day-stale majority (1,620 of 1,710) so the queue reflects genuinely reviewable content instead of accumulated backlog. Ship whichever the operator chooses before anything else on this list — every other freshness fix is downstream of this gate being clear.
2. Ship and activate whichever of NewsCatcher/CatchAll or Exa performs best in a real bake-off (infrastructure already exists; this is an activation decision, not new engineering) — but only after #1, since more discovery volume into an already-570:1-backlogged queue makes the backlog worse, not better.
3. Fix the two known duplicate-Source registrations (TD-108, and the pre-existing hortifrut.com one) and add an onboarding-time host-uniqueness check so a third instance is caught automatically.
4. Wire the BigQuery Patents adapter's assignee/inventor data into a real `parent_variety`/`develops_from`-style relationship, closing the variety-lineage gap directly rather than leaving it as prose.
5. Add a basic notification layer (even just a daily digest email of new Watch activity) — the highest-leverage retention feature currently missing, and the smallest lift of anything in Section 14.
6. Resolve the two documented, real identity gaps (Allberry/Advanced Berry Breeding; USDA-ARS) as a proof that the identity-redirect mechanism actually works beyond its single existing entry.
7. Remove or properly re-classify `assessment-20260821072758-6106-smoke-td-012-berry-scope-20260821-072758` — a smoke-test-style artifact currently sitting in production's trusted Assessment table (Appendix A) — as a matter of basic data hygiene.

## 17. Next 90 days

1. Design and ship a real multi-role trust model (reviewer vs. analyst vs. admin) — required before any second real user, and the largest single blocker to calling this a SaaS product rather than a single-operator tool.
2. Deliberately grow Signal/Assessment volume — set an explicit internal target (e.g. 1 Signal per 20-30 Evidence records, not 1 per 200) and treat it as a tracked product metric, not an incidental byproduct of review throughput.
3. Build the tenant-isolation model needed for private/internal customer-data overlays (product north star #7) — this is a schema and session-auth change, best done deliberately rather than retrofitted.
4. Commission a real licensing/ToS review (News API terms, UPOV PLUTO redistribution, article-body storage) before any paid contract is signed.
5. Add real pagination to Global Search, Live Intelligence, and Pending Review before the next order-of-magnitude Evidence growth makes the hard `limit=48` caps a visible product problem.
6. Design the "COMMUNITY/CHATTER — UNVERIFIED" trust state (schema + Front Page representation) as groundwork for social ingestion, without actually ingesting anything yet.

## 18. Can this realistically become best-in-class?

Yes, conditionally. The hardest thing to build in this category — an enforced, auditable trust boundary between "the internet said this" and "we believe this" — is already built and already better than most well-funded "AI research" competitors bother to build, because it's genuinely tedious, unglamorous engineering with no demo-day payoff. That is the correct foundation for a defensible product.

What stands between here and best-in-class is not a discovery-provider decision — it's making the graph the trust machinery protects actually deep (Signals/Assessments, entity resolution, variety lineage) and making the product usable by more than one operator (roles, tenants, notifications). Those are Sections 16-17's roadmap, not new architecture. The team has now proven, in a single day, that it can identify a real product gap (stale homepage) and close it end-to-end with real production verification rather than a demo. Apply that same discipline to the graph-depth problem next, and this becomes a real, defensible product. Keep spending it on the fourth and fifth discovery provider instead, and it stays a very well-engineered filing cabinet.

---

## Appendix A: Production trusted-freshness funnel forensics (2026-09-01)

**Trigger.** A mid-audit request asked this audit to run `scripts/trusted_freshness_funnel.py` read-only against production. That script does not exist anywhere in this repository — not on canonical (`origin/v2/intelligence-os`), not in the history of any of the ~150 remote branches, not in any open PR, and it returns zero hits on a GitHub code search across the repo. Rather than fabricate that script or its output, this appendix builds the equivalent read-only diagnostic directly against the real production data structures (already deeply familiar from this session's own build work) and reports only measured numbers. Similarly, "Cursor's red-team verdict" referenced alongside this request could not be located anywhere in the repo, branches, or PRs available to this audit — it is not incorporated below because its content is not available to verify or cite; if it exists as a separate artifact outside this repo, it should be supplied directly rather than assumed.

**Method.** Read-only `docker compose exec` into the live production container (deployed SHA `721dc9a` — Perplexity Semantic Pulse Activation V1; this predates PR #212 and the just-merged PR #213 Continuous Newsroom Intake V1, neither of which has been deployed yet). Every query below calls only `.list()`-style repository/service reads already used throughout the live application (`repos.evidence.list()`, `repos.signals.list()`, `repos.assessments.list()`, `list_discovered_items()`, direct JSON reads of `inbox/evidence/*.json`). Nothing was written, mutated, or deleted. Captured date and published/source date are reported separately throughout, per the mission's explicit instruction never to substitute one for the other.

### Funnel, stage by stage

| Stage | Total | Newest by capture | Newest by real source/published date | Age buckets (by the more meaningful date for that stage) |
|---|---|---|---|---|
| 1. Discovery (raw `media_discovery` items) | 4,267 | 2026-09-01 (today) | 2026-08-26 (6d stale) | by capture: <24h=25, 1-3d=0, 4-7d=289, 8-14d=2,915, >14d=1,038 |
| 2. Qualified discovery (`relevance_screening.decision == "process"`) | 1,639 (38.4% of raw) | 2026-09-01 (today) | not separately tracked at this stage | by capture: <24h=16, 1-3d=0, 4-7d=0, 8-14d=1,600, >14d=23 |
| 3. Acquisition → Publication draft (`inbox/evidence`, `status=draft`, `evidence_role=publication_artifact`) | 1,710 pending | 2026-09-01 (today) | **2026-08-24 (8d stale)** | by source date: <24h=0, 1-3d=0, 4-7d=0, 8-14d=90, **>14d=1,620 (94.7%)** |
| 4. Publication Review (published) | **3** | — | oldest of the three: 2022-12-01; newest: 2026-01-13 | only **1** recorded review event exists in `inbox/review_events/publication_review/` across all of production history |
| 5. "Extraction proposal" | *n/a — does not exist as a distinct persisted stage in this architecture* | — | — | see note below |
| 6-7. Evidence review → Published Evidence (Atomic Evidence, `evidence_role=None`) | 1,268, all `status=published`, **zero pending drafts of this type found anywhere in the inbox** | 2026-09-01 (today, 3 records) | **2026-08-06 (26d stale)** | by source date: <24h=0, 1-3d=0, 4-7d=0, 8-14d=0, **>14d=1,211, unknown=57** — **zero published Evidence records anywhere in production have a real-world source date newer than 14 days** |
| 8. Signal | 6 | — | — | all 6 are `status=proposed`; none have ever progressed to `monitoring`/`confirmed`; none carry an update timestamp |
| 9. Assessment | 6 (one more than this audit's earlier count of 5 — see finding below) | — | only 1 of 6 carries an `as_of_date` (2026-08-21) | all 6 are `status=active` |

**Note on stage 5 (Extraction proposal).** The funnel this audit was asked to trace assumes a distinct "extraction proposal" holding queue between Publication Review and Evidence Review. No such queue exists as persisted state in this codebase: there is no `extraction_proposals` folder anywhere under `inbox/`, and the 1,268 published Atomic Evidence records (`evidence_role=None`) have **zero corresponding pending drafts** anywhere in the inbox at the moment of this read. This means Atomic Evidence extraction and Publication review are two structurally separate paths converging on the same `data/evidence` table, not one linear pipeline — the older, higher-volume path (1,268 published, direct-to-Evidence) and the newer, near-empty path (3 published, gated by Publication Review) do not currently feed each other. That is itself a finding, not a gap in this reporting: it means "Atomic Evidence extracted from a published Publication" is not yet a real, exercised mechanism in production, despite existing as a documented design intent (Section 2 of the main audit).

### New finding: a smoke-test artifact in production's trusted Assessment table

`assessment-20260821072758-6106-smoke-td-012-berry-scope-20260821-072758` — the id pattern (timestamp + `smoke` + a TD number) is unmistakably a smoke-test artifact, not a genuine analytical Assessment, yet it sits in production's `data/assessments/` alongside the 5 real ones, `status=active`, exactly as if it were trusted output. This was not previously known to this audit and should be corrected as basic data hygiene (Section 16, item 7).

### Direct answers to the addendum's questions

- **Newest genuinely current source item in production:** none, in the sense the question intends. Every stage shows items being *captured* today, but the newest *real-world source date* degrades at each gate: 2026-08-26 at raw discovery → 2026-08-24 in the Publication queue → 2026-08-06 in published, trusted Evidence. Capture activity is current; the trust boundary's output is not.
- **Newest trusted Evidence source date:** **2026-08-06**, 26 days old as of this read (2026-09-01). Zero published Evidence records anywhere in production carry a source date newer than 14 days.
- **Exact transition where freshness is lost:** between qualified discovery and published output — i.e., at the human review gate, not at ingestion. Ingestion and qualification are both current (new items discovered and qualified daily). The loss happens at Publication Review specifically: a 1,710:3 pending-to-published ratio, sustained by a grand total of one recorded review decision in production history.
- **Backlog vs. ingestion as the dominant problem:** **backlog, unambiguously.** Ingestion is not starved — it is outrunning review capacity by orders of magnitude. Adding more discovery providers (Section 6 of the main audit) would make this ratio worse, not better, until the review gate itself is addressed.
- **Review throughput, if calculable from real history:** **not calculable.** One recorded Publication Review decision exists in production. This independently confirms a finding already surfaced during this session's own build work: `review_event_analytics()` refuses to compute a rate below 30 decisions across 2 days — production has 1 decision, total, ever.

### KEEP / REFACTOR / REPLACE verdict for ingestion/review architecture, incorporating this evidence

**KEEP** the trust gate itself — Publication Review correctly refusing to auto-publish unreviewed content is the system working as designed, not a defect. **REFACTOR** the queue's operability: at 1,710 pending items with a single operator, no bulk/triage tooling, and no confidence-based ordering, the queue is mathematically unclearable by hand at any sustainable review pace — this needs bulk actions, staleness-aware triage (the >14-day-stale 94.7% majority is a strong candidate for an explicit bulk-archive policy decision rather than item-by-item review), or both. **Do not REPLACE** the architecture — the qualification/dedup/provenance layers upstream of the gate are sound and already validated in this audit (Sections 2, 6); the defect is queue *operability*, not queue *design*. This is also, concretely, why Section 15's "STOP BUILDING" call on further discovery-provider integration is not a stylistic preference but a direct consequence of this data: every additional provider adds volume to a queue that cannot currently clear the volume it already has.

("Cursor's red-team verdict" could not be located to weigh against this — see the Trigger note above. If it exists and is supplied, this appendix's verdict should be revisited against it explicitly, but is not assumed to already agree or disagree with it.)
