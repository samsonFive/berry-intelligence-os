# Competitor source-coverage summary — 2026-09-15

This is a read-only audit of the required 33-name roster against the current base. Entity existence alone is not called tracking.

- 11 of 33 roster labels resolve uniquely to existing canonical company entities.
- 22 do not resolve and were reported without creating or changing entities.
- Maturity counts after the isolated canary: level 1 = 5, level 2 = 5, level 3 = 0, level 4 = 1, level 5 = 0, unresolved = 22.
- California Giant resolves to `company-california-giant-berry-farms` at level 1: entity represented. It has zero explicitly linked Sources, zero runnable linked Sources, no readable article from a linked Source, and no usable published company coverage in the last 90 days.
- BerryWorld reaches level 4 because its linked newsroom Source discovered successfully and yielded a readable body in the canary. The only staged draft is dated 2025-08-29, so it does not establish current coverage.

Resolved labels: Advanced Berry Breeding, BerryWorld, California Giant, Fall Creek, Fruitist, IQ Berries, Mountain Blue, Planasa, University of Arkansas, University of Florida, Wish Farms.

Unresolved labels: AgroBerries, Australasian Plant Genetics, Black Venture Farm, Costa, Denning Blueberries, Expoberries, Fresh Forward, Gem-Pack Berries, Hortifrut Genetica, Marionnet, Oishii, Ozblu, Pairwise, Perfection Fresh, Plant Sciences, Royakkers, Smart Berries, Splendor Produce, SunBelle, The Berry Collective, UC Davis, Well-Pict.

The audit accepts a later canonical roster as a JSON list or `{ "competitors": [...] }` through `--roster`; Claude's entity work can therefore be consumed without redesign or duplicate entity creation. Full machine-readable results are in `competitor-source-coverage.json`.
