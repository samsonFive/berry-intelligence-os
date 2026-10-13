# Session-only previews of held variety photos

The user explicitly requests an **Ignore permission** button when a named
variety photo has been found but reuse permission is not recorded. The private
gallery now offers that button alongside the source credit. Choosing it creates
the image element and loads the original asset directly in the browser. **Hide
photo** removes it and revokes the session choice. Permission remains visibly
unconfirmed; no saved reuse field, review decision or publication state changes.

## Behavior and boundaries

- Only the selected photo loads. Other held photos stay unloaded.
- The exact source-page and image URLs key `sessionStorage`, per tab. Reloading
  or moving between candidate detail and its photo editor retains that choice.
  A new session, replacement image or changed source URL requires another choice.
- When session storage is unavailable, the control works in the current view.
- The control is a client-side button, with no app POST or private-file write.
  Attribution, source links and the unreviewed image association remain visible.
- A failed image retains its caption, credit, original links and unavailable
  message. Without JavaScript, original links remain available.
- Readonly/static output excludes the private gallery and override controls.
  The browser choice does not grant permission or enable public publication.
- Returning from the photo editor preserves the candidate's filters and anchor,
  including after a saved edit. Return paths are restricted to that target's
  local candidate queue or variety profile; external/malformed paths fall back.

## Named source population

[BerrYum's current product page](https://www.berryneo.com/en/varieties-berryum/)
lists six blackberry products: FURIA, EQUA, NEMUS, KALIKA, INDRA and KROLA. Each
individual page and its fruit photograph were visually checked. The images
include the variety label; decorative brand artwork was excluded. The publisher
does not name the photographer, so credit says **Berryneo / BerrYum · Photographer
not credited**. [The publisher's legal notice](https://www.berryneo.com/en/legal-notice/)
requires written consent; none is recorded. These six photo associations stay
held until an explicit private session choice or separately recorded reuse basis.

The existing imports/name-review pipeline carries one bounded source section,
six name occurrences and six source photos. BerrYum remains the existing brand
entity, not an inferred company/breeder. Product labels pair with base labels
in the comparison chart without approving aliases or denominations. LOCH NESS
is explicitly excluded as a chart comparator, not a seventh BerrYum product.
The production calendar repeats Furia/Kalika by growing system, not cultivar.
Some thumbnail anchors point to other products; image matching uses the actual
individual page and printed photo label. Marketing charts, health copy and
production months do not become approved traits, performance or growing regions.
This is current-page coverage, not the complete lifetime portfolio.

## Verification and remaining work

Fifty-seven focused photo/portfolio/crosscheck tests pass; the return-path test
also passes after malformed-URL fallback was added. The shipped JavaScript runs
against isolated DOM/session adapters: default no-load, single-photo selection,
reload, fresh session, changed URLs, revocation, unavailable storage and failed
images are exercised. Persistent storage/network writes are forbidden in that
test. Canonical records and JavaScript syntax pass; expansion guide unchanged.

Native browser review confirms the real 650px Furia asset loads on explicit
choice. Candidate-to-editor session carryover, reload and Hide photo are checked.
The repaired return retains `q=Furia`, `berry=berry-blackberry` and the candidate
anchor. Phone content/scroll widths are 360px/360px. Normal viewport restored;
final view returns to the held-photo state. No runtime JSON files were added or
changed, and no source/identity/photo-review decision was made. Screenshots and
source capture proof remain under ignored inbox storage.

An initial test-count edit also changed an unrelated ABZ expectation; it was
corrected. The restricted local run could not use existing temporary/cache
paths, and its subsequent sandboxed run stalled. The affected owned test process
was stopped; the fresh permitted test run passes. No application behavior was
changed to satisfy these environment failures. Exact new-head executable CI is
required; parent draft #332 passes all four checks (4,133/11/two warnings).

Current audit: catalog **64**, primary occurrences **537**, text matches **33**,
identity review needs **504**, source sections **51**, derived candidate keys
**448** before private state. Of 77 registry rows, 22 have some enumerated names;
55 initial checks and seven source follow-ups remain. Seven source-labeled
photos: one recorded reuse basis, six held, zero approved for public publication.
CAT-01/CAT-02/TD-116, wider photo population and human publication remain open.
No merge, deployment or other-berry Landscape rollout.
