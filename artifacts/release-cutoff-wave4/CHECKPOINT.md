# Release-cutoff Wave 4 candidate

This candidate extends the completed Publication Review Wave 4 atomic checkpoint without restarting or discarding it. The final exact SHA is the tip produced by the release-manifest commit and is verified externally by the final local/remote and Luna checks.

## Inputs

- Publication Review Wave 4 checkpoint: `00a6e31edda6c3bc6f8542404863edf599860f43`
- PR #255 exact green head: `3c585f23c39a4fd033bfc4fe944e89bb9626dea9`
- TD-THREAD-002 published coverage: `1b01aab6b8bf69714a831fa5406c88a0d745a724`
- Product Visual System Slice 2: `0ec6904f2ffacea17637b2aa92782f89de2cb8e6`

Publication Review retains its exact contract, candidate pack, safety audit, backend `cf6d19319363dadd20d7182d5b8aaf3f97726d7b`, read-only UI `d19ee0a35033a574dec6c03ecf6aa5008ed7102d`, and Luna validation `7873a685042f1bd4d16d93137981737854802be4`.

## Cutoff exclusions

The following work started after integration began and is excluded:

- Claude durable-read-model V1
- Grok PVS Slice 3
- High-fast calendar-determinism recovery

PR #253 is open, conflicting, and has no reported checks. PR #254 is a draft and has no reported checks. Neither meets the cutoff gate and neither is included.

## Preserved boundaries

- Publication review UI remains private, read-only, and disconnected from mutation commands.
- TD-THREAD-002 expands only the eligible published-Evidence candidate universe and does not broaden its matcher.
- PVS Slice 2 changes presentation while preserving 33/33 roster/profile semantics and unknown/unassigned honesty.
- PR #255 adds Learner content and calendar-stable checks without turning learning content into trust objects.
- No post-cutoff work, live review decisions, auto-publication, or trusted Atomic Evidence promotion is included.

The exact final combined head must pass the complete release gate and independent Luna validation before merge or deployment.
