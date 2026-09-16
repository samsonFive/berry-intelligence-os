# Claude profile-completeness fix intake

Expected branch: `fix/profile-completeness-semantics-v1`

Do not invent or infer its commit. When Claude publishes the checkpoint:

1. Verify the remote branch and exact 40-character head before integration.
2. Confirm it is based on profile head `516f1ee74a369fb59e0563341a0b9d75da6edf9e` and inspect only its delta.
3. Reconcile the small semantic delta into this branch after the Wave 2 reconciliation commit.
4. Preserve the five independent monitoring dimensions and all canonical identity/genetics review states.
5. Do not let completeness mean "tracked," do not turn non-applicable fields into missing data, and do not flatten provisional identity into represented/unrepresented.
6. Rerun `tests/test_competitor_profile_v1.py`, registry/identity tests, landscape tests, record validation, and any new focused tests supplied by Claude.
7. Record the exact source-to-integrated commit map and any changed audit output.

No UI rewrite, source run, collection, approval, publication, or live-data import belongs in this follow-up.
