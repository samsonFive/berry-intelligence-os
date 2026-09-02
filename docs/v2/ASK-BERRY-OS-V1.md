# Ask Berry OS / Strategy Research Desk V1

Date: 2026-09-01

## Completion report

1. **Research Desk architecture.** `/research` is an authenticated stakeholder surface over a single orchestration service, `app/services/research_desk.py`. It resolves scope, builds a canonical packet immediately, runs bounded live discovery asynchronously, and renders a composed intelligence brief. It creates no repository and no new trust object.
2. **Natural-language scope handling.** Deterministic report-scope parsing and canonical entity resolution identify companies, varieties, berries, geography, timeframe, topic, intelligence type, and comparison intent. The interpreted scope is visible. Ambiguous or unresolved identity is retained as a warning, never silently guessed.
3. **ResearchPacket design.** The packet selectively includes trusted facts/evidence, companies, varieties, geography, relationships, rights/IP, market context, signals, assessments, source index, and explicit gaps. Topic and entity scope determine which layers are requested.
4. **Live-research integration.** One scoped query runs per configured provider through the existing `DiscoveryProvider` abstraction. Google News and Perplexity were available during acceptance; CatchAll is cache-only through existing background hits. Returned material remains structurally separate from canonical truth.
5. **Trusted-layer integration.** Published Evidence uses the repository's existing `evidence_trust_tier()` labels. Facts, Signals, and Assessments stay distinct; the UI never converts a provider hit into Evidence.
6. **Structured-data integration.** Company/variety/relationship records and `patent_record` / `plant_breeders_rights_record` evidence are rendered as structured intelligence, not disguised as articles.
7. **Semantic expansion.** When Exa is configured, the service permits exactly one additional bounded semantic query and marks its results `RELATED / EMERGING`. Exa was not configured in the acceptance environment, so this path was contract-tested rather than live-provider-tested.
8. **Synthesis/citation discipline.** Deterministic findings carry packet source IDs. Optional model synthesis sees only public source title, publisher, date, and already displayed live snippet. Unknown citation IDs and unsupported claims are dropped; private/internal record text is not sent.
9. **Comparison mode.** A two-company request reuses Company Compare presentation to show current developments, regions, varieties, rights/IP, partnerships/relationships, trusted coverage, and differences without a generalized matrix framework.
10. **Follow-up behavior.** A follow-up posts the prior structured scope, not article bodies. New explicit dimensions replace the prior dimension while unmentioned company/window context carries forward.
11. **Create Brief handoff.** `Create leadership brief` posts the confirmed scope and research question into the existing Report Builder preview. That preview shows preselected source-backed developments or an explicit in-window gap before the user generates or persists anything.
12. **Stakeholder UI.** The new stakeholder shell presents an editorial research terminal: simple question entry, examples, visible scope, composed sections, trust badges, comparison, gaps, sources, packet rail, and brief action. It has no chat bubbles or old workbench chrome.
13. **Time to first content.** Real seven-question acceptance measured 368–2,173 ms for the canonical answer (median 686 ms). Content appears before live providers complete.
14. **Complete-answer latency.** Real configured-provider acceptance measured 2,938–7,014 ms for the sampled questions (median 3,779 ms). No 20-second blank wait occurred.
15. **Acceptance Q1 — “What has Planasa done in the last 30 days?”** Scope resolved Planasa/30d. Packet: 7 trusted, 30 structured, 0 qualifying live, 7 findings. Canonical results covered current variety and relationship context; the answer correctly did not invent live activity. Manual research later exposed one specialist variety-rights miss (TD-112). Useful, with an honest current-recall limitation.
16. **Acceptance Q2 — “What is happening in European blueberry genetics?”** Scope resolved Blueberry/Europe/genetics. Packet: 36 trusted, 30 structured, 5 live, 7 findings. Live results included current Oregon-variety and UK-industry coverage; canonical context added European genetics records and rights. Useful.
17. **Acceptance Q3 — “What competitors are expanding berry production in Peru?”** Scope resolved Peru/expansion/supply. The tightened generic-berry query returned relevant Peru expansion/export material, including Vaighai and El Niño/acreage context, alongside trusted Proarándanos context. It missed a material current Camposol facility expansion (TD-112). Useful but non-exhaustive.
18. **Acceptance Q4 — “What should I know about Hortifrut right now?”** Scope resolved Hortifrut/7d. Packet: 5 trusted, 4 initial live results, 7 findings; canonical intelligence was strong, while live results included same-name/company-directory noise. The answer remained source-traceable and trust-separated, but this is the weakest precision case and is included in TD-112.
19. **Acceptance Q5 — “What new PBR or patent developments matter for berry genetics?”** Scope resolved genetics/rights. Four structured rights/IP records were identified and prioritized; no qualifying current live hit was found. Undated structured coverage is stated as a gap instead of being presented as current news. Useful for known IP context, not an exhaustive new-filings search.
20. **Acceptance Q6 — “What are the important emerging developments in blackberry?”** Scope resolved Blackberry/emerging without the earlier false `supply` substring match. Crop relevance filtering rejected BlackBerry device/stock and garden noise; the remaining live result concerned seedless blackberry innovation. Useful and precise at small volume.
21. **Comparison acceptance — “Compare Planasa and Fall Creek.”** Both canonical companies resolved in requested order. Packet: 19 trusted plus company graph/relationships/varieties/rights context. The rendered two-column comparison and key differences were visually verified, and the Create Brief transition preserved both companies.
22. **Manual-research challenge.** Three bounded ordinary-web comparisons were run: Planasa 30d, European blueberry genetics, and Peru expansion. Ask Berry OS found overlapping current specialist results and supplied canonical company/variety/relationship/rights context in one sourced view. Manual tabs found two material results the configured live pass missed. The app still provided a clear productivity advantage by resolving entities, joining current and durable intelligence, separating trust, exposing gaps, and preparing a brief in one workflow.
23. **Material misses.** A 2026-08-10 Planasa Plablue 15122 specialist rights listing and a 2026-08-27 Camposol Chao capacity expansion did not appear. Hortifrut live precision was uneven. These are recorded as active TD-112; no perfect-recall claim is made.
24. **Unique app advantages.** Canonical identity, company/variety/geography graph context, structured IP/rights, durable trusted Evidence, Signals/Assessments, explicit gaps, one source trace, stakeholder comparison, and an immediate Report Builder handoff were all absent from the ordinary-tab workflow.
25. **Focused tests.** Scope, entity resolution, follow-ups, topic boundaries, packet composition/immutability, trust segregation, provider neutrality, blackberry noise, citation/security boundary, comparison, brief handoff, invalid browser state, and endpoint state were covered. Result: 116 passed.
26. **Visual QA.** Playwright Chromium checked landing, completed desktop result, and 390 px mobile result. Desktop and mobile had zero horizontal overflow; all result sections and the brief action rendered. The comparison was readable and the trust system visually distinct.
27. **Final suite.** 2,435 passed in 13m41s on Windows after the clean rebase onto current canonical; only existing dependency deprecation warnings were emitted. Canonical record validation and the 1,628-page static build/leakage verification also passed.
28. **CI.** Pending PR gate: Change scope, Repository integrity, Static public safety, Python tests.
29. **PR.** Pending.
30. **Merge SHA.** Pending.
31. **Deployment state.** Pending. Interactive `/research` is deliberately absent from the static public snapshot and requires the private FastAPI deployment.
32. **CODE COMPLETE?** YES.
33. **PRODUCT ACCEPTED?** YES — it is materially more useful than manual tabs for the tested strategy workflow, with imperfect current-web recall explicitly disclosed in TD-112.
34. **DEMO READY?** YES locally: question → trusted content → live completion → source trace → comparison → Create Brief works without architecture narration. Hosted deployment proof remains item 31.

## Product boundaries

- No vector database, agent framework, new ontology, provider integration, trust queue, or market ingestion was added.
- Market Reality has a clean optional `market_context_provider` seam and can join the packet without redesign.
- Counts are labeled as coverage, never performance or confidence scores.
- “No result” means no result in the configured bounded sources, never proof of absence.
