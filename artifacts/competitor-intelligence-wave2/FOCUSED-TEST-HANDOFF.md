# Focused-test handoff

Date: 2026-09-15

- Combined focused suites: **282 passed**, 17 warnings, 59.80 seconds. See `focused-tests.txt`.
- Targeted static-link suite after the verification fix: **6 passed**, 1 warning.
- Record validation: **passed**. See `record-validation.txt`.
- Static build: **passed**, 1,665 pages; Pagefind completed; unpublished-draft leak check passed. See `static-build.txt`.
- Browser checks: seven pages returned HTTP 200, all expected markers were present, and no browser console errors were observed. See `browser-checks.json` and `BROWSER-SCREENSHOT-INDEX.md`.
- Full suite: **NOT RUN**. Linux CI owns that gate.

The only combined-suite failure was fixed in `fe46718116de764d1f02a49fdc8dfc1e42414d11`: static internal links now preserve query strings and fragments.
