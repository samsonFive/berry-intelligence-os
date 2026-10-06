# Mission 9 — Visual Learn and explicit research

Draft implementation on `feature/visual-learn-research`, stacked on Mission 8. No merge, deployment or canonical data change. This is the first complete research-to-lesson slice of the accepted Learn expansion; it does not claim visual coverage for every topic.

## The user experience

Learn stays in the primary navigation. Its 27 existing concepts across five pillars remain searchable and readable in the Glasshouse shell. Lesson pages lead with the answer, then separate the idea, implications, conditions, crop notes and teaching resources. Source provenance and technical review details are secondary disclosures. Existing related intelligence retains its separate review status.

The cane-year lesson includes an interactive two-year diagram, a knowledge check, an attributed raspberry-fruit photograph and a university pruning-video link. Switching fruiting habit changes the explanation and illustrated fruit position. The diagram is explicitly schematic, applies to raspberry/blackberry and does not establish a farm's performance or a regional pruning calendar. The photo's actual caption and CC BY 2.5 attribution replace the inaccurate legacy presentation without changing the canonical record. Other legacy photographs without a verified reuse basis are source links rather than automatically embedded images. The video is linked from a University of Maryland Extension guide; its player was not verified or copied.

Selecting text in reading content reveals **Research & add to Learn**. The Reader also has a keyboard/touch-accessible book action when text selection is inconvenient. Both open an editable topic/excerpt form before any paid request. Matching concepts or saved lessons can be read immediately without research. Crop, region, pillar and knowledge class are explicit selections. Whole articles, private forms, notes and saved lesson edits are not sent automatically.

Starting research reserves a durable private job before contacting Perplexity. The user can continue elsewhere, return to check its status and retrieve a saved educational draft. There is no fabricated progress percentage. Rendering converts native citation codes into accessible source links, preserves substantive paragraphs and lists, and builds actual comparison tables. Edits use revision checks, retain the original provider text, sources and earlier revisions, and allow intentionally empty text. Updated research creates a separate draft rather than replacing an edited lesson. Saving or researching does not approve guidance or competitive statements.

## Provider, persistence and boundaries

The current official [background-mode contract](https://docs.perplexity.ai/docs/agent-api/background-mode) and [presets documentation](https://docs.perplexity.ai/docs/agent-api/presets) were checked October 2, 2026. The provider call uses `POST https://api.perplexity.ai/v1/agent`, `preset=medium`, `background=true`, at most 15 steps and 6,000 output tokens. Retrieval/cancellation use the existing provider run reference. Prompt version `learn-deep-v1` and the returned model are retained because preset internals can change. This is separate from closed-book inference and Atomic Evidence extraction qualification.

Private `inbox/learn_research.json` stores reservations, provider references, requests, citations, lessons and history. No Evidence, Fact, Signal, Assessment, entity identity or canonical learning file is written. GET/browse/search never calls the provider. Research actions require the analyst workspace and same-origin protections. Public/live read-only browsing cannot see private drafts; the static build continues to use existing published educational templates and never includes this store.

Same topic/scope and repeat submissions reuse the reservation. Concurrent updated requests for the same parent/scope reuse the active run. At most two unfinished runs can be reserved. Submit timeouts/ambiguous provider failures are visibly uncertain and never trigger an automatic second paid submission. An explicit confirmed provider reference can recover the existing run by retrieval only. Cancellation remains pending until the provider confirms it; revision checks protect against late status updates undoing cancellation or analyst edits. Damaged stores are left unchanged and the public concept library remains available.

## Verification

- **106 focused tests passed** across learning persistence/provider routes, existing concept behavior and feed acceptance/regressions; one existing reportlab deprecation warning. Tests use deterministic transports, never live provider calls.
- JavaScript syntax and canonical record validation passed. Required full/static checks will run on the pushed draft head; local focused results are not a substitute for exact-head CI.
- One authorized bounded public-topic run completed: raspberry primocane/floricane biology and regional pruning. It captured **42 unique provider source URLs** and their native citation aliases; the returned model was `openai/gpt-6-luna`. No private notes or full article were transmitted. It is an educational draft, not reviewed scientific or competitive evidence. Live response/lesson storage stays ignored under the isolated preview inbox.
- Browser: fruiting-habit controls changed the illustration and text; the attributed photo loaded. Selected “Shelf life” in a news summary opened an editable request and a matching existing lesson without calling research. Returning reopened the same source in Brief mode. A scrolled-reader return exposed image-height timing, which is corrected and rechecked separately below.
- Native lesson editing saved a shorter title; reloading retained it, all 42 citations and original research/version history. The comparison renders as a real table and citation codes are readable links.
- At 390px, page width remained contained and the 560px comparison table scrolled inside a 311px container. The temporary viewport was reset. Screenshots: `learn-diagram-live.png`, `learn-research-live.png` under `artifacts/design-sprint/`.

## Remaining accepted work / release concerns

**Reader-position follow-up:** Native browser round trip at 466px returned to the same source, Brief mode and exactly 466px after article-image loading. Restoration yields if the user starts scrolling/typing. The existing Reader owns opening/focus and durable reading state; the Learn hint is session-local.

Verified pictures, diagrams, videos and interactive lessons across the other concepts/pillars remain to expand; absent or unlicensed media must not be invented or copied. Static Learn styling and legacy media rights presentation remain to reconcile with the final deployment path. Job retrieval is an explicit check, not unattended result harvesting. Workspace-wide private stores and process-local write locks require account/multi-worker review before any broader deployment. A provider-accepted submission interrupted before its reference is stored requires explicit recovery rather than resubmission. Remaining canonical integration, Monitor/Operations, data-readiness and final workflow explainer stay on the ongoing checklist.

**Exact-head CI:** draft #282 at `9dd69112b7725e2111bed33035f5b1cd4be02020` passed Change scope, Repository integrity, Static public safety and Python tests, run `37011755674`: 3,509 passed / 11 skipped / two warnings. This closes the slice’s CI gate; the combined release is still pending.
