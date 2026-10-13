# Captured article names in variety review

The private catalog workspace now includes explicitly named varieties from known
news whose original text is already available. Analysts no longer have to run a
second discovery action for those names to appear in the general review queue.
The Reader shows catalog matches and proposed names in a collapsed section.
“Keep discoveries for review” retains new candidates using the existing additive
intake; it never confirms identity or creates a canonical variety.

## Real source proof

The original [Hortifrut genetic-development page](https://www.hortifrut.com/innovation/genetic-development/)
was captured through the native Reader action in the isolated local preview.
Its 18 available paragraphs contain 24 explicit names: 17 blueberries, five
raspberries and two blackberries. Native review checked the forward license list,
the quoted Berry Blue list, the blackberry pair and the PBB raspberry list.
One name matches the existing catalog; 23 require identity review. Pacific Gema
opens the general Raspberry candidate queue directly from the Reader.

This is one agent-checked real source, not a human-qualified independent recall
benchmark or proof of a complete/current company portfolio. The publisher's
licensing, breeding, trial, production and performance statements remain source
claims. No relationship, trait, rights status or growing region was approved.

The repeatable private audit now finds 102 distinct source names, 32 catalog
matches and 70 candidate discoveries before private identity decisions. The
summary-only audit remains 99 / 31 / 68. The two additional candidate identities
already existed in the primary portfolio review, so this preview's combined queue
remains 738 keys. The 64 mixed-status canonical varieties remain unchanged.

```powershell
python scripts/audit_variety_catalog_coverage.py --inbox-dir inbox/european-portfolio-followup/apg-preview-runtime/inbox --output inbox/european-portfolio-followup/captured-article-catalog-audit.json
```

The output includes source/name metadata, not original article bodies. Private
capture reports must stay under the selected inbox or repository inbox; the CLI
rejects public `generated/`, `data/` and `artifacts/` destinations even if one
is accidentally selected as the inbox. The default audit remains published
summaries/typed records only and does not read private captures.

## What is connected and preserved

- The existing Digest inventory identifies known published and retained news.
  Reader captures must match both the exact item ID and original requested URL,
  be successful, have string passages and fit the two-megabyte read bound.
  Orphans, mismatches and malformed/failed captures are excluded.
- Existing source text, including operator edits, wins over refreshed captures.
  Summaries copied into body fields and access-screen text are not original
  article inputs. Documents over 200,000 characters are excluded explicitly.
- Existing paragraph/crop-aware discovery handles names. No new extractor,
  scraper, provider call or candidate store was introduced.
- GETs derive proposed rows without fetching or writing. Source review and
  variety identity review stay separate. Each contributing article retains its
  own source URL and publication-review status; a reviewed co-mention cannot
  confer that status on an unreviewed primary source.
- Human-reviewed/rejected candidates and notes remain unchanged. Additional
  article references are a read-only overlay. The explicit Keep action compares
  against persisted candidates, so derived visibility does not prevent saving
  new names; replay is additive and idempotent.
- Public/static discovery never reads the private article inputs or captures.
  No canonical Variety schema, CPVO, commercial observation, footprint, Trade
  or Weather record was changed.

## Verification

- 132 affected discovery, Digest, corpus, universe, portfolio and company tests
  passed in 184.37s. After adding audit coverage, the final 13 focused tests passed
  in 5.21s. These runs overlap and must not be added as unique test counts.
- The first new CLI-boundary test incorrectly treated local pytest scratch space
  under the repository inbox as public. It was corrected to target the actual
  public-build folder; the rejection assertion was preserved.
- Native desktop review checked the capture, 24-name section, catalog/profile
  links, general candidate queue and separate per-article review labels.
- Actual 390px phone review checked the Reader and alphabetical queue jump.
  Client width and scroll width were both 375px. Search/crop scope survived the
  P jump. The viewport was reset and the temporary phone tab closed.
- Record validation passed; all 2,771 original data JSON files and the canonical
  expansion guide were preserved. No human identity/publication form was
  submitted. Existing Reader-position autosave still operates independently.
- Parent [draft #366](https://github.com/samsonFive/berry-intelligence-os/pull/366)
  is green on `bb95be5b99eec83ce9c57619bbfec417af921ecc`: all four checks;
  4,405 tests passed / 11 skipped / two warnings in 424.01s. Run 37880415786,
  Python job 113658688522; watcher 47684 completed with exit 0 and was consumed.
  This child still requires its own pushed-head full checks.

## Remaining mission scope

Only one of the preview's 1,269 known published sources has an available private
Reader capture; the canonical published records still contain zero readable
original article bodies. The new connection does not acquire missing bodies,
scan arbitrary orphan files, resolve image-only names, or qualify an extractor.
Active publication-draft bodies outside the retained-news inventory still need
their own acquisition/reconciliation proof through the existing workflows.
Complete current/historical portfolios, official current rights, profile depth,
independent human-reviewed recall and human catalog authoring remain open under
CAT-01/CAT-02/TD-116. This is progress toward the full goal, not its completion.
No merge/deployment or other-berry Landscape rollout is authorized by this review.

## Completed pushed-head CI

Draft #367 is green on `e494eb9ba3dda1c9cd0364270bc4016301228c95`.
All four required checks passed. Python: **4,418 passed / 11 skipped / two
warnings / 486.63s**; run 37882948181, job 113666573480. Watcher 68964
completed with exit 0 and was consumed. The recorded pending-draft gap above
is now addressed by [pending-article integration](PENDING-ARTICLE-VARIETY-COVERAGE-REVIEW.md),
which requires its own new-head checks. The broad catalog and release gates
remain open.
