# Blueberry Landscape Explorer — review packet

This is the blueberry checkpoint of the larger mission. **No merge or deployment; remaining berries require feedback first.** The [mission checklist](LANDSCAPE-EXPLORER-MISSION.md) preserves all remaining scope.

[Draft PR #313](https://github.com/samsonFive/berry-intelligence-os/pull/313) is the review checkpoint. It remains a draft.

## Open the candidate

[Local preview](http://127.0.0.1:18342/landscapes/explorer). This uses canonical repository data and a separate empty private inbox. It does not use synthetic landscape data, production user state or a paid inference provider. The existing redesign preview on port 18331 is unchanged.

Branch: `feature/landscape-explorer`. Base: `v2/intelligence-os` at `7962ac04dd05855985f51596f3f8070f19990a75`. The draft PR description records the final exact HEAD and required-check run; resolve this checkout with `git rev-parse HEAD`.

Start/restart from the feature checkout with the established project Python environment:

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

These are local loopback review settings, not remote/public deployment settings. Existing remote session authentication protects every explorer format when enabled; published-only mode returns 404.

## Five-minute, evidence-backed walkthrough

1. **Read the three lanes.** Default Chile / China / Peru has 53 nodes, 82 sourced connections, 47 records / 19 clustered source origins. Its 10 company-location links do not establish variety growing footprints. Note the separate genetics area and explicit zero direct genetics-location links.
2. **Inspect an honest location caveat.** Under China choose Fall Creek's **Intent only** connection. It resolves to `rel-fall-creek-operates-sekoya` and `ev-produce-report-sekoya-china-2025`. Publication/effective date is November 13, 2025; source capture is August 3, 2026. This is stated market intent, not a completed market entry. Compare Hortifrut's test stations and Mountain Blue's rights enforcement labels.
3. **Follow the actual breeding links.** Focus **Fall Creek Blueberry Breeding Program** in Connected genetics. Six of its eleven direct variety links appear initially; Show all expands them. Select SEKOYA Nova and inspect the breeder/developer relationship `rel-fall-creek-program-develops-sekoya-nova`, citing `ev-produce-report-sekoya-nova-2026`. Company trial links are labeled separately; they do not automatically assign every program variety to Chile or China. Relationship table offers the same keyboard-accessible evidence action.
4. **Separate the clocks.** Expand Refine relationships & dates. Choose Custom dates, March 1–31, 2026, and Recorded event / effective date; Apply, then Changes. Seven connections are dated in that window: Fall Creek's Chile location plus six explicit variety trial links. Switch to First captured: source captures belong to a different window. Past 7 days can legitimately be empty in this retained corpus. Standing landscape links remain visible. Explain → What changed cites only the selected clock/window.
5. **Check trust and take a briefing.** Explain the selected markets or selected genetics; every finding opens supporting evidence, while interpretation/unknowns stay distinct. To inspect ownership conflict, use all countries and focus Berry Blue LLC: the Hortifrut and Michigan Blueberry Growers ownership records remain disputed. Download printable HTML, vector SVG and CSV from Export briefing; all selected relationships/sources are included, even when display limits hide some. Reload the URL to return to the same focus, filters and source selection.

## Artifacts

- [Desktop evidence](../../artifacts/landscape-explorer-blueberry/desktop-evidence.jpg).
- [Dark workspace](../../artifacts/landscape-explorer-blueberry/desktop-dark.jpg).
- [Phone controls](../../artifacts/landscape-explorer-blueberry/mobile-controls.jpg), [stacked country lanes](../../artifacts/landscape-explorer-blueberry/mobile-lanes.jpg), [phone evidence](../../artifacts/landscape-explorer-blueberry/mobile-evidence.jpg), [dark phone evidence](../../artifacts/landscape-explorer-blueberry/mobile-dark-evidence.jpg), and [contained export menu](../../artifacts/landscape-explorer-blueberry/mobile-export-menu.jpg).
- [Focused program connections](../../artifacts/landscape-explorer-blueberry/desktop-focus.jpg) and [cited visual explanation](../../artifacts/landscape-explorer-blueberry/desktop-explanation.jpg).
- [Downloaded standalone briefing](../../artifacts/landscape-explorer-blueberry/blueberry-briefing.html), [briefing preview](../../artifacts/landscape-explorer-blueberry/briefing-preview.jpg), [vector portrait](../../artifacts/landscape-explorer-blueberry/blueberry-portrait.svg), and [relationship/source CSV](../../artifacts/landscape-explorer-blueberry/blueberry-relationships.csv). These actual native downloads use the same default three-country scope: 82 relationships / 47 sources / 97 relationship-source CSV rows. A program focus can be selected and remains in export metadata without cropping out the rest of that selected scope.
- [Measurements and export parity](../../artifacts/landscape-explorer-blueberry/verification.json).

No artifact asserts growing presence unsupported by a canonical edge.

## Validation status

- Final focused explorer: **44 passed**. Related explorer / retained Landscape / saved Landscape workspace / remote authentication / synthesis regression: **139 passed** before the final recovery-page addition; the new recovery case and all explorer cases passed afterward.
- The first complete local run had **3,945 passes / 9 skips and one obsolete navigation-label assertion**. That assertion was corrected to verify both the retained Landscape overview and new Explorer entry, and the focused regression passed. The first pushed candidate then passed all four required GitHub checks, including the full Python suite ([run 37498703589](https://github.com/samsonFive/berry-intelligence-os/actions/runs/37498703589)). The final HEAD's full check set and run link are recorded in the draft PR description at delivery; no first-candidate result substitutes for final-head checks.
- Canonical record validation passed. JavaScript syntax and diff whitespace checks passed. The complete local static build wrote **1,755 pages** and verified that unpublished draft IDs/titles were absent. No canonical records, domain schemas or protected expansion-guide changes.
- Native browser review: desktop 1280×720 and phone 390×844, light/dark, stacked lanes, scroll-safe evidence, country multi-select and URL reload/reset, focus expansion, all three explanations, custom event versus capture windows, empty recent window, disputed ownership, keyboard Enter in the table, company/variety contextual entries, and the existing slide-over Reader. The Reader opens existing article/brief controls; this corpus example has no stored full article text, which remains honestly labeled.
- Native download review: HTML, SVG and CSV succeeded. Complete IDs, review scope and version match the API; SVG XML parses and retains the source links. Inline printable HTML was visually inspected. SVG is a continuous vector with readable panels, not a paginated PDF.
- Selection errors return an understandable recovery page with a reset link; APIs retain structured 422 errors. Authorization remains fail-closed outside analyst mode and on unauthenticated remote access. No paid inference/acquisition ran.

## Performance and limits

Windows laptop, Python 3.13 existing virtual environment; real browser 1280×720 and phone 390×844. Final JSON payload: **396,063 bytes**, 53 nodes / 82 edges / 47 sources. Three complete API samples: **434.05, 192.65, 225.66 ms**. Native markup/data binding was **2.10 ms** and program focus/highlighting **7.80 ms**; these measure the post-data UI work, not first network paint. Earlier cold adapter construction was about 84 ms. No console errors were observed in the Explorer. A separate synthetic backend test exercises the 100-node / 200-edge display bound and complete export preservation; a maximum-size synthetic browser run was not performed. Synthetic evidence never enters the preview or exports. Measurements and their limits are stored with the artifacts.

Corpus limitations are separate from software behavior: no direct genetic geography; four provisional variety identities; legacy inferred/substituted role mappings; incomplete event chronology and verbatim locators; conservative source clustering; company annotations excluded from reviewed graph; no model-assisted new facts. Large SVGs are tall multi-panel vectors; printable HTML provides pagination. Downloadable PDF, saved explorer views, remaining berries and cross-berry comparisons are Milestone B.

## Feedback requested

Please review **readability** (lanes and connection diagram), **trust** (location meanings, roles, dates, conflicts and identity caveats), **analyst usefulness** (whether the questions and focus/table flow answer real work), and **export quality** (what you would share in a meeting). Specific changes are welcome before the other-berry rollout. The milestone pause is required by the supplied brief, not a routine permission checkpoint.
