# Luna verdict verification

- Luna branch: `test/publication-review-command-service-adversarial-v1`
- Luna head: `7873a685042f1bd4d16d93137981737854802be4`
- Backend head tested: `cf6d19319363dadd20d7182d5b8aaf3f97726d7b`
- Exact ancestry check: backend is an ancestor of Luna.
- Luna-only commit count: one.
- Required verification artifact: present.
- Verdict: **PASS**.

Luna independently reran six adversarial tests, 143 backend tests with nine intentional skips, 291 existing publication/trust/acquisition/transcript tests, record validation, the 1,665-page static build/Pagefind, and the 244-check quick gate. No blocker was reported.
