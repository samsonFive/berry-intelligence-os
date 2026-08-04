# ADR-0001: JSON files are authoritative

## Status
Accepted

## Decision
Trusted intelligence records will be stored as human-readable, versioned JSON files.

## Rationale
The system must remain local-first, portable, Git-compatible, inspectable, and independent of proprietary SaaS platforms.

## Consequences
Generated databases and indexes may improve performance but must be rebuildable. Concurrency and collaborative editing are deferred.
