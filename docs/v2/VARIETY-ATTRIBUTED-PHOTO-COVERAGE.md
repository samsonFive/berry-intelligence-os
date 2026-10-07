# Attributed photos for named varieties

The user requires photographs of the actual named variety wherever they can
be properly sourced and credited. This extends CAT-02's rich-profile work;
it is not satisfied by a generic berry illustration or a company logo.
The first executable slice adds private credited galleries, compact directory
thumbnails and photos inside expanded candidate details. Source population and
human-reviewed public photo publication remain open; no canonical identity,
trait, role, rights or growing-location record is changed.

## Presentation and source requirements

- Lead variety profiles with a compact credited photo or gallery when available.
- Use small thumbnails in directories and expanded candidate details where
  they aid identification. Preserve dense rows, the floating alphabet and
  readable evidence rather than turning the review queue into tall image cards.
- Retain the original photo/source URL, photographer or publisher, caption,
  reuse terms/license link, source check date and exact named variety/code.
- Identify fruit samples, trial plants and patent drawings clearly. A patent
  drawing is a different media type from a photograph.
- A source caption is a proposed identity association until reviewed; keep it
  distinct from approved catalog identity, traits, roles, rights and location.
- Preserve analyst corrections, replacements and removals on subsequent source
  refreshes. Keep human identity/source/publication gates intact.
- Show only reviewed, appropriately reusable assets in the public snapshot.
  Private candidates and unresolved associations remain in the live review
  workspace. A usable source link can remain available while reuse is unresolved.
- Make the caption and source accessible, contain mobile galleries, lazy-load
  images and handle missing/failed images without presenting a substitute as
  a photograph of the named variety.

## Implemented slice

Photo observations extend the existing primary-source name observations. Matching
reuses the existing identity resolver with an explicit berry: USDA's Keepsake
strawberry must never appear on our Keepsake blueberry profile. Multiple catalog
matches are held back. Candidate crop tags from a multi-crop parent source do not
override the candidate's own berry. A source caption remains visibly unreviewed.

The first populated example is Columbia Star blackberry, photographed by Chad
Finn for USDA ARS. Its available magazine image loads at 660px; its original
gallery download links returned 404. The caption/gallery identifier D3403-1 and
the magazine filename d3402-2 differ, so both references and that limitation stay
in the reuse note. The ARS Image Gallery public-domain policy requires credit
and prohibits implied endorsement. Attribution and source URLs are retained;
no generic berry image is substituted. One photo is attached to the existing
Columbia Star observation, without adding another name/source-count occurrence.

The private editor adds/corrects, hides, restores and resets photos. It reuses
the existing profile override file, revision conflicts, atomic writes, saved
history and cross-site edit guard. Source refreshes cannot overwrite these
choices. Unknown reuse shows a source link without an inline image. Credit,
caption, exact name/code, berry, photo type, check date, terms URL and reuse
explanation travel together. Lazy loading, no-referrer images and a missing-image
message retain source links. Source and user photo associations are excluded
from readonly/static output. Public photo publication remains an existing
human-review integration task; selecting a reuse label never publishes a photo.

Native desktop and 375px phone review show the real Columbia Star photo and
credit. The phone gallery measures 375px content/scroll width; the expanded
editor measures 360px/360px after its scrollbar, with only Blackberry offered.
Normal viewport restored. Browser review makes no source/identity decisions or
private photo edits. Screenshots are retained under ignored inbox storage.

Sixty-eight focused photo/navigation/portfolio tests pass, including the
catalog-profile/directory integration case. Canonical record validation and
JavaScript syntax pass; the static build writes 1,755 pages and passes its
unpublished-content scan. This draft's full executable CI is required on its
new head; the previous documentation-only checks are not proof for this code.
Catalog remains 64, primary observations 506 in 46 sections, and derived
candidate keys 423 before private state. No merge, deployment or other-berry
Landscape rollout.

## Remaining coverage

Inspect existing entity/profile and media conventions first. Reuse the current
identity and source-review paths, bounded image handling and private/public
split; do not create a parallel crawler, identity resolver or trust store.
Continue real source-specific photos and their attribution/reuse checks. Rich
catalog photo coverage, human photo-identity/publication decisions and full
patent/claims coverage remain open. No merge or deployment without the existing
release gate.

Current source leads: CFIA descriptions expose labeled photographs; CBC has
individually checked product pages; two AVA technical PDFs were visually
inspected; UGA historical slides include labeled photographs. Those are leads
only. Their image reuse and any catalog association are not established by
having read a page. Raw PDFs and screenshots remain private. Source audit can
continue independently; no missing user information blocks it.

## Previous completed slice

Draft #330, head `8aa8de732388d392031dfcb1975ca2ecd3d9f83d`, passes all four
required exact-head checks, run 37690588963: 4,106 tests passed / 11 skipped /
two existing warnings in 475.48 seconds. The sticky candidate alphabet,
compact phone picker, List top / Filters and original rights-reference links
are implemented and browser-reviewed. The catalog remains 64, primary source
occurrences 506 in 46 sections and derived candidate keys 423 before private
state. Attributed variety-photo coverage is the next retained requirement;
full rights documents/claims, portfolio depth and human catalog authoring
also remain open.
