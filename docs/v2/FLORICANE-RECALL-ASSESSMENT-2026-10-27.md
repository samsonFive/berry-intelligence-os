# Floricane / Blackberry live recall assessment

Assessed October 27, 2026 against review commit `5d90a66e`. This is a targeted live check, not aggregate search-quality acceptance or deployment approval.

## Result

Combined archive + web Report Builder research now retrieves and cites the two inspected Ervin primary sources for the original typo and two equivalent questions. The newly added recurring Keyword Monitoring query did **not** increase unique News coverage in this live sample. Archive-only coverage remains empty for these questions in the checked-out canonical corpus.

## Actual Report Builder path

The assessment called `build_report_packet`, `attach_topic_research` and `topic_sections`, using the existing Perplexity Search integration, registry-derived cultivar follow-ups, source capture and citation selection. Scope was Blackberry, Global, combined archive + web, with no publication-date restriction. No fixed answer URLs or hand-injected articles were provided to discovery. The original pre-mission Global Search implementation at `94a3b99bfd3936a65136fd54c73f5006fa51ba45` was compared against the same local evidence corpus. It is an archive baseline, not a replay of the unavailable original production report request.

| Wording | Original archive matches | Current archive matches | Web candidates retained | GPG primary rank | NC State primary rank | Both cited in recent findings |
|---|---:|---:|---:|---:|---:|---|
| Blackberry Floricans | 0 | 0 | 20 | 2 | 3 | Yes |
| Floricane blackberry developments | 0 | 0 | 20 | 2 | 3 | Yes |
| New blackberry varieties that fruit on second-year canes | 0 | 0 | 20 | 2 | 3 | Yes |

The 20 retained candidates are not 20 verified relevant developments. The checked acceptance claim is limited to the two primary pages and their inclusion in generated cited sections. All three actual report searches completed without provider search errors. Captured-body counts were 30/40, 21/28 and 26/31 discovered candidates respectively. The two checked primary pages had full captures and source publication dates. Discovery/source capture took 32.62, 14.48 and 13.95 seconds. This measures the service path through section generation; no new browser report was saved or production report regenerated in this assessment.

The inspected sources support two separate milestones:

- [NC State, February 8, 2026](https://rubus.ces.ncsu.edu/news/meet-ervin-blackberry/): introduction of Ervin as a floricane-fruiting blackberry, previously trialed as NC 740.
- [Global Plant Genetics, September 1, 2026](https://www.globalplantgenetics.com/introducing-ervin-the-latest-introduction-nc-states-breeding-programme/): licensing for development outside the United States. This does not establish commercial sales or planted acreage in particular countries.

FreshPlaza's September 3 report ranked first but covers the licensing announcement; it is not a third independent development. The report currently retains both that article and the primary licensing page, so event-level duplication remains open.

## Recurring News / Keyword Monitoring

Live Google News RSS calls used the application's real provider and `_keep_window_hits` pipeline, with October 27 as the evaluation date. The broad baseline was the existing default Blackberry query with its industry topics and `when:30d`. The added monitor was `(Floricane) AND (blackberry OR blackberries OR zarzamora) when:30d`.

| Query | Raw RSS candidates | Retained by News pipeline | Additional unique candidates from new monitor |
|---|---:|---:|---:|
| Existing broad Blackberry search, 30 days | 81 | 10 | Baseline |
| New Floricane + Blackberry monitor, 30 days | 1 | 1 | 0 raw and 0 retained |

The one new-monitor candidate is [HortiDaily's October 22 Rejoice article](https://www.hortidaily.com/article/9885365/greenhouse-propagation-and-primocane-genetics-for-flexible-production-in-blackberries/). Its subject is primocane production; floricane is mentioned as comparison. It was already present in the broad baseline. Therefore this run does not demonstrate incremental direct floricane-development coverage from the new monitor.

Removing the date restriction from the same compiled monitor returned 10 RSS candidates, including FreshPlaza's September Ervin coverage. Restricting the query to 2026 returned seven. Neither query found both inspected primary pages in Google News RSS. A cultivar-name probe returned 13 candidates, with significant unrelated material; more candidates is not automatically better recall.

News independently enforces a 30-day publication window after discovery. Merely broadening the provider query would therefore still exclude the February introduction and September licensing coverage from today's News feed. Historical research needs a separate broader time scope and acquisition path. Saving a monitor is prospective configuration and does not backfill the archive.

## Acceptance and next work

- Targeted combined-research regression: demonstrated for the original wording, corrected question and second-year-cane paraphrase, with inspected primary passages and citations.
- Archive-only regression: unresolved in the local canonical corpus; no historical backfill occurred.
- Incremental recurring-monitor recall: not demonstrated in this sample.
- Broader search mission: remains open. Google organic parity, full source-inspected relevance judgments, event clustering and historical acquisition remain required; candidate counts cannot substitute for these checks.

Next work should distinguish prospective monitoring from retrospective research/backfill, expose the effective collection/research time range, and evaluate newly acquired article bodies and direct floricane relevance before claiming a recall gain. Do not silently relax News's freshness contract or persist unreviewed web discoveries as trusted Evidence.

Raw RSS responses as normalized candidates, report source captures, generated section excerpts, query traces and timestamps remain in gitignored `inbox/search-quality-evaluation/floricane-assessment-2026-10-27/assessment.json`. No production configuration, source onboarding, trust promotion, merge or deployment was performed.

## Subsequent historical-backfill implementation

The new explicit backfill was subsequently live-tested in the isolated review runtime. It collected six older matching articles, including the two checked Ervin primary pages. The actual app's archive-only report assembly now retrieves all six and cites both primary sources for each of the three regression wordings, with web discovery forbidden during verification. These are acquired, pending/unreviewed publication drafts, not published Evidence. See KEYWORD-MONITOR-BACKFILL-V1.md for bounds and validation. The earlier recurring News result remains unchanged; this is a separate historical acquisition path. Deployment remains held.
