# Source intelligence transcript capture review — November 5, 2026

This is a local candidate for review, not a deployment or recurring-activation receipt. It follows the [native production browser acceptance](SOURCE-INTELLIGENCE-BROWSER-ACCEPTANCE-2026-11-04.md) and [manual collection canary](SOURCE-INTELLIGENCE-MANUAL-CANARY-2026-11-04.md). The mission remains open.

## Verified inherited state

Read-only verification after the overnight pause still finds production release `8f510b5383274f218e4e1eb714b4c28dc5413da7`, image `sha256:7cb55cc6995f7e9ca044f846882142c3efa432de88beba1559a8a72588e6c2eb`. The four manually created canary discoveries/drafts retain their recorded hashes, UID 0/GID 1000 and mode 0644. App UID 1000 cannot write those files directly; parent directories are writable. No repair has occurred.

Automatic approval review rejected both the proposed isolated writer probe and the exact owner-only repair for missing specific authorization. The subsequent read-only access report ran successfully. A human question for the four-file owner repair remains pending; it does not authorize the separate probe. The repair must retain bytes, group, mode, modification time and review state, and record before/after metadata. Other release approval cannot substitute for this permission.

## Reproduced browser defect and candidate

In a new isolated localhost fixture, a native triple-click selected a complete Spanish transcript paragraph. The original client submitted the visible clock and paragraph separators with the spoken words. The backend correctly retained the capture as unresolved because that quote does not exist in the archived transcript. The failed capture remains preserved in the fixture.

The candidate wraps spoken segment text separately from clocks and intersects the native selection with those text spans. It reconstructs the stored newline-separated transcript, computes Unicode code-point offsets, and sends the displayed transcript version. The server rejects a changed version before creating a capture. Repeated wording still requires a valid position; unresolved source wording is never silently attached to the first occurrence.

New snapshots retain transcript language. Captured-evidence views and Markdown exports display a time range only for an exact locator matching the retained transcript version. New cited digests retain that locator and version. Existing source snapshots, publications, review decisions and previously saved digests remain unchanged.

## Real native browser results

| Material | Saved destination | Exact stored location | Result |
|---|---|---|---|
| Redagrícola introduction | Blueberry workspace | 0–34 characters; 4.39–4.40 seconds | Whole paragraph saves without display clock; unverified |
| Explicit `empresa empezó con la variedad biloxi` | Biloxi transcript research workspace | 4,024–4,061 characters; 315.60–320.51 seconds | Exact cultivar wording; no trait or identity promotion |
| Lucentlands Fall Creek passage across two segments | Fall Creek transcript research workspace, associated with existing company ID | 369–446 characters; 40.46–45.82 seconds | Exact newline preserved; source-stated capture remains unverified |

The English capture uses `company-fall-creek-farm-and-nursery`, verified in the existing entity chooser. Its company profile's existing **Related research** disclosure shows the quote as a source statement, unverified. The first Spanish browser capture used only a named research destination. A subsequent separate native capture explicitly associated the same cultivar wording with existing `variety-biloxi-47764824`; the Biloxi profile then showed it as **Publication review pending**. Both captures are preserved. No trait, canonical identity, role, right, footprint or review decision was promoted.

A deterministic cited digest was generated through the visible controls with model use unchecked. A native Markdown download preserved the quote, original source and capture link. That download preceded the time-label enhancement; route regression tests verify the enhanced export. The local server was stopped and restarted with the same fixture; both English and Spanish evidence pages reopened with exact quotes, version-bound timing and original transcription provenance. The saved company workspace and digest persisted. Browser console errors were empty in the final evidence view.

Four exact captures, the earlier failed capture, all 3,438 copied canonical files and both original transcript copies are preserved. The fixture has its own inbox, local test identity and session, with source polling/extraction disabled and provider keys removed from its process. No production credentials were used on localhost. The production browser session used the existing app credentials only, as authorized.

Private proof: `inbox/search-quality-evaluation/source-browser-capture-acceptance-20261105.json`, the retained before/after receipt, native screenshots and exported Markdown. These files and private captures are excluded from Git and public static output.

## Real blog canary and feed metadata corrections

