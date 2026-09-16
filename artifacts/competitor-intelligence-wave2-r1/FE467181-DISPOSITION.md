# Disposition of `fe46718116de764d1f02a49fdc8dfc1e42414d11`

Conclusion: **already present and retained**.

Evidence collected before editing:

1. `git show -s` reports `85a157233674ee5cd3d2e358ea02924d3ac04790` has parent `fe46718116de764d1f02a49fdc8dfc1e42414d11`.
2. `git merge-base --is-ancestor fe467181… 85a157…` succeeds.
3. `fe467181…` changes exactly two files: `scripts/build_static.py` and `tests/test_build_static.py`.
4. A direct diff of those two files between `fe467181…` and `85a157…` is empty.
5. The prior Wave 2 focused suite, including the static-link regression test, passes on R1.
6. The R1 static build passes and filtered competitor query links remain correctly rewritten.

The previous report's “verification-fix commit” field identified the fix commit while the “local/remote HEAD” field identified the later reconciliation commit. Both statements were individually correct, but the relationship was not stated clearly. The fix is the parent of the reported head, not an alternative head.

Action taken: no cherry-pick, revert, or amendment. The commit remains in ancestry exactly once.

