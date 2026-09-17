# All-Ready Dogfood Release V1 — Release Manifest

## Canonical and integration basis

- Canonical target: `v2/intelligence-os`.
- Canonical checkpoint used to begin the interrupted integration: `c0de14c88960c22fee97a51fef0c71ffe386bcf9`.
- Valid recovered Sol checkpoint: `3e68d0a678678a5109801ef12404a94db6c20e96` on `integration/publication-review-wave4`.
- Consolidated branch: `release/all-ready-dogfood-v1`.
- Exact source SHAs are generally not ancestors because the frozen inputs were reconciled or cherry-picked onto the integration lineage. The mappings below name the release equivalents; the source branches remain unchanged.

## Included inputs

| Input | Frozen source SHA | Release disposition | Release equivalent / notes |
|---|---|---|---|
| Wave 3 foundation | `c95c05e51b8247a0b22f417a877088c8d7f20e6b` | Included | Literal ancestor. Includes PVS Slice 1, reader focus fix, Wave 2 R1, acquisition diagnostics, competitor intelligence, and source activation lineage. |
| Publication Review contract | `4c126a6e15d448c4be2f0dae73ddce879fbc0346` | Included | Reconciled as `5491367` / `b33f411` contract documentation. |
| Candidate pack | `8952566625a543f1850b33fcb033ef0aac5a0839` | Included | Reconciled as `aac9568`; bounded rehearsal data remains under test/import artifacts and is not production backlog. |
| Safety audit | `decb97049a79b3d9e7c4f007f4f5977284d27eec` | Included | Reconciled as `2e888a9`; human gate, duplicate safety, compensation, and append-only audit rules retained. |
| Publication command service | `cf6d19319363dadd20d7182d5b8aaf3f97726d7b` | Included | Reconciled as `cbbf35a`; authorization, optimistic concurrency, immutable binding, idempotency, and recoverable transaction boundaries retained. |
| Read-only UI reference | `d19ee0a35033a574dec6c03ecf6aa5008ed7102d` | Included as reference/rehearsal | Reconciled as `ead7a41` + `c877b75`; its fixture-only adapter is enabled solely by `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1`. |
| Durable read model | `2100d2a` | Included | Cherry-picked as `ac1abda`; durable queue/detail queries never expose full acquired bodies. |
| Read-only durable page | `36bff694fb2c6d37899514ef7ef6e819b86c0be2` | Included | Cherry-picked/reconciled as `c1b25b8` + `167dfd1`; it is the production route. |
| Read-only follow-up | `88e89879d3f583881aece3856720c66d801553f3` | Included | Cherry-picked as `6f450c9`; acquisition-failure classification and Review Operations link retained. |
| PVS Slice 2 | `0ec6904f2ffacea17637b2aa92782f89de2cb8e6` | Included | Reconciled in recovered Sol checkpoint (`ebefd01` through `248b34a`). |
| PVS Slice 3 | `dd72be72dd50ac087e51a5089dfef2d357926a02` | Included | Source tip is ancestor of Slice 5; content cherry-picked as `7c4e605` + `5f3e858`. |
| PVS Slice 4 / PR #256 | `69465fa91c7fa8e6f4a79743762fb013f0b0f811` | Included | Source tip is ancestor of Slice 5; content cherry-picked as `2d1eaf4` through `b4af990`. Source PR Python failure repaired in consolidated release. |
| PVS Slice 5 / PR #257 | `3455529598ba6dcfd1ef2e11565ead14bd3a8331` | Included | Verified descendant of Slices 2, 3, and 4. Slice 2 was already integrated, so only non-duplicate Slice 3–5 commits were replayed; Slice 5 maps to `da73708` + `565a6e4`. |
| PR #255 | `3c585f23c39a4fd033bfc4fe944e89bb9626dea9` | Included | Four checks were green on source PR. Reconciled as `6e0f0ad`, `3de9ed2`, `f7011f7`, and `603a042`. |
| Calendar Determinism Recovery | `6e81e48397de9bb3c6743d646f0bf9e40b05b345` | Included | Cherry-picked/reconciled as `f79e45d`; shared UTC clock freezes recency tests. |
| Google News/Pulse/TD-014 | `ca829cdbb39dda585109185ce34f36735de3b51e` | Included | Parent and tip replayed as `0e8e08d` + `2abfac3`; decoded publisher URLs and honest dates retained. |
| Story Threads published coverage | `1b01aab6b8bf69714a831fa5406c88a0d745a724` | Included | Reconciled as `3e57fc8`; matcher scope unchanged. |
| Combined integration repairs | release-local | Included | `4717156`, `167dfd1`, `1797bfc`, plus final gate repair: seed exclusion on Today, single durable review route, fixture-only rehearsal compatibility, restored operator routes, Watchtower/War Room/This Week navigation, export closure, and current domain-pack counts/templates. |

## Ancestry findings

- `cf6d193...` is an ancestor of `36bff69...`; the page lineage contains the command-service backend.
- `d19ee0a...` is not an ancestor of `36bff69...`; its rehearsal/reference UI was preserved separately rather than assumed to be contained.
- `36bff69...` is an ancestor of `88e8987...`.
- `0ec6904...`, `dd72be7...`, and `69465fa...` are all ancestors of `3455529...`.

## Excluded or superseded candidates

| Candidate | SHA / status | Disposition |
|---|---|---|
| PR #253 Radar scope-tag audit | `b6290f3d3efc60d4e1ae0ac2c4e0409cfe9f6860`; open, conflicting, no CI checks | Excluded. Completion, compatibility, and green validation are not demonstrable. |
| PR #254 backlog workbook | `ba2389933651cbdf76df99e984841fdb17264e3e`; open draft, no CI checks | Excluded. It is an approval workbook/draft and does not meet the completed, green cutoff. |
| PR #256 as a separate merge | `69465fa...`; draft, Python failed | Superseded by consolidated Slice 5 descendant plus release repairs. |
| PR #257 as a separate merge | `3455529...`; draft, Python failed | Superseded by consolidated release; its completed presentation changes are included and repaired. |
| Post-cutoff unfinished branches | unspecified | Excluded. No branch was included solely because it existed. |

## Data boundaries

The release imports no ignored inbox state, no live canary queue, no approved publication, and no trusted Evidence generated by an integration run. Tracked canonical additions are frozen feature inputs only. The final gate compares tracked data and ignored runtime state before/after validation.
