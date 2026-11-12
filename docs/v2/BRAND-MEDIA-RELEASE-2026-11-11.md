# Image-display release preparation

The user explicitly authorized deploying the image-display changes to the live
app. The release branch is reconciled onto `c0b50d9e` (News recovery #556),
preserving the later News changes and the expansion guide verbatim. It does not
include the separate experience-consolidation candidate.

The image display uses direct official-page references: two company logos and
three visually inspected Driscoll's packaging images. Five real browser image
loads, expansion and Compare passed on the feature candidate. No paid provider
request, image-object cache, generated branding or new primary destination.

The bounded public seed contains only five official-reference asset records,
not the private social snapshot or a replacement runtime index. Run
`scripts/seed_brand_media.py --inbox PATH --data DATA` to plan and add `--apply`
only during a quiesced writer window. Every existing asset/decision wins;
new seed rows are never marked as analyst selections or primary overrides.

Local validation: 311 affected image/social/company/auth checks passed on the
feature candidate, and 40 additive-seed checks passed after reconciliation.
The actual five-row seed passed dry-run, first apply and zero-write repeat.
Record validation and whitespace checks pass. The four repository checks must
pass on the final PR head before merge; local checks do not substitute for CI.

Deployment requires a fresh verified server-local runtime backup, a restored
isolated copy and successful bounded preservation/seed rehearsal, retaining
the 2 GiB available-memory and 10 GiB free-disk floors. Preserve the live mounts,
effective environment, authentication, schedulers and prior immutable image /
Compose override for rollback. Code rollback must not rewind newer runtime data.
Final exact revisions, runtime-preservation counts and live smoke results are
recorded in the private server release receipt after deployment.
