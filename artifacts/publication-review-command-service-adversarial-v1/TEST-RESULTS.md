# Test Results

| Group | Command | Result | Count | Duration |
|---|---|---:|---:|---:|
| Validator adversarial | `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp-command-adversarial tests/test_publication_review_command_adversarial_v1.py` | PASS | 6 passed | 4.25s |
| Backend publication command | focused domain/repository/command/crash/migration/static suites | PASS | 143 passed, 9 intentional skips | 12.86s |
| Existing publication/trust/acquisition/transcript suite | documented existing suite | PASS | 291 passed | 95.70s |
| Record validation | `python scripts/validate_records.py` | PASS | 0 test rows | 3.43s |
| Static build/Pagefind | `python scripts/build_static.py` | PASS | 1,665 pages | included in build run |
| Wave 2 quick gate | `python scripts/wave2_contract_gate.py --mode quick` | PASS | 244 underlying checks | 212.2s |

Total observed execution count across backend report and validator runs: no failures. The backend's prior report separately records its full suite totals; this document reports independently rerun groups and does not treat pre-existing intentional skips as validator failures.
