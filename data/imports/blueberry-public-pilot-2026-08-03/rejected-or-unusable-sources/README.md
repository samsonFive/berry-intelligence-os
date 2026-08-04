# Rejected and unusable sources

Sources that were reached for during Waves 1 and 2 but did **not** become evidence records, with
the reason in each case. This list exists so that a later wave does not silently re-walk the same
dead ends, and so that a reviewer can see which facts rest on a substitute source rather than the
preferred one.

Two categories are distinguished:

- **Unavailable** - the source could not be retrieved or yielded no extractable content. Nothing is
  asserted about its quality. These are re-try candidates.
- **Rejected on quality grounds** - the source was retrieved but does not meet the evidence
  standard in the brief (no attribution, no method, retail listing, snippet-only, or a republished
  press release offering no independent confirmation).

No search-result snippet was used as evidence anywhere in this package. Every value in every
record traces to a page that was opened.

---

## 1. Unavailable: could not be retrieved or yielded no extractable text

| Source | What was wanted from it | Outcome | Consequence for the package |
|---|---|---|---|
| `https://patents.google.com/...` (bulk programmatic fetches) | Patent front pages at volume | All bulk fetches errored | Substituted with the patents index returning Lens.org records; individual pages retrieved one at a time where needed |
| `https://fallcreekcatalogs.com/2025/01/23/cargo/`, `/sekoya-crunch/`, `/sekoya-nova/` | Fall Creek catalogue descriptions | `disallow_by_robots` | Fall Creek variety detail rests on the patent record and the main Fall Creek site |
| `https://www.blueberrybreeding.com/meadowlark` | UF Meadowlark programme page | 404; correct path is `/meadowlark-fl01-173` | Corrected URL was used |
| `https://ffsp.net/varieties/blueberry/meadowlark` | FFSP licensing page for Meadowlark | 404 | Meadowlark licensing detail is thinner than for other UF releases |
| `https://www.berryworld.com/en-gb/berries/varieties/berryworld-twilight` | Per-variety page for Twilight | "Page not found" | `variety-twilight` remains `unverified` |
| CFIA blueberry index `blueberrye.shtml` and record `app00011181e` | Canadian PBR records | 404 | The working index `ble.shtml` was used instead |
| `https://www.mountainblue.com.au/` subpages | Mountain Blue variety pages | Intermittent timeouts on repeat fetches | Some Mountain Blue detail rests on a single successful fetch |
| `https://sekoyafruit.com/members/` | SEKOYA member roster | Renders only an availability-calendar contact block; no names published | The 14-vs-15 member-count conflict (`fact-fall-creek-commercial-platforms-2026-3`) is therefore unresolved |
| `https://www.gob.mx/cms/uploads/attachment/file/322756/GacetaDOV1erTrim18.pdf` | Mexican DOV numbers for the Ridley series | Fetched, but only front matter extracted from the cleaned text | Mexican registration numbers recorded as not available |
| `https://planasa.com/varieties/` | Planasa full variety list | Returned cookie-consent boilerplate only | Planasa coverage limited to Blue Manila and Blue Maldiva |
| `https://www.businesswire.com/news/home/20250219105540/en/` | English-language release | HTTP client error | Not used; a Chinese-language variant existed but was not usable as an English-language primary |
| `https://active.inspection.gc.ca/.../bl/bl132e.pdf` | CFIA blueberry examination report | Fetched but returned undecodable binary | The parent journal index page was used instead |
| `https://active.inspection.gc.ca/.../applist/appliste.shtml` | CFIA pending application list | HTTP client error | Pending Canadian applications are not covered |
| `https://blugenix.com.au/varieties/` and `/our-varieties/` | Per-variety BluGenix data | Fetcher timeout / client error; the homepage carries marketing copy only | BluGenix variety detail rests on the Produce Report launch article |
| `https://www.driscolls.com/about/our-story` | Driscoll's founding history | HTTP client error | Driscoll's founding year rests on secondary sources and is flagged as such |
| `https://www.hortifrut.com/hortifrut-acquires-atlantic-blue/` | Primary announcement of the Atlantic Blue acquisition | HTTP client error | The acquisition rests on the Leaders League report |
| `https://patents.justia.com/assignee/planasa` | Planasa patent portfolio | Fetcher timeout | Substituted with the Justia page for PP31,345 |

## 2. Rejected on quality grounds

| Source | Why it was not used as evidence |
|---|---|
| `https://patents.justia.com/search?q=blueberry&assignee=Planasa` | Assignee filter did not function; page returned navigation chrome plus two unrelated results. A search interface that does not filter cannot support a negative finding about portfolio scope |
| `https://www.globalplantgenetics.com/crops/blueberry/` | Carries an unattributed storage claim - "after 25 days maintains 80% firmness, Brix 12.5%, acidity 0.9" - with no cultivar, method, site or season. Unusable as a measurement and too thin to record even as an attributed claim |
| `https://www.freshdirect.com/...` retail listing | A retail product listing. Used only to establish that "Mighty Blues" is a Naturipe brand; not used for any trait, volume or ownership fact |
| `https://kingberry.eu` | Search results indicated an unrelated Polish grower. Not fetched, not used, and no link to Agrovision was established. Recorded here so the apparent lead is not chased again |
| Wikipedia pages for Driscoll's, Planasa and Costa Group | Not rejected outright, but treated as tier-3 secondary and flagged at every point of use. Where a founding year or family-ownership statement rests on Wikipedia alone it is classified `claim`, not `fact` |
| Trade articles that reproduce a company press release | Not counted as independent corroboration of the release. Where both exist, the release is the evidence and the trade article is not double-counted |
| Search-result snippets, in all cases | Never used. The brief excludes them and no record in this package depends on one |

## 3. Effect on confidence

Three material facts rest on a substitute source because the preferred primary was unavailable:

- The Atlantic Blue acquisition value and date (Leaders League rather than the Hortifrut release).
- Driscoll's founding year (secondary sources rather than the company's own history page).
- BluGenix per-variety trait figures (a trade launch article rather than the breeder's variety pages).

Each is classified and confidence-scored accordingly in `facts/`, and each is listed in
`coverage-gaps.md` as a re-try candidate for the next wave.
