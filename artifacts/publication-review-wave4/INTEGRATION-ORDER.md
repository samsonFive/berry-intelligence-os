# Integration order

The worktree was created from exact Wave 3 base `c95c05e51b8247a0b22f417a877088c8d7f20e6b` on branch `integration/publication-review-wave4`.

1. Contract range `5cb3b0b90ebb17568cb6a1688a2431514d31fc82..4c126a6e15d448c4be2f0dae73ddce879fbc0346` in chronological order.
2. Candidate pack `8952566625a543f1850b33fcb033ef0aac5a0839`.
3. Safety audit `decb97049a79b3d9e7c4f007f4f5977284d27eec`.
4. Wave 3 → backend unique commit `cf6d19319363dadd20d7182d5b8aaf3f97726d7b`.
5. Backend → Luna unique commit `7873a685042f1bd4d16d93137981737854802be4`.
6. Wave 3 → UI unique commits `3a8da84cce935ed5d1f234bc07bdb95441fb67a2` and `d19ee0a35033a574dec6c03ecf6aa5008ed7102d`.
7. Integration-only portable-path test fix.

All cherry-picks were sequential. There were no textual conflicts and no source commit was replayed twice.
