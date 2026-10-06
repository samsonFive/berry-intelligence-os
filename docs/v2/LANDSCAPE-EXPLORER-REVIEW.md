# Blueberry Landscape Explorer — review packet

This is the blueberry checkpoint of the larger mission. **No merge or deployment; remaining berries require feedback first.** The [mission checklist](LANDSCAPE-EXPLORER-MISSION.md) preserves all remaining scope.

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
- [Downloaded standalone briefing](../../artifacts/landscape-explorer-blueberry/blueberry-briefing.html). This real native download retains the selected Fall Creek program focus and the complete three-country scope.
- Additional mobile, focus, explanation and vector/CSV artifacts are added as the final native walkthrough completes. No artifact is an assertion of growing presence unsupported by a canonical edge.

## Validation status

- Focused explorer: 38 cases passed before the inline briefing preview was added; final focused and authentication checks are rerun on the final implementation.
- Landscape plus new explorer: 60 passed. The full first local run had 3,945 passes / 9 skips and one old navigation-label assertion; it expected the former More-menu wording. That assertion was updated to verify both the retained Landscape overview and new Explorer entry, and the focused run passed.
- Canonical record validation passed; JavaScript syntax passed; no canonical records/domain schemas or protected expansion guide changes.
- Final complete suite, static/public safety, exact-head CI and native mobile/export outcomes are recorded here before checkpoint delivery. Until then this remains a draft candidate.

## Performance and limits

Windows laptop, Python 3.13 existing virtual environment; real browser 1280×720. Initial read-model benchmark: 53 nodes / 82 edges, 47 sources, about 0.084 seconds, approximately 386 KB JSON before final provenance fields. Native page startup binding was 11.30 ms and program focus/highlighting 7.50 ms, well below the 200 ms selection budget. Final measurements and payload sizes are stored with the artifacts. Backend synthetic 100-node / 200-edge display bounds are tested separately; synthetic fixture evidence never enters the preview or exports.

Corpus limitations are separate from software behavior: no direct genetic geography; four provisional variety identities; incomplete event chronology and verbatim locators; conservative source clustering; company annotations excluded from reviewed graph; no model-assisted new facts. Large SVGs are tall multi-panel vectors; printable HTML provides pagination. Downloadable PDF, saved explorer views, remaining berries and cross-berry comparisons are Milestone B.

## Feedback requested

Please review **readability** (lanes and connection diagram), **trust** (location meanings, roles, dates, conflicts and identity caveats), **analyst usefulness** (whether the questions and focus/table flow answer real work), and **export quality** (what you would share in a meeting). Specific changes are welcome before the other-berry rollout. The milestone pause is required by the supplied brief, not a routine permission checkpoint.
