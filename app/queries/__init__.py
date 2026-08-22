"""Core query services (V2 Phase 2B.2, docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
Part 3.3).

Cross-object, domain-neutral reads that sit between record repositories
(persistence only) and Berries domain services (app/services/berries/,
which hold logic that means something only because Berries is the
activated Domain Pack). Nothing in this package decides what a
"competitor" or a "market" is -- that's a Domain Pack concept -- but it
does know how to walk from one record family to another (an Entity's
Facts, a Recommendation's linked Assessments, a record's explicit
analytical scope) without a caller re-implementing that traversal.
"""
