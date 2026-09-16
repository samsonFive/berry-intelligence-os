# Exact commit map

Base: `c95c05e51b8247a0b22f417a877088c8d7f20e6b`

| Order | Source | Exact source commit | Integration commit |
|---:|---|---|---|
| 1 | Contract foundation | `5cb3b0b90ebb17568cb6a1688a2431514d31fc82` | `54913671bf3e21503791e75935820ef11e10b467` |
| 2 | Final contract durability addendum | `4c126a6e15d448c4be2f0dae73ddce879fbc0346` | `b33f4115a463eee1b2b3af49cacacc6aad40286e` |
| 3 | Candidate/rehearsal pack | `8952566625a543f1850b33fcb033ef0aac5a0839` | `aac9568b44e134b109cfda9d1dbfb7d1095514f6` |
| 4 | Safety audit | `decb97049a79b3d9e7c4f007f4f5977284d27eec` | `2e888a99020e4e32f996fbf43202468268dc17a7` |
| 5 | Backend command service | `cf6d19319363dadd20d7182d5b8aaf3f97726d7b` | `cbbf35a41307780ea0022c26a0a980b49592e6d8` |
| 6 | Luna validation unique commit | `7873a685042f1bd4d16d93137981737854802be4` | `91d68960cbb03572acccd32570ddfdebaa4ac16a` |
| 7 | Read-only UI implementation | `3a8da84cce935ed5d1f234bc07bdb95441fb67a2` | `ead7a41002097238f8b33893e1f151f691ae2ef2` |
| 8 | Read-only UI verification artifacts | `d19ee0a35033a574dec6c03ecf6aa5008ed7102d` | `c877b7511bec951091efb6b69ae1391d6ccc3662` |
| 9 | Integration-only Windows test portability fix | n/a | `9507df5c64276481257e36d8a906f5bbe7d0a184` |

Luna is based on the exact backend commit, so only `7873a685042f1bd4d16d93137981737854802be4` was replayed from its branch. No backend commit was replayed twice.

No commit from `prototype/publication-review-workflow-v1`, PR #255, Story Threads, Learner work, or a branch based on `origin/v2/intelligence-os` was imported.
