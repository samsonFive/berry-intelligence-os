# Conflict resolutions

## Cherry-pick conflicts

None. Backend, Luna-only, and UI path sets did not overlap.

## Integration-only fix

The first combined focused run produced two failures in `tests/test_publication_review_readonly_ui.py`. Both asserted POSIX path fragments against `str(WindowsPath(...))`. Product behavior passed.

Resolution: use `FIXTURE_PATH.as_posix()` in the two assertions. Commit: `9507df5c64276481257e36d8a906f5bbe7d0a184`.

The exact combined focused gate then passed: 208 passed, 9 intentionally skipped. No production behavior was changed.
