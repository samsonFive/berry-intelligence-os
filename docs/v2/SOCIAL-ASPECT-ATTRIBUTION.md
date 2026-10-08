# Competing-food aspect attribution — October 7, 2026

Literal extraction version `social-literal-4` conservatively handles another food in an aspect descriptor's clause. For example, “Blueberries are sweet. Cashews are crunchy and bananas are soft” retains positive blueberry flavor but leaves texture uncertain and untargeted. A bounded EN/ES/PT/ZH/JA food list and punctuation boundaries retain original evidence spans and explicitly record the competing-food uncertainty. This is not a general grammatical parser; combined clauses can intentionally remain uncertain even when a human could resolve them.

Five new language regression cases check the same separation with exact original offsets. The affected pipeline/routes suite passed92 tests, one existing dependency warning. Refreshed synthetic reports retain all-berry246/246 checks and blueberry202/207, including the same five conservative negation disagreements. Independent live grades remain0; these counts do not qualify native-language accuracy.

Versioned private analyses require offline replay/reanalysis to reflect the change. Back up private SQLite first, preserve reviewed corrections and removal tombstones, and replay retained payloads through the existing Store ingestion path without new source calls. Already saved private records can still show version3 until that replay. No registry, trusted Evidence or canonical schema migration. Rollback code and restore an operator-selected private backup if the previous unreviewed analyses are required; preserve subsequent unrelated changes.

Remaining limits include unlisted foods, anaphora, irony, clauses without punctuation and ambiguous descriptor ownership. No paid provider/model, live collection, source rights qualification, merge or deployment occurred.
