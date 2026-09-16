# Exact commit map

## Base

| Role | Full SHA | Subject |
|---|---|---|
| Wave 2 R1 base | `0b0c6fc65395261afe0c9653640bafcd5a20b394` | Document Wave 2 R1 integration validation |

## Source to integration map

| Source scope | Source commit | Integrated commit | Purpose |
|---|---|---|---|
| Luna gate implementation | `e08dae3266fbde3efc4c4a4b1210b62910377cca` | `2d39965880f8ff668936f673e1218d7238ee3539` | Add the nonmutating quick/full Wave 2 contract gate and artifacts. |
| Luna requested source head | `20c7f26efc5f9dddf7f4aa44e64f639e627a45d2` | `9578df15a60f051903799c3ff3dfbbbc632ba5e3` | Complete the gate checkpoint at the exact requested head. |
| Claude requested source head | `02bd03f675dacd3b066e54aec63468402901073c` | `e544e7ae9e7abd49af3843dfadc5dfbbb205b34a` | Add acquisition diagnostic tests, redacted canary audit, and findings without production acquisition changes. |
| Grok Slice 1 implementation | `558574d073b38fcaf16b52098298319383d33f07` | `77eeb0194bf138fb1962bf159fc745d47209871b` | Move the visual system into the production Daily Briefing and reader. |
| Grok requested source head | `e9801dbb8ee0066f17e7c47981dc2bf77aae71ba` | `073e0c22b9bf21411dfb06c87a4f0f4b8f985d58` | Add the exact requested Slice 1 verification artifacts. |
| Wave 3 verification fix | local integration finding | `25fa04acac8effa488926c56f68268a81d5b5aef` | Restore reader focus to the exact opener after navigation and add regression coverage. |

The Luna and Grok requested heads are follow-up commits whose parents contain the implementation they document or complete. Their complete two-commit logical ranges were applied in source order; applying only the named tip commit would have omitted the reported production scope.

All source commits were descendants of pre-R1 Wave 2 commit `85a157233674ee5cd3d2e358ea02924d3ac04790`. They were replayed onto exact R1 base `0b0c6fc…`, preserving R1 profile-completeness semantics.
