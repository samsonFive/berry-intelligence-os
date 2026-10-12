# Blueberry Landscape Explorer — revised review packet

For the October 9 integrated candidate, use [the current handoff](BLUEBERRY-INTEGRATED-REVIEW-HANDOFF.md).
The ports, catalog counts, screenshots and checks below describe the earlier
#313 checkpoint and remain historical evidence, not the latest release state.

This is the blueberry checkpoint in [draft PR #313](https://github.com/samsonFive/berry-intelligence-os/pull/313). No merge, deployment or other-berry rollout. The [mission checklist](LANDSCAPE-EXPLORER-MISSION.md) and [catalog coverage mission](VARIETY-CATALOG-COMPREHENSIVENESS-MISSION.md) preserve remaining work.

## Open the candidate

[Local preview](http://127.0.0.1:18342/landscapes/explorer) uses canonical repository data and a separate empty private inbox. No synthetic landscape data, production user state or paid provider is used. The preview on port 18331 is unchanged.

Branch: `feature/landscape-explorer`. Base: `v2/intelligence-os` at `7962ac04dd05855985f51596f3f8070f19990a75`. The PR description records the delivered exact HEAD and required-check run.

```powershell
Set-Location C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-landscape-explorer
$env:BIOS_MODE = 'authoring'
$env:BIOS_REMOTE_INTERACTIVE = 'false'
$env:BIOS_BASIC_AUTH = 'false'
$env:ENABLE_SOURCE_POLLING = 'false'
$env:BIOS_DATA_DIR = "$PWD/data"
$env:BIOS_INBOX_DIR = "$PWD/inbox/landscape-preview"
& C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18342
```

These are loopback review settings, not public deployment settings. Every Explorer format retains analyst authorization and remote authentication.

## Five-minute walkthrough

1. **Compare the whole picture.** Read the three cited takeaways, then the company-by-country table. Six company rows show all ten location links in Chile / China / Peru. Distinguish registered offices, breeding tests, market intent, rights enforcement and reported production. These do not establish the growing footprint of every company variety.
2. **Trace genetics without losing the comparison.** Grouped portfolios show programs and connected catalog varieties. Focus Fall Creek's program or SEKOYA Nova; the compact neighborhood expands actual links. Evidence opens when requested; closing it restores full comparison width. Relationship table preserves the same evidence actions.
3. **Check a source against the catalog.** Open evidence under **Control needs checking**. Hortifrut's source shows seventeen named blueberries: eleven portfolio names and six licensed names. Keepsake links to its profile; missing names such as Prelude link to the existing review queue. MBG retains sixteen name/code pairs. Search Prelude in the variety directory: it appears as awaiting approval. Source context does not approve breeder, owner or growing-region claims.
4. **Separate clocks and disputes.** Under Refine relationships & dates, choose March 1–31, 2026 and Recorded event / effective date, then Changes. Seven connections fall in that window; First captured gives a different result. Recent windows can legitimately be empty. Hortifrut and MBG's conflicting Berry Blue ownership accounts remain disputed; the cited takeaway explains what needs checking.
5. **Take a complete briefing.** Export printable HTML, SVG and CSV. All 82 relationships and 47 sources are included, even when display bounds hide connections. HTML includes takeaways and the full-width matrix; source names/catalog status appear in source notes. Reload preserves filters, focus and evidence.

## Catalog repair and remaining coverage

Shared discovery now audits **1,269 published stored sources** against **64 canonical varieties**. It identifies **99 explicit names: 31 catalog matches and 68 review candidates**, compared with 62 mentions / 34 candidates before repair. These are names and possible aliases, not 68 approved new varieties. The isolated preview excludes private photo imports; existing human edits and rejected decisions are preserved when those records are present.

Explicit lists, quoted license names and declared selection-code pairs now enter the existing workflow. Ambiguous aliases do not select the first match; berry boundaries, generic-class exclusions and source references remain intact. Directory searches and source readers reveal gaps. GET requests never acquire sources or persist candidates.

This measures stored-summary recall, not internet completeness. Strawberry and blackberry parsing still returns no names in this audit and needs investigation. The broader mission covers complete primary portfolios, university releases, registry reconciliation, richer cited profiles, freshness and a manually checked multi-berry benchmark. No public “most comprehensive” claim is justified yet.

## Current artifacts

- [Overview](../../artifacts/landscape-explorer-blueberry/desktop-overview-revised.png), [dense matrix](../../artifacts/landscape-explorer-blueberry/desktop-matrix-revised.png), [dark desktop](../../artifacts/landscape-explorer-blueberry/desktop-dark-revised.png).
- [Source-to-catalog links](../../artifacts/landscape-explorer-blueberry/desktop-catalog-evidence.png), [directory search](../../artifacts/landscape-explorer-blueberry/directory-source-name.png), [phone evidence](../../artifacts/landscape-explorer-blueberry/mobile-catalog-evidence.png), [dark phone](../../artifacts/landscape-explorer-blueberry/mobile-catalog-dark.png).
- [Downloaded HTML](../../artifacts/landscape-explorer-blueberry/blueberry-briefing.html), [briefing preview](../../artifacts/landscape-explorer-blueberry/briefing-revised.png), [SVG](../../artifacts/landscape-explorer-blueberry/blueberry-portrait.svg), [CSV](../../artifacts/landscape-explorer-blueberry/blueberry-relationships.csv).
- [Repeatable catalog audit](../../artifacts/landscape-explorer-blueberry/variety-catalog-audit.json), [current measurements/parity](../../artifacts/landscape-explorer-blueberry/verification-revised.json).

Older `.jpg` screenshots and `verification.json` describe the preceding checkpoint, not this revision.

## Validation and limits

- Revised discovery/navigation/seed/Explorer regression: **91 passed**. After the final HTML layout repair, all **46 Explorer tests** passed again. One existing ReportLab deprecation warning remains.
- Required GitHub checks on the delivered exact HEAD are recorded in PR #313: Change scope, Repository integrity, Static public safety and Python tests. Earlier runs do not substitute for final-head checks.
- Canonical validation, JavaScript syntax and diff whitespace checks passed. No canonical data, schema or expansion-guide change. Human publication, claim and identity gates remain intact.
- Native browser review: 1280×720 desktop and 390×844 phone, light/dark, compact comparison, scroll-safe evidence, source-to-review navigation and directory lookup. Phone document width was 375 pixels; tables scroll internally without horizontal page overflow. Prior date/focus/authentication cases remain covered by tests.
- Native HTML/SVG/CSV downloads match every relationship/source ID and data version. CSV has **97 relationship-source rows**; SVG XML parses and retains links. Final HTML was visually inspected after correcting a nested-grid defect.
- Current API payload: **711,662 bytes**; three complete requests took **354.74, 302.51, 286.93 ms** on this laptop. This is the real 53-node/82-edge corpus, not a maximum-size browser benchmark. The 100-node/200-edge bound and complete exports are separately tested with synthetic backend fixtures.

Default scope remains 53 nodes / 82 relationships / 47 sources / 19 clustered origins, with ten company-location links and **zero direct genetic-location links**. Four identities remain provisional; legacy role caveats, incomplete chronology and source locators stay visible. Discovered names create neither graph edges nor approved identities. SVGs are continuous multi-panel vectors; printable HTML provides pagination. PDF, saved Explorer views, other berries and cross-berry comparison remain Milestone B.

## Review checkpoint

Review revised **readability, trust, analyst usefulness and export quality** before other-berry rollout. The blueberry pause is required by the supplied brief. The catalog mission and ongoing redesign goal remain open.
