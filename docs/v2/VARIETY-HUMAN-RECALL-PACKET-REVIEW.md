# A human worksheet for checking variety-name detection

The private worksheet makes the outstanding expected-name review practical:
choose a source, read its retained copy, enter literal names/crops/codes, and
download the answers. It prepares no detector answers. The current local packet
contains all 32 pending Article copies with every expected-name list unfinished.

The saved-copy link uses the existing source-review route with `?name_review=1`.
That read-only view shows captured text and headings, hides the stored summary,
and has no source-acceptance or identity controls. Normal authenticity review
retains its original forms and required confirmation. The operator packet adds
no permanent top-level site section or alternate trust workflow.

## Reviewer workflow

1. Open a source in the worksheet, then use **Read saved copy**. Review the
   captured words; a current publisher page may have changed.
2. Enter one literal name per line as `berry | name | optional code`. Preserve
   names and codes separately. Include named parents/comparisons; exclude
   generic crop classes and brands. Do not guess a crop or merge aliases.
3. Explicitly mark the source list complete. A completed empty list means the
   reviewer read the copy and found no names. An unfinished list stays null.
4. Download the answers. Partial work is allowed and retained in browser storage,
   but unfinished lists cannot be scored. This worksheet sends no answers to a
   server. Source acceptance, catalog authoring and benchmark qualification
   remain separate human decisions.

The worksheet and browser exports contain source metadata and entered answers,
not article bodies. The explicit assembly command later reads the existing
private Article copies, verifies their identity/text/title/language and builds
input for the existing offline scorer. No app record is hydrated or replaced.
Stored summaries and unrelated enrichment are excluded from scoring input.
This packet measures literal name/crop/code detection; it does not measure
live catalog identity resolution or global variety completeness.

## Operator commands

From the repository root, prepare a fresh private packet against an explicitly
selected runtime. The example below refers to local research copies; cloud agents
do not receive that ignored runtime automatically.

```powershell
python scripts/prepare_variety_recall_review.py --runtime-inbox inbox/european-portfolio-followup/apg-preview-runtime/inbox --output-dir inbox/review-packets/new-source-scope --review-base-url http://127.0.0.1:18573
```

Serve only that packet directory on localhost to review the generated worksheet.
Existing human files are never replaced. Answers are saved in the browser under
the packet fingerprint; download them before changing browsers or clearing storage.
After a human supplies the real completed answers:

```powershell
python scripts/prepare_variety_recall_review.py --runtime-inbox inbox/european-portfolio-followup/apg-preview-runtime/inbox --output-dir inbox/review-packets/completed-source-scope --review-file inbox/reviewer-answers.json
python scripts/audit_variety_name_recall.py --fixture inbox/review-packets/completed-source-scope/human-expected-recall-input.json --output inbox/review-packets/completed-source-scope/name-comparison.json
```

The first command refuses missing/shortened source lists, changed captures,
unfinished expectations, unsupported crop IDs, duplicate names and approval
fields. Outputs must stay under ignored inbox storage, outside the active
source runtime. Exclusive file creation preserves prior human answers and
prevents file-symlink or concurrent overwrite. A comparison result does not
approve a benchmark, an extractor, a source or a catalog record.

## Actual review and verification

Native browser review verifies the actual 32-source worksheet starts at zero
completed lists; its saved-copy link opens the captured text without the stored
summary or decision buttons. Draft retention after reload and a real partial JSON
download were tested with two explicitly fictional sources. That file retains
one fictional answer and one null unfinished list; it is not a human benchmark
and cannot assemble against the real 32-source set. No actual answers were entered.

An initial syntax typo in the new test fixture was fixed before execution.
The affected packet/scorer/source-authenticity suite then passed 65 tests with
one warning in 11.19 seconds; final test,
public-output and preservation evidence is recorded in the verification artifact.
The 1,755-page public/Pagefind build and record validation pass. Actual phone
visual verification remains open; responsive CSS is not evidence of a phone test.

Parent #389 passes all four current-head required checks on 977163c, including
4,597 tests /11 skipped /two warnings in 726.03 seconds. This new draft requires
fresh checks on its pushed head. Canonical records and private review state stay
unchanged. The source audit remains 378 sections /1,549 occurrences /88 matched /
1,461 needing review /1,124 derived candidate keys; canonical varieties remain 64.

The packet is prepared, not human-completed or independently qualified. The
32-source set is not an all-four-berry gold benchmark or a complete corpus.
CAT-01, CAT-02, TD-116, LAND-02 and REL-01 remain open: original/current/historical
coverage, independent human recall, actual identity/catalog authoring, source-backed
profiles/photos/regions, current rights, phone review and integrated release.
The visual explainer remains at `/guide`. No merge/deploy or other-berry Landscape
rollout before revised blueberry feedback and separate release approval.
