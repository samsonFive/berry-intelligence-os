"""JSON-backed implementations of the record-repository contracts
(app/repositories/base.py). Preserves current runtime/storage behavior
exactly -- same file layout, same JSON formatting, same folders -- per
docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 3: existing JSON files
remain canonical during Phase 2; nothing here changes a file format,
relocates data, or normalizes a record."""
