# Publication Review Workflow V1 — Operator Prototype

Disconnected, fixture-driven prototype for reviewing publication drafts and recording an explicit operator decision.

## Base

- Production reference branch: `integration/competitor-intelligence-wave3`
- Exact base commit: `c95c05e51b8247a0b22f417a877088c8d7f20e6b`
- Prototype branch: `prototype/publication-review-workflow-v1`
- Visual system: Product Visual System (navy / bronze / warm-canvas) via `tokens.css`

## Non-goals (enforced)

- No production routes
- No backend mutation calls
- No canonical / live data
- No trusted publication creation
- No Evidence
- No full application redesign
- No PR, merge, or deployment from this prototype track

## Run locally

```bash
cd prototypes/publication-review-workflow-v1
python3 -m http.server 8765
# open http://127.0.0.1:8765/
```

## Fixture states (10)

| State | Draft id |
| --- | --- |
| Readable body | `pub-readable-ok` |
| Transcript | `pub-transcript` |
| Metadata-only | `pub-metadata-only` |
| Navigation-only shell | `pub-nav-shell` |
| Probable duplicate | `pub-probable-dup` |
| Uncertain date | `pub-uncertain-date` |
| Missing entity match | `pub-missing-entity` |
| Upgraded acquisition | `pub-upgraded` |
| Already handled by another reviewer | `pub-concurrent` |
| Validation failure | `pub-validation-fail` |

## Decisions (prototype memory only)

- **Approve publication** — explicit confirmation; not Evidence approval
- **Reject** — reason required
- **Defer** — optional notes
- **Request correction** — reason required

Guardrails: no bulk approval; warnings vs contractual blockers; stale/concurrent idempotent no-op; duplicate-click idempotency; success receipt (actor, time, source draft, resulting publication id label); no false undo.

## Deliverables

| Path | Purpose |
| --- | --- |
| `index.html` + `app.js` + `styles.css` + `tokens.css` | Prototype UI |
| `fixtures/` | Synthetic draft fixtures |
| `docs/` | Catalog, interaction notes, a11y checklist, migration map |
| `verification/capture_screens.py` | Playwright screenshot/video capture |
| `artifacts/publication-review-workflow-v1/` | Screenshots + walkthrough video |

## Safety tally

```
PRODUCTION FILES MODIFIED: 0
PRODUCTION MUTATIONS CONNECTED: NO
BULK APPROVAL AVAILABLE: NO
TRUSTED PUBLICATIONS CREATED: 0
TRUSTED EVIDENCE CREATED: 0
CANONICAL/LIVE DATA MUTATED: 0
PR/MERGE/DEPLOYMENT: NOT PERFORMED
```
