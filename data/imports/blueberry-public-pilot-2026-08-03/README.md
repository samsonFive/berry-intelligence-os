# Blueberry public-source research package — `blueberry-public-pilot-2026-08-03`

A staged, additive set of structured records for the blueberry competitive-intelligence dataset,
built entirely from public sources. Nothing here has entered the trusted dataset. Everything is
intended to be reviewed by a human first.

## Read these in order

| # | File | What it is |
|---|---|---|
| 0 | `EXECUTIVE-SUMMARY.md` | **Start here.** What the dataset contains, the seven findings that matter, and what it deliberately does not claim |
| 1 | `WAVE-1-REVIEW.md` | The first delivery checkpoint and the schema decisions that were confirmed |
| 2 | `schema-assessment.md` | What the running schemas actually permit, findings A-1…A-11 and limitations L-1…L-10 |
| 3 | `research-method.md` | Evidence tiering, confidence rules, identity resolution, trait provenance, date handling |
| 4 | `manifest.json` | Machine-readable record counts, breakdowns and a content hash |
| 5 | `source-coverage.csv` | Every source, its tier, and what it supports |
| 6 | `qa-report.md` | Validation results and self-assessment |
| 7 | `conflicting-claims.md` | Where sources disagree and how each disagreement is represented |
| 8 | `coverage-gaps.md` | What is missing, and why it is missing rather than filled by inference |
| 9 | `next-research-waves.md` | What a subsequent pass should do |
| 10 | `proposed-schema-enhancements.md` | Backward-compatible schema proposals P-1…P-11 |
| 11 | `import-order.md` | The order to import in, and the exact commands |
| 12 | `CHANGELOG.md` | What changed, when |
| 13 | `signals/` | Six proposed signals. All `status: "proposed"`, none confirmed. **Not importable** - no signal schema exists in the repository (limitation L-7) |
| 14 | `priority-actions.md` | 16 recommended actions in three tiers, each with a success test |
| 15 | `rejected-or-unusable-sources/` | Sources reached for but not used, and why. Prevents a later wave re-walking the same dead ends |

## Layout

```
entities/
  berries/  brands/  breeding-programs/  companies/
  geographies/  patents/  retailers/  traits/  varieties/
evidence/
facts/
relationships/
strategic-questions/
signals/                      non-importable
rejected-or-unusable-sources/ non-importable
scripts/
  validate_package.py         schema + convention + referential integrity checks
  import_package.py           --dry-run / --apply / --approve / --rollback
  build_reports.py            regenerates manifest.json and source-coverage.csv
```

## Requirements

Use Python 3.12. The repository pins `pydantic==2.11.7`, which does not build on Python 3.14.

## Quick start

```bash
# 1. Validate the package on its own
python data/imports/blueberry-public-pilot-2026-08-03/scripts/validate_package.py --verbose

# 2. See exactly what would be written, without writing it
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --dry-run

# 3. Write the records (evidence lands as in_review and stays out of the feed)
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --apply

# 4. Confirm the repository is still healthy
python scripts/validate_records.py
python -m pytest

# 5. Only after human review — publish the evidence to the feed
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --approve

# Undo an apply
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --rollback
```

## Four things to know before reviewing

**Evidence arrives unpublished.** Every evidence record has `status: "in_review"`. The feed only
renders `published`, so importing this package changes nothing a user sees until someone runs
`--approve`. This is deliberate: the platform's stated principle is that the system proposes and a
human approves.

**`fact` and `claim` are not the same thing.** The schema's `classification` enum has exactly two
values. Registry and measured values are `fact`. Owner and marketer assertions are `claim`, and
the statement text names who is claiming. An attributed claim is never promoted to a fact.

**No company is privileged.** No record marks any organisation as the reader's employer. Roles are
specific — breeder, licensor, nursery, marketer, grower, retailer, rights holder — and no
organisation is labelled simply "competitor" without also carrying its functional roles.

**Analyst inference is not in the record set.** Anything that is an interpretation rather than a
sourced statement lives in `signals/`, which the importer does not read. No signal is labelled
confirmed.
