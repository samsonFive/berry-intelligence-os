# Avoid attributing unrelated pending stories on an entity profile

An isolated current-data catalog rehearsal returned Emerald's profile in
44.872 seconds. A worker-thread profile then recorded 73.722 instrumented
seconds: 52.105 in recent intelligence, including 1,721 global draft-attribution
calls and 899,801 entity-needle preparations. Original patent references took
0.496 seconds. These measurements identify the pending-story scan as the main
delay; they do not make patent references or human gates optional.

`draft_matches_entity` now checks the selected entity's possible title and
newsroom paths before attributing an unrelated draft against every entity.
Body-only mentions already fail the existing about-this-entity rule. Stored
entity links and supplied pending attribution keep their earlier behavior.
Possible matches still use the full authoritative attribution calculation.
Catalog values and source links are read on every call; no record, matching
decision, article body or human disposition is cached.

## Verification

- 39 focused/existing tests pass across attribution, recent intelligence and
  the pending-review read model. Cases cover competing title companies,
  newsroom/source labels, unusual linked-source types, body-only mentions,
  explicit stored links, precomputed suggestions and fresh catalog/source edits.
- Four alternating network-disabled current-data requests took 41.379 / 10.546
  and 41.711 / 10.342 seconds without/with the combined performance changes.
  All four return the same 49,526-byte HTML, byte for byte, including the
  original Emerald patent link. All 65 profiles, 9,767 protected JSON files and
  account rows remain unchanged. Production was not changed.
- The combined comparison includes the preceding Reader/article-source changes
  in this PR. A separate full-context comparison also passes, with no different
  fields after serializing template helper functions by their module and name.
  The first diagnostic incorrectly serialized their process-specific memory
  addresses, causing different hashes even between two baseline runs. That
  failed diagnostic is retained in the private receipts; no data difference was
  suppressed or review state excluded to obtain parity.

Ten seconds remains too slow. Candidate discovery, large coverage pages and
wider request contention stay open under TD-122. This follow-up requires fresh
current-head CI and browser/release review; earlier green checks are not proof
for the new source. It approves no source, identity, catalog entry, publication,
photo right or extraction configuration.
