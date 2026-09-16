# Live-data exclusion confirmation

The integration imports zero live canary records.

- `git ls-files -- inbox demo-runtime/inbox generated` returned 0 tracked paths.
- The base-to-integration diff contains no path under `inbox/`, `demo-runtime/inbox/`, or `generated/`.
- The local static build created ignored `generated/` output only; it is not committed.
- No credentials or local environment files are included.
- Prototype screenshots and videos remain under `prototypes/**/verification/` as review evidence and are not runtime inputs.
- The temporary readable-reader browser fixture was created under `C:/Users/Johnny/AppData/Local/Temp/berry-wave2-reader-verification-20260915`, outside the repository and integrated application data. It is not committed.

Wave 1's source checkpoint records 25 staged discoveries, 5 discovery states, 20 operation items, 5 run records, 11 acquisition outcomes, and 10 private unapproved drafts in that source worktree's ignored inbox. None is present here and cherry-picking the tracked commits did not import them.

Publication mutations: 0. Approval mutations: 0. Live collection runs during integration: 0.

