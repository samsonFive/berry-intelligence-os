# Keep review jobs from competing with production

The 4GB VPS ran out of memory on 28 October 2026. The prior-boot kernel
journal records a global OOM at 06:53:31 UTC that killed the production
`uvicorn` process. The provider console also showed a failed journal service.
Several old app previews had remained running without memory limits. Their
individual contribution was not measured; do not claim one specific rehearsal
caused the outage.

The user authorized server recovery. After inspecting the console, an IONOS
restart restored SSH, logging, Docker and the unchanged canonical production
image. Login GET returned 200 and the authenticated News feed rendered with
images. Original production data/inbox mounts and the release receipt remained
in place. No runtime was restored from a stale copy, no credentials were changed,
and no feature PR was merged or deployed. This is not a claim that all mutable
production files are byte-identical to a historical backup.

Old app previews remain stopped. Four current task previews were additionally
capped at 768MiB, one CPU, 256 PIDs, no swap and `restart=no`. Their bind-mounted
copies and evidence were retained. The small static mobile review server remains
running with its existing 128MiB cap.

## Before any further rehearsal

Prefer local work or CI. On this VPS, allow one temporary app copy at a time.
Never start an old unbounded helper because its SSH connection timed out.
Inspect the actual process, container ID and result receipt first. In this
incident the original navigation preservation check had completed successfully;
its receipt was recovered after the restart, so a retry was unnecessary.

`scripts/run_bounded_rehearsal.py` runs an existing Python preservation check
against an already prepared runtime copy and an already built local image:

```sh
python3 scripts/run_bounded_rehearsal.py \
  --name berry-rehearsal-example \
  --image berry-intelligence-os:review-example \
  --runtime /opt/berry-platform-releases/example/runtime \
  --script /opt/berry-platform-releases/example/check.py
```

It holds `/run/lock/berry-review.lock` for the complete job, refuses any running
container beyond production/Caddy/the static mobile server, requires healthy
production plus 2GiB available RAM and 10GiB free disk, and only accepts a
release runtime copy without symlinks or hard links. It does not create or refresh that copy.
Fixtures use ordinary login and never a real person's credentials.

The job has no network, no published ports, no host credentials, a read-only
container root, a 1GiB memory/no-swap cap, one CPU, 256 PIDs and a ten-minute
default time limit (maximum fifteen). It pins the locally resolved image ID
and never pulls an image. The disposable container is removed by its exact
created ID on success, failure, interruption or timeout; the runtime copy is
retained. Do not raise the memory budget on this host to make a check pass.
An OOM inside that cap is a failed check, not a successful preservation receipt.

The lock coordinates this launcher only: it cannot stop another operator from
running arbitrary Docker commands. The running-container check catches existing
previews, but is not a machine-wide scheduler. Never start separate previews
while this job holds the lock. This tool handles offline scripted checks, not
persistent browser-preview hosting or deployment.

## Recovery checks

Check provider console/status when both SSH and HTTPS fail. Do not reset
credentials, reimage, replace data or weaken a firewall to recover an OOM.
After recovery, verify the production image and persistent mounts against the
release receipt, Docker health, actual login GET and the browser. Keep the
backup and rollback. Release approvals and all human evidence/identity/rights
gates remain separate from permission to recover the server.
