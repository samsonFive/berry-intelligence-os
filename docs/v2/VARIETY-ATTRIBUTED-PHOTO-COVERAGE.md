# Attributed photos for named varieties

The user requires photographs of the actual named variety wherever they can
be properly sourced and credited. This extends CAT-02's rich-profile work;
it is not satisfied by a generic berry illustration or a company logo.
Implementation and photo population remain open. No images were imported,
published or assigned to a canonical variety in this requirements update.

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

## Next implementation slice

Inspect existing entity/profile and media conventions first. Reuse the current
identity and source-review paths, bounded image handling and private/public
split; do not create a parallel crawler, identity resolver or trust store.
Verify one real named-variety image and its attribution/reuse basis before
claiming an end-to-end gallery is populated. Candidate versus catalog identity,
analyst overrides, source fidelity and static exclusion need meaningful checks.
Review actual desktop/mobile photos and captions before pushing the executable
slice as a draft. No merge or deployment without the existing release gate.

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
