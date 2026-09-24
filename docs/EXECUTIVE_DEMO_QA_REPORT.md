# Executive Demo QA Report

Date: 2026-09-24
Branch: `cursor/executive-demo-sprint-ba0a`
Target: `v2/intelligence-os`
Environment tested: local interactive application with repository-published evidence

## Release decision

**PASS for review.** The bounded executive path passed the full automated suite,
required repository checks, and three consecutive browser rehearsals. Production
deployment remains gated on PR approval and merge.

## Automated evidence

| Gate | Result |
|---|---|
| Full Python suite | PASS — 3,328 passed, 9 skipped, 2 warnings |
| PR change-scope check | PASS |
| PR repository-integrity check | PASS |
| PR static-public-safety check | PASS |
| PR Python-tests check | PASS |

The full suite was run with live-provider credentials removed so the result
measures deterministic repository behavior rather than external-provider
availability.

## Manual golden-path evidence

Three consecutive non-mutating rehearsals passed after the final product-code
revision:

| Run | Viewport | Result | Evidence checked |
|---|---:|---|---|
| 1 | 430 × 932 | PASS | Blueberry filter; asynchronous reader; source label; original-evidence action; close/back state; mobile navigation; Variety Database; Fall Creek monitoring expression and multi-source evidence |
| 2 | 430 × 932 | PASS | 48-item Blueberry result; stacked reader; Company signal treatment; preserved feed state; mobile navigation; Fall Creek Podcast, Company signal, and News provenance |
| 3 | 1280 × 800 | PASS | 48-item Blueberry result; side-panel reader; preserved feed state; Variety Database; Fall Creek Podcast, Report, Company signal, and News provenance |

No rehearsal opened an external publisher, triggered live collection, or
mutated Save/reaction/confirmation state.

## Acceptance coverage

- Mobile reader appears before the feed instead of after the card list.
- Opening a story updates the in-page reader without a document reload.
- Close and browser history preserve filter and scroll context.
- High-frequency filters remain visible; secondary filters are progressive.
- Original evidence is a distinct, prominent action with an honest body-text
  fallback.
- Source families normalize to News, Report, Podcast, Research, Company signal,
  Professional signal, and Registry without changing underlying evidence.
- Fall Creek's dossier exposes an inspectable monitoring expression, explains
  matching provenance, and shows diverse real public sources.
- Same-timestamp pending-draft rewrites invalidate the query sidecar by content,
  avoiding stale review results on Linux filesystems.

## Honest limitations

- Live discovery remains provider- and network-dependent; the demo uses stored
  published evidence and does not refresh live lanes on stage.
- The public trusted corpus contains one published podcast item; the UI does not
  imply broad podcast coverage.
- Monitoring profiles are transparent retrieval expressions, not claims of
  exhaustive company monitoring.
- Geography remains an evidence-backed table/grid surface. No map is shown
  because the corpus does not support that precision.
- This report does not assert production deployment. Post-merge health and
  public-route checks are still required.

## Demo artifact

`/opt/cursor/artifacts/mobile_async_reader.mp4` shows the asynchronous reader
opening with Company signal provenance and an original-evidence action, then
closing to the preserved feed. The capture is desktop-width despite its
historical filename.

See `docs/EXECUTIVE_DEMO_RUNBOOK.md` for the stage sequence and fallback rules.
