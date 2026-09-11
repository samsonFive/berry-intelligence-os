# Continue Berry OS repairs

Work in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-astra-repair`, branch `fix/astra-news-reader`. Read `artifacts/astra-repair/REPAIR-CHECKPOINT.md` first for the latest commit, verification, screenshots, and outstanding issues. Do not restart the investigation from scratch.

Johnny authorizes autonomous investigation, implementation, focused tests, browser verification, and coherent commits on this isolated branch. Do not merge, deploy, change production data, rewrite shared Git history, expose credentials, or send messages to others. Continue without non-blocking questions. Preserve a reviewable checkpoint and a refreshed continuation prompt before running out of usage. Do not consume usage-reset credits unless explicitly requested. No subagents unless separately authorized.

The product acceptance path is: **search Cal Giant → canonical company → last 90 days by publication date → readable sources/excerpts with honest quality and review status → complete company report and PDF**. The current production app at `https://intel.johnnyaceii.com` embarrassed the user: no canonical company, mismatched UI, old stories shown as current, contaminated source captures, and missing recent coverage found with ordinary web search. Prioritize actual intelligence value and collection reliability next; more empty UI panels will not solve this.

Read `AGENTS.md`, `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`, and the existing repair brief in the parent directory. Respect publication review, source-fidelity review, and atomic-claim review as separate human gates. Never fabricate article bodies, trust, analysis, relationships, or screenshot data. Pending items stay private. Avoid new parallel discovery engines: reuse Industry Pulse, media discovery/acquisition, Source Health, and the existing reader.

What exists now:
- News homepage with publication-date windows, filtering/pagination, shared reader and cleaner stakeholder navigation.
- Read-time access-screen detection across news, readers, evidence, and timelines; raw stored evidence is preserved.
- Canonical California Giant Berry Farms with aliases including Cal Giant. Existing mention recall resolves historical articles without inventing graph relationships.
- Company 90-day coverage panel and report handoff. Reports have an uncapped current article inventory and excerpts; pending rows remain outside trusted synthesis. Undated rows are separate. PDF no longer automatically claims analyst review.
- Read-only audit: `python scripts/audit_company_coverage.py company-california-giant-berry-farms --as-of 2026-09-11`.

Critical remaining collection problem:
- The checked-in snapshot has 20 Cal Giant mentions, nine access-screen captures, and zero published articles in June 14–September 11, 2026. These are LOCAL counts. User's production audit reported 25 historical records / 14 contaminated / one pending current item; do not conflate environments.
- Two Cal Giant source entries were blank-URL manual references. They now point to the official newsroom, but remain reference sources; this is NOT functioning automated acquisition.
- Official news listing: `https://www.calgiant.com/news/press-releases/`.
- Verified coverage gaps: Aug 3, 2026 Back-to-School Label; July 14, 2026 IFPA Foodservice Conference; June 29, 2026 Organic Produce Summit; June 15, 2026 Pacific Northwest blueberry season. Verify exact dates and URLs again before collection.
- Known URLs: `https://www.calgiant.com/newsroom/california-giant-berry-farms-introduces-back-to-school-label-to-inspire-shoppers/` and `https://www.calgiant.com/newsroom/california-giant-berry-farms-to-showcase-year-round-berry-solutions-and-menu-innovation-at-ifpa-foodservice-conference/`.
- Direct HTTP feed/article acquisition returned 403. Indexed browser/search text being accessible does not prove the app collector works. Diagnose a supported forward acquisition route, honest blocked status, and lawful alternate publisher coverage; do not bypass access controls or label consent text as content. Stage any real source recovery or new source items privately for review, never auto-publish.

Next bounded milestone:
1. Reproduce current source discovery/acquisition using a small real Cal Giant acceptance set. Make failures and last successful capture visible; distinguish reference/manual, discovered, blocked, pending, published, and readable. Do not present a source count as recall.
2. Repair existing pipeline defects that prevent recent, relevant articles reaching private review with source URL, verified publication date, and usable text. Add targeted fixture tests from real failure shapes without committing copyrighted full bodies or credentials.
3. Verify company/search/report date filters agree, pending data never reaches static output or trusted model grounding, and report inventories do not silently cap articles.
4. Review the wider build guide only after this path materially works; prioritize what supports real stakeholder decisions.

Runtime: use `../berry-intelligence-os/.venv/Scripts/python.exe` (the parent repo's Python 3.13 environment). System Python lacks dependencies. Git may need per-command `-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-astra-repair`; do not globally disable safe.directory. Default autocrlf applies; do not force false and stage whole-file line-ending churn. The original sibling checkout contains pre-existing work; leave it alone.

Validation: focused pytest first, then full pytest / `scripts/validate_records.py` / `scripts/build_static.py` including private-state leakage tests. Full suite takes roughly ten minutes. Use browser tools for local UI checks and save actual screenshots. Local preview may still run at `http://127.0.0.1:8018`; verify its process before restarting only that owned server. No remote model calls are required for deterministic report verification; pass `completer=None` or patch `maybe_untrusted_completer` only in verification code.

Keep context economical: read targeted files, run small focused tests during iteration, run the full suite once near the checkpoint, and record reproducible facts rather than repeating broad repository audits. Finish with commit IDs, real screenshots, test outcomes, material limitations, and the next concrete acceptance test.
