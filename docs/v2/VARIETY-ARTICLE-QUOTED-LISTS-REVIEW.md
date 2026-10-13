# Selected articles: quoted lists and paragraph crop scope

The original Hortifrut genetics page exposed a shared automated discovery miss.
The app recovered 18 original paragraphs with HTTP 200, including 24 literal
names across blueberries, raspberries and blackberries. Its quick name check
returned only Rocio and Corona. Most remaining names already had manually
accounted source/candidate entries, which did not make automated detection work.

The selected-source check now detects all 24 with correct crop assignment and no
unexpected names. The original source is
[Hortifrut Genetic Development](https://www.hortifrut.com/innovation/genetic-development/).
Expected names were recorded from the native source read before parser edits;
the before/after reports and full captured text stay ignored. This is one bounded,
agent-checked source comparison, not a human Gold Set or global recall estimate.

## Shared repair

- Selected text keeps paragraph boundaries. Explicit crop words in that paragraph
  override publication-wide tags, preventing blueberry tags from assigning Camila,
  Amara or the Pacific raspberry names to blueberries. Crop context does not carry
  into another paragraph. A direct crop in a declaration can resolve a mixed-crop
  paragraph; ambiguous quoted lists remain unresolved.
- Bounded quoted lists accept a positive cultivar declaration after the names,
  such as “are the first varieties” or “are some of the ... raspberry varieties”.
  Lists must begin at a paragraph/sentence boundary, and stay whole within bounds.
  Ordinary brand, quality, partner and parentage prose does not become a name list.
- An explicit license / varieties colon accepts a quoted list and a bounded second
  list after source attribution. It does not scan every quotation in the article
  or create license, ownership, current-rights or trait relationships.
- A negated forward declaration is refused. The first regression run exposed
  a pre-existing false positive from “no license ... varieties:”; its clause guard
  now passes, along with the positive source cases.

The default corpus/list path still does not hydrate article bodies or capture
sources. No provider, new acquisition process, model qualification, schema or
canonical writer is added. Existing publication/identity decisions, rejections,
user aliases, source URLs and private/public boundaries remain separate.
The existing explicit action may persist untrusted candidates; GET only previews
the selected result. Neither operation approves identity or source claims.

## Validation and limits

103 affected discovery, Reader, Digest, navigation and recall tests pass in
73.88s with one existing ReportLab warning. Canonical record validation passes;
portfolio audit remains 255 sections / 972 occurrences / 707 proposal keys /
64 mixed-status catalog records, with 23 initial registry enumeration gaps and
58 source follow-ups. No data files or governing guide changed in this follow-up.

Native desktop review finds 24 names, links Keepsake to its existing catalog
entry, and shows 23 candidate entries. Applying Raspberry retains selected-source
context and gives five Pacific names with the correct crop. This was read-only;
no real candidate/review action or permission decision was submitted. Preview
has four fictional candidates and one fictional article, excluded from real
counts. Phone acceptance of this follow-up remains unverified.

The unchanged summary diagnostic stays 23/24 cases and 60/64 expected names,
with zero unexpected names and four unsupported raw-body misses. The new actual
selected-article proof does not redefine that fixture or disguise acquisition
gaps. Most saved publications still lack original readable bodies; private
selected captures do not change the canonical-only coverage count.

Parent draft #355 has all four green required checks (4,341 passed / 11 skipped /
two warnings in 441.39s). Draft #356 also passes all four checks: 4,351 passed / 11 skipped / two warnings
in 520.89s.
Broader acquisition/independent coverage, current rights, attributed photos,
human catalog authoring and release review remain open. No merge, deployment
or other-berry Landscape rollout.
