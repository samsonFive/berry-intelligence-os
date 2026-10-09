# Blueberry Landscape and workflow guide — integrated review

The revised blueberry checkpoint is ready for UI feedback. The complete
Landscape mission and comprehensive variety-catalog mission remain open.
This is a local review candidate, not a merged or deployed release.

## Candidate identity

- Review draft: [PR #374](https://github.com/samsonFive/berry-intelligence-os/pull/374). Fresh exact-head checks are separate from the all-green parent.
- Branch: `feature/blueberry-review-handoff`.
- Parent: `feature/variety-original-corpus-followup`, draft [#373](https://github.com/samsonFive/berry-intelligence-os/pull/373), `5a707a0741cd506b7464cabec8fc7f751830b927`.
- Canonical baseline: `v2/intelligence-os`, `7962ac04dd05855985f51596f3f8070f19990a75`.
- The delivered draft PR description records its final HEAD and exact-head checks. Resolve the current checkout with `git rev-parse HEAD`; do not mistake the parent SHA for this delivery.
- Parent #373 has all four required checks green: 4,522 passed, 11 skipped, two warnings in 756.73s; run `37904296369`, Python job `113734005787`. This is parent evidence, not a substitute for the new draft's CI.

## Open the actual app

[Landscape Explorer](http://127.0.0.1:18568/landscapes/explorer) and
[the visual workflow guide](http://127.0.0.1:18568/guide) use the real repository
data and an isolated private runtime. These loopback URLs work on this PC, not
directly on a phone outside this computer. No authentication boundary is relaxed
to publish a remote preview.

If the preview stops, run the retained local launcher in this checkout:

```powershell
Set-Location C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-variety-source-coverage
& C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os/.venv/Scripts/python.exe -X utf8 inbox/european-portfolio-followup/apg_live_preview.py
```

The launcher binds only `127.0.0.1:18568`, disables source polling, and preserves
its existing private inbox. Never copy these local settings to a public host.

## What changed

The portfolio table gives more width to the variety names and shows recorded
direct company roles in place of repeated instructions. Owning a program does
not turn the owner into the breeder of every program variety. Historical,
disputed and limited-support role summaries retain their labels and caveats.
Program buttons keep the full relationship wording for accessibility and
evidence selection. Catalog-gap links now name their publishers.

A real browser walkthrough found that opening evidence unrelated to the current
focus lost that evidence on reload. The controller now restores both explicit
URL selections. Deliberately changing focus still closes unrelated evidence.
This fixes return/share behavior without changing the graph or evidence.

The visual guide retains all eleven consolidated section homes and now explains
six reporting outputs. Landscape links to the current Explorer while retaining
the configurable overview. HTML, SVG and CSV are available now; other berries,
saved Explorer views and downloadable PDF remain the next gated milestone.
Recovered source-text review is explained in a collapsed secondary section.
Its live review link is excluded from the public guide, as is the private
Explorer link.

## Five-minute review

1. **Scan the landscape.** Read the three takeaways, then the six company rows
   across Chile, China and Peru. An office, breeding test, planned entry and IP
   enforcement have different implications from production. The unused evidence
   column disappears when closed.
2. **Trace a variety.** Select Keepsake under Berry Blue. The existing breeder
   relationship is shown directly. Select evidence under “Control needs
   checking” while Keepsake remains focused, then reload. The focus and disputed
   Hortifrut/Berry Blue evidence both remain selected. Close the panel to recover
   the comparison width.
3. **Investigate a catalog gap.** Hortifrut's cited summary exposes seventeen
   named blueberries and MBG's source sixteen name/code pairs. Names such as
   Prelude link to identity review; they are visible without being silently
   approved as canonical varieties or growing-location facts. The overview's
   34 review-needed mentions belong to this selected source bundle, not the
   whole catalog audit.
4. **Compare dates.** In Refine relationships & dates, choose March 1–31, 2026
   and Recorded event / effective date, then Changes: seven dated connections
   appear and 66 lack an effective date. Switch to First captured: zero fall in
   March. The standing 82-connection landscape remains available. A recent empty
   window does not imply withdrawal.
5. **Inspect an output.** Open the printable briefing or the downloaded HTML,
   SVG and CSV below. The complete selection contains all 82 connections and
   47 sources, with 97 relationship/source CSV rows. Then open the guide's
   Reports & exports section: the six outputs distinguish a live workspace,
   refreshed saved selection and frozen download.

## Real-data scope and limits

The default reviewed-source selection remains **53 nodes, 82 relationships,
47 sources and 19 conservatively clustered origins**. There are ten company
location links, sixteen event-dated connections and **zero direct variety or
program location links**. Four identities remain provisional: Arana, Eterna,
FC11-164 and Twilight. Company presence does not establish a variety footprint.
The records include two disputed ownership links and legacy inferred or
substituted roles. Their presence is not independent claim confirmation.

Broader catalog work remains distinct: 348 source sections / 1,084 name
occurrences / 749 combined private candidate keys, with 750 in this isolated
preview including its pending Italian Berry source. All **64 canonical varieties
are unchanged**. The 32 current-page source copies from 35 attempted IDs still
await source-authenticity review; none was accepted or enabled for extraction
during this handoff. Capture success is not human approval or proof of complete
article recovery. Historical production review decisions are separate.

Full original-corpus coverage, current/historical portfolios, independent
human-qualified recall, richer rights/profiles/photos, human catalog authoring
and integrated release review remain open. No “most comprehensive on the web”
claim is justified. These requirements stay in the
[durable checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) and
[catalog mission](VARIETY-CATALOG-COMPREHENSIVENESS-MISSION.md).

## Review artifacts

All links below point to the actual native review or downloads, not mock data.

- [Light desktop](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-desktop.png), [dark desktop](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-dark.png), [light phone](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-phone.png), [dark phone](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-dark-phone.png).
- [Focus and restored evidence](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-focus-evidence.png).
- [Visual guide](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-guide-desktop.png), [phone guide](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-guide-phone.png).
- [Printable HTML](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-briefing.html), [briefing preview](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-briefing-preview.png), [vector SVG](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-briefing.svg), [relationship/source CSV](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-briefing.csv).
- [Actual scope/parity measurements](../../artifacts/blueberry-integrated-review-2026-10-09/blueberry-handoff-verification.json).

## Verification

Draft #374 is now all-green on `3a8261769768588009fa507d113d197c644b5e43`: all four
GitHub checks pass; Python reports **4,524 passed / 11 skipped / 2 warnings /
627.09s**. The watcher completed successfully and its terminal result was consumed.
The separate public-program catalog draft adds no Landscape rollout approval.

- Initial Landscape/guide/shell/retained-workspace suite: **120 passed**, one
  existing warning, 118.04s. Final changed Landscape/guide/static suite, including
  the production JavaScript reload regression: **66 passed**, one existing
  warning, 34.89s. The runs overlap and must not be summed.
- Record validation passes. All 2,771 original data JSON files and the canonical
  expansion guide remain unchanged. The private audit preserves prior source
  payload hashes and the real pending draft; zero new review events or extraction
  readiness.
- Final static build: **1,755 pages**, Pagefind built, unpublished draft
  ID/title exclusion passes. Generated controller hash matches final source.
  Public-guide tests exclude the private Explorer and source-authenticity links.
- Native desktop/light/dark and 390px viewport checks pass. The phone document
  stays at its 375px usable width; comparison tables scroll within containers.
  Temporary viewport overrides were reset.
- Native downloads retain the complete bundle version `ef36ff4511c8cb1b`, all
  82 relationship IDs, all 47 source references and original URLs; CSV has exactly
  97 unique relationship/source pairs. SVG parses as valid XML; line-wrapped
  source IDs are checked as rendered text rather than raw markup substrings.
- Local Windows loopback API: 711,429 bytes, three warm responses **423.92 /
  338.22 / 313.96ms**. Browser initialization after reload measured **43.30ms**
  and focus highlighting **25.80ms**; an earlier click measured 9.00ms.
  These are local measurements, not production latency guarantees. Existing
  synthetic scale/truncation and authentication tests cover larger graphs and
  private UI/API/export boundaries.

No migration, new dependency, source onboarding, model call, canonical write,
identity merge or review automation is introduced. Revert this additive draft
to roll back the presentation/reload/guide changes; retained overview, dossiers,
News and source-review workflows continue to exist.

## Required feedback gate

Review **readability, trust, analyst usefulness and export quality**. Approving
the revised blueberry direction permits the remaining Landscape milestone:
other berries, All berries, side-by-side comparison, saved-view integration and
downloadable PDF. It does **not** approve a merge, deployment, source-copy
acceptance, individual claims or variety identities. The full retained scope is
in [the brief](LANDSCAPE-EXPLORER-BRIEF.md); broader accessible catalog work may
continue independently while this feedback is pending.

Blueberry milestone is ready for review. Remaining berries and cross-berry
completion are pending your feedback; the full mission remains open.
