# Catalog compatibility with the tested platform

This draft places catalog/source #431 on the tested platform #433. It retains
the source history already assembled in #430/#431 while preserving collaborative
Workspaces, account-private Digest/layouts, on-demand name checks, the visual
guide, News relevance and phone Reader controls. Frozen review heads and their
actual approval questions remain unchanged. Nothing is merged or deployed.

The existing catalog image was built from live `e24b566b`. It must not be used
to replace a later platform image: that would risk undoing platform fixes.
This branch reconciles the code in advance. A later release must use the then
current canonical/platform image and its own fresh verification.

The overlapping photo implementations now use one request-local
`SourcePhotoIndex`. The catalog API projects through the same source-photo
path used by individual profiles, then shares that preparation with held-photo
review links. This retains crop/name/code ambiguity checks, larger-original
preview overlays, stable photo IDs, user captions/hiding and permission gates.
No cross-request cache or saved review decision is introduced. Shared variety
JavaScript references advance to version 13 so browsers receive both changes.

Three integration cases verify the complete current corpus, an exact-code
larger-original preview fixture, once-per-photo validation and rejection of a
different input snapshot. The preview fixture does not create a canonical
alias: the real larger-preview references currently belong to coded candidates.
The full public catalog projection exactly matches individual profile results;
Kwanza and Rutgers D'Light retain their name-review holds.

The final 72 affected checks pass with one existing warning in 37.18 seconds.
A separate read-only comparison against the exact #431 coverage implementation
produces identical 38,504-byte JSON in all four alternating calls, SHA-256
`d788945d46c1e1e2d5a9c0a35299a6220ce439812fc7fa0b16f25b23583576c1`.
Warm function calls remain around half a second; the first reference call had
cold-start overhead. This is public-seed function evidence, not a live-route
performance claim.

The public seed remains 64 profiles, 516 source sections and 1,854 name
occurrences. Photo/rights/cited-trait/company gaps remain 11/13/33/10. Sources,
literal legal stages and numbers, existing canonical records, schemas, the
governing guide and all 31 accepted requirement definitions/order are preserved.
The 65-profile live runtime is a separate population and must never be replaced
with this research seed.

This child requires its own exact-head CI and native desktop/phone review.
After an actual platform release, reconcile its real canonical revision and
image, repeat current-head checks and fresh isolated live-data preservation,
then obtain approval for the intended catalog combination. Existing #430
approval scope does not cover this later combination. Source/name/catalog,
current-rights, claim review, qualification and photo-use decisions stay human.
