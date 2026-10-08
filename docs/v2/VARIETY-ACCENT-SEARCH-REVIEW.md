# Accent-tolerant variety review search

Typing Merida now finds the source-listed Mérida entry, including when company,
crop and original-source filters are active. Native review previously reproduced
zero results for Merida and one for Mérida. Search now compares Unicode text
without combining accents, while preserving the user's literal query in the
input and navigation URLs. This is a navigation comparison only.

Stored names, candidate IDs, aliases, human decisions and source references are
unchanged. Non-Latin characters are retained, and code punctuation remains
significant: PB-17 does not silently become PB17. Company, berry, source, status,
rejected-item and alphabet gates retain their existing behavior. No fuzzy
identity resolution, new alias, role, trait, rights status or schema is added.

55 focused navigation, original-source and portfolio tests pass in 102.43s with
one existing ReportLab warning. They exercise accented/decomposed/unaccented
queries, company-name search, crop/source/status exclusions, rejected records,
unchanged analyst fields and URL queries, Chinese names and literal codes.
Records validate. This branch changes no data files or governing build guide;
parent #353 already verified all 2,771 baseline JSON files unchanged.

Native desktop review on the updated local preview at port 18564 verifies
Merida returns one entry within the existing Berries del Oeste strawberry /
Mérida-profile scope. The result retains spelling Mérida and candidate anchor
vcand-c584f27fb47f, separate-candidate identity and hidden unconfirmed photos.
Preview includes four fictional names: 711 visible versus 707 real source keys.
No real decision or permission form was submitted. Phone acceptance is not
claimed. Draft #354 exact head 2dd0ac8b4745b89e8caf9cae710782d659e993f2 passes all four
required checks: 4,336 passed / 11 skipped / two warnings in 661.22s,
run 37809475229.

The first restricted preview process remained alive without opening its port.
A diagnostic runner using the same tested local code started successfully with
normal application permissions. Only the specifically identified non-listening
helper processes were stopped afterward; existing previews and runtime data
were preserved. This was a local runner limitation, not a deployed app restart.

Parent #353 passes all four checks with 4,331 tests. Scope remains 244 source
sections / 972 occurrences / 707 proposal keys / 64 mixed-status catalog records.
23 registry enumeration gaps, 47 source follow-ups, independent recall, official
rights verification and human catalog authoring remain open. Readable Singrow,
Biogea and Berry Collective source-gap research is retained separately; unclear
commercial labels and input products have not been imported as cultivars.
No merge, deployment or other-berry Landscape rollout.
