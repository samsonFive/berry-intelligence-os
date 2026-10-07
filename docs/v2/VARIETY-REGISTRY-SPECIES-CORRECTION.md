# Black raspberry registry classification

While preparing NIWA primary portfolio expansion, a concrete catalog correctness
blocker was found: the CPVO adapter mapped `Rubus occidentalis L.` to blackberry.
The canonical raspberry entity already includes that species. USDA's
[Rubus nomenclature table](https://www.fs.usda.gov/nsl/Wpsm/Rubus.pdf) identifies it
as black raspberry in the raspberry subgenus, and
[USDA ARS research](https://www.ars.usda.gov/research/publications/publication/?seqNo115=265653)
explicitly uses “black raspberry (Rubus occidentalis L.).” NIWA's primary homepage
also separates [black raspberry from blackberry](https://en.niwabrzezna.pl/).

This narrowly justified exception to the backend freeze changes one species map
entry. New registry review drafts carry raspberry context for black raspberry;
`Rubus subg. Rubus` stays blackberry. It adds no species, changes no schemas,
query scope, identity rules, collectors, existing filings, review gates or
footprints. No provider call or new official filing was captured.

A deterministic monitor integration test checks both crop contexts, untrusted
draft status, idempotence, preservation of operator notes and byte-identical
canonical inputs. The existing species test now covers the previously omitted
black-raspberry case. Required exact-head checks remain the release gate.

Repository search found no stored CPVO filing with this species to migrate.
Operator-private runtime was not copied or rewritten; older reviewed drafts,
if present there, need explicit review of their crop tags. Re-running acquisition
preserves those files rather than silently overwriting them. This does not close
CAT-01/CAT-02 or TD-116, and does not authorize merge, deployment or other-berry
Landscape rollout.
