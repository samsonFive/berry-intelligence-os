# Continue Competitor Identity and Genetics Verification work

Work in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-identity-genetics-verification-v1`,
branch `research/competitor-identity-genetics-verification-v1`. Read
`artifacts/competitor-identity-genetics-verification-v1/CHECKPOINT.md`
first. Do not re-run the 17-entity or 3-relationship research from
scratch — it is settled and documented with evidence.

This branch does not overlap Sol's source activation, Luna's full-suite
validation, or Grok's briefing prototype. Do not touch Source records,
acquisition code, collection execution, `/competitors` visual design, the
Daily Intelligence Briefing prototype, or Radar.

## Settled facts — do not re-derive

1. 8 of 17 provisional entities promoted `unverified` -> `active` with
   real primary-source evidence; 9 retained provisional with a specific,
   documented reason each (not vague "insufficient time").
2. Planasa/Planasa-2/Plantas de Navarra: **already resolved** before this
   mission via `data/configuration/entity-identity-redirects.json`
   (decided 2026-09-01) — confirmed via the existing
   `audit_entity_identity()` auditor as the only duplicate in the whole
   69-company graph. Do not re-investigate.
3. Exactly 1 of 3 seeded genetics relationships upgraded (AgroBerries <->
   Mountain Blue Orchards, now `licenses`/`active`/`high` confidence with
   a real FreshFruitPortal citation); the other 2 searched and left
   pending — absence of evidence is not disproof.
4. 19 previously-withheld handwritten mappings reclassified into 8
   categories; 0 promoted to a seeded relationship. No illegible
   handwriting was guessed at.
5. 65 focused tests pass; a 198-test regression sweep found no side
   effects; `scripts/validate_records.py` passes. Full suite not run
   (Luna's scope).

## Next concrete steps, in order

1. A human decision is needed on: AgroBerries/BerryWorld possible
   corporate-family relationship, Gem-Pack Berries/Well-Pict possible
   merger, and The Berry Collective's true identity — this mission
   deliberately did not force any of these three.
2. Marionnet's current legal name/entity needs a primary-source check
   (post-2018 acquisition by Agri Finest Company group).
3. If new authoritative evidence later surfaces for any of the 9 retained-
   provisional entities or the 2 retained-pending relationships, re-run
   this mission's same evidence bar (primary source preferred, external
   verification required before strengthening a status) rather than
   promoting on inference alone.
4. Do not create a Variety entity or relationship from this mission's
   findings without new evidence naming a specific variety.

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-identity-genetics-verification-v1`
per command. `scripts/_gen_identity_genetics_verification_v1.py` is a kept,
non-runtime generator; it is idempotent for entity status/alias changes
(re-running it will not error or double-apply) but will overwrite its own
output JSON files under
`data/imports/competitor-identity-genetics-verification-2026-09-15/` each
time.