Two manual local cycles used the already registered UF breeding-program blog Source, capped at two persisted discoveries and two processed items, with provider keys removed and zero transcription/model/extraction allowance. The current public robots policy allowed this access. Discovery observed 104 sitemap entries but persisted only two. Both article-body acquisitions were unusable (59-character shell/byline); one existing orchestration path created a clearly thin, unreviewed draft and the other retained an operator case. The repeat found the same two entries and created no further drafts. All 3,446 pre-existing canonical/evidence/transcript files in the fixture remained byte-identical. These results are not a production health update or successful full-text acquisition.

The real UF draft exposed a format gap: `/post/` URLs from an explicitly labeled Blog publisher were treated as Articles. Format selection now recognizes a standalone Blog/Blogs declaration in the publisher label as well as existing explicit types and blog paths. A headline containing “blog” or an arbitrary `/post/` route alone is insufficient. The actual browser Blogs filter now shows the UF draft and a historical InvestChile publisher-blog record that was previously classified as an article. The historical record was retained all along; a zero pre-fix Blog classification count did not mean no blog material existed.

Native excerpt capture also exposed a metadata-path defect: `news_workspace` already excludes saved passages, but the streaming private publication preview discarded their `workspace_capture` marker. Previews now carry only a boolean marker, retaining no saved quote/locator body. The original publication remains visible; captures stay in their workspace/profile paths. A native post-fix video filter shows exactly the one Redagrícola publication, with all five captured items still retained. Both focused regressions failed before the correction.

The UF Reader recovered only a byline and labels its publisher text as potentially partial. Native publisher inspection found an explicitly offered `FBGA2026_EconGrafting_Athearn.pdf` presentation (728,160 bytes), downloaded through the public page. Its substantive content and integration into linked Reader navigation remain a separate open case; the byline is not represented as the presentation. Private receipts: `source-blog-local-canary-{1,2}.json`, `source-blog-local-canary-proof.json`, and the real blog/feed-exclusion screenshots under the same private evaluation directory.

## Validation and release gate

Focused media/workspace/competitive-capture, feed/private-preview and route regressions: **89 passed**. This includes changed-version rejection without item creation, repeated wording after a Unicode character, language/provenance persistence, exact time/version citations, HTML evidence presentation, Markdown export, declared blog formatting, body-free saved-passage exclusion and adjacent workspace behavior. JavaScript syntax and diff checks pass. Initial sandbox runs could not create pytest temporary folders or asyncio socketpairs; subsequent runs used workspace-local temporary directories and approved local socket access. These environment failures are retained and are not test passes.

All four required CI checks must pass on the final remote head, followed by canonical reconciliation and a fresh bounded preservation rehearsal before any deployment review. No deployment, recurring collection/transcription or paid provider routing is approved by this candidate.

## Separate recurring collection review proposal

The existing timer must retain its current News selection until separately approved. Registry `scheduled=true` is not evidence that another lane is dispatched. The proposed first media lane uses only the existing `spoken_media` dispatcher and exact Source allowlist `source-business-of-blueberries-podcast`:

```text
scripts/run_collection.py --pipeline-scope spoken-media --source-allowlist source-business-of-blueberries-podcast --max-discoveries 2 --max-items 2 --skip-transcription --max-transcriptions 0 --no-model-enrichment --json-summary
```

Its process must run as app UID/GID 1000, with extraction explicitly disabled and the credit-free guard retained, under existing collection/shared-host locks and resource floors. A daily dispatcher evaluates the Source's existing weekly due state; it must not force daily collection or include historical backfill. The November 4 manual success puts the next normal weekly due time around November 11 at 3:27 p.m. Pacific. Source cadence and the existing News worker remain unchanged.

Before activation, review the exact scheduler wiring, selector, Source eligibility, fresh recovery point, four-file permission disposition, no-op due-state check, logging and disable/rollback procedure. Do not remove the current selector to activate every enabled registry lane. Local STT remains a separate decision requiring a specific recording, transcript/caption availability check, resource budget and audio-quality review. No credits may be purchased.

## Remaining gaps

Audio word accuracy has not been checked against either recording. Fresh Blueberries TV material remains local, exact podcast page binding is held, linked accessible-page browsing is incomplete, account-specific Exa allowance is unverified, and the standalone Reports capture flow needs further browser acceptance. The entity-profile path is verified only for the two explicit associations above. The existing tag-classification failure is separate. A fresh sealed mixed-source analyst-outcome evaluation and wider source/variety coverage remain open; frozen failed Google comparisons are unchanged.
