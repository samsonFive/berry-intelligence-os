# Berry command runtime

This is the separately configured, token-guarded CopilotKit 1.86.0 runtime for the
authenticated FastAPI gateway. The React client uses the same investigation
actions as direct controls. Ordinary page interaction does not start a model turn.

Use Node 24 or later and pnpm 11.25.0:

```powershell
pnpm install --frozen-lockfile --ignore-scripts
pnpm test
pnpm start
```

The dependency store is shared with `frontend/.pnpm-store`. Guard tests run
without provider credentials and can also be invoked directly:

```powershell
node --test tests/*.test.mjs
```

The server requires an explicitly selected `BIOS_COPILOT_MODEL`, its matching
server-side provider key, and a `BIOS_COPILOT_RUNTIME_TOKEN` of at least 32
characters. `BIOS_COPILOT_PORT` defaults to 8200. The FastAPI gateway must use the
same token and point at the loopback `/copilot` endpoint. Credentials never belong
in the frontend, URL state, Docker build arguments, or committed configuration.

The runtime exposes the supported single-route protocol behind its token guard.
The configured SDK/provider must still pass a separately approved real tool turn;
metadata discovery and deterministic tests do not establish that acceptance.

`Dockerfile` is built from the repository root:

```powershell
docker build -f copilot-runtime/Dockerfile -t berry-command-runtime .
```

The server binds loopback. A separate container therefore requires the gateway's
network namespace or a reviewed network arrangement. Runtime network/deployment
configuration remains with the release owner. The main application Dockerfile
builds and copies Vite assets independently; generated assets are excluded from
Git and the Docker build context.

The explicitly supported Perplexity profile is
`BIOS_COPILOT_MODEL=perplexity:openai/gpt-5.6-sol`. It reads the existing canonical
`PERPLEXITY_API_KEY` in memory at invocation time and uses Perplexity's fixed
`https://api.perplexity.ai/v1/responses` Agent API alias. The SDK's OpenAI-compatible
adapter is selected only for that transport; the key is never copied into
`OPENAI_API_KEY`. No preset, hosted web search, alternate destination or automatic
provider fallback is enabled. The documented function-tool protocol and model
are described in the [official custom-function guide](https://docs.perplexity.ai/docs/agent-api/tools/custom-functions)
and [compatibility reference](https://docs.perplexity.ai/docs/agent-api/openai-compatibility).

`BIOS_RESEARCH_CREDIT_FREE_ONLY=1` continues to block paid command runs. A dedicated
rehearsal process can separately set `BIOS_COPILOT_ALLOW_PAID_COMPARISON=1` only
after operator authorization. That permit allows one user-message/thread identity
with the exact command `Compare Fall Creek and Costa in China`, accepts at most
eight continuation requests, and rejects additional commands and unknown tools.
The Python research setting remains unchanged. This configuration is not enabled
by source changes, and ordinary runtime mode does not receive a paid allowance.

All tests intercept provider transport or exercise local guards; they make no
paid provider request. A transport fixture is not a successful real model turn.
For an authorized rehearsal, record only terminal SDK usage totals and sanitized
status. Do not log prompts, tool payloads, credentials or raw provider errors.

The supported AI SDK LanguageModel wrapper preserves the installed model's
getters and method binding. It advertises only the seven registered investigation
functions to the provider and rejects unapproved returned tool names before the
SDK can execute them. This excludes BuiltInAgent's automatically injected
`AGUISendStateSnapshot` and `AGUISendStateDelta` helpers from the command boundary.
The guarded-handler tests exercise the actual streaming Responses path, in
addition to the lower-level JSON function-loop fixture.

The dedicated process emits `Berry command diagnostic: ` followed by allowlisted
JSON receipts: tool counts, known error category/code/parameter, HTTP error
status, validated request ID, terminal type and numeric token usage when exposed.
Freeform error messages and request/response bodies are excluded. The first
funded G1 attempt failed; its historical terminal details were not retained, so
these boundary and diagnostic corrections do not establish its exact cause or
authorize another paid attempt.

## Local release-shaped smoke plan

PR CI retains `experience-client-<source SHA>-<run attempt>` for three days.
It contains only the compiled `client/`, a versioned `client-manifest.json`
with every path, byte count and SHA-256, and command-image size metadata.
CI requires those client bytes to match the independently built web image.
This permits a reviewed release to copy the verified client without repeating
the frontend dependency build on a constrained Docker host. Validate the source
SHA and every manifest entry before use. Existing offline model resources and
the actual production configuration still require explicit preservation.

This is a prepared plan, not an executed deployment. Docker is unavailable in
the current Windows tool environment, so image builds, merged Compose validation
and container health remain unrun. Local source tests/builds do not replace
required final-head CI or production acceptance. This plan's startup and smoke
steps make no model turn. Paid acceptance follows the separately recorded,
current user authorization; a retry rejected by automatic approval review needs
that rejection resolved before execution, including its stated private-selector
metadata transfer and credit-spend scope.

The source option runs FastAPI and Node as separate processes on the same host:
serve FastAPI on `127.0.0.1:18000`, Node on `127.0.0.1:8200`, and configure Python's
gateway URL as `http://127.0.0.1:8200/copilot`. Both processes receive the same
private runtime token. FastAPI uses authoring mode, real session login, an
isolated writable rehearsal runtime, `ENABLE_SOURCE_POLLING=false` and
`BIOS_RESEARCH_CREDIT_FREE_ONLY=1`. Node uses the fixed Perplexity profile above
and its existing canonical key, with the paid comparison flag absent or `0`.
After the already installed locked dependencies and built assets are verified,
the two foreground commands are `python -m uvicorn app.main:app --host 127.0.0.1
--port 18000` from the repository root and `node copilot-runtime/server.mjs`
from another terminal in the same root. No Vite dev server or public runtime
port is involved. Stop only the two processes started for this rehearsal.

For Linux containers, use the separate, optional
`deploy/docker-compose.copilot.yml` together with the existing base Compose file.
The Node service uses `network_mode: service:app`: it shares the application's
network namespace, so its loopback listener is reachable by the gateway's
literal loopback URL. Two ordinary bridge-network containers cannot reach one
another through `127.0.0.1`; a service-name URL would be rejected by this gateway.
The override does not publish a Node port or share application volumes with it.
This matches [Docker's container-network model](https://docs.docker.com/engine/network/#container-networks)
and [Compose service networking](https://docs.docker.com/reference/compose-file/services/#network_mode).

The override is opt-in; the base deployment remains unchanged when that file is
omitted. It preserves existing Python provider-key configuration and all runtime
mounts. It forces credit-free research and disables source polling. The one-shot
deployment permit has a distinct variable and defaults to `0`; an old ephemeral
rehearsal flag cannot enable it. The Node service does not automatically restart,
which prevents a crash/restart from silently resetting that permit's in-memory
command identity. Recreate the app and Node together when replacing the app's
network namespace.

| Setting | Where needed | Handling |
| --- | --- | --- |
| `BIOS_REVIEW_USERNAME`, `BIOS_REVIEW_PASSWORD` | Existing FastAPI session login | Operator-owned private environment; never print rendered configuration |
| `BIOS_SESSION_SECRET` | FastAPI | Separate strong secret from the review password |
| `BIOS_COPILOT_RUNTIME_TOKEN` | FastAPI and Node | Matching private secret, at least 32 characters; no browser exposure |
| `PERPLEXITY_API_KEY` | Existing configured features and Node | Existing canonical variable, supplied at process start; no `OPENAI_API_KEY` copy |
| `BIOS_COPILOT_MODEL` | Node | Fixed `perplexity:openai/gpt-5.6-sol` in this override |
| `BIOS_COPILOT_RUNTIME_URL` | FastAPI | Fixed `http://127.0.0.1:8200/copilot` inside the shared namespace |
| `BIOS_RESEARCH_CREDIT_FREE_ONLY` | Both processes | Forced `1`; no research activation |
| `BIOS_COPILOT_DEPLOY_PAID_COMPARISON_PERMIT` | Optional override input | Defaults `0`; only an explicit newly approved turn permits `1` |
| `BIOS_DEMO_RUNTIME` | Base Compose persistent mounts | Explicit isolated rehearsal directory, never production runtime paths |
| `BIOS_BACKUP_HOST_DIR` | Base Compose backup mount | Isolated rehearsal backup directory; do not inherit production backup paths |
| `BIOS_APP_BIND`, `BIOS_APP_PORT` | Host-facing FastAPI port | Use `127.0.0.1` and an unused port such as `18000` for the local smoke |

Use an existing protected operator environment/secret store. Do not create a
second key file, put secrets in build arguments, or paste `docker compose config`
output. The following commands are prepared for an authorized Docker host,
from the repository root; they have not been run here:

```sh
# The protected environment is already provisioned; no values are echoed.
# Explicit local-only overrides take precedence over values in deploy/.env.
export BIOS_DEMO_RUNTIME=../demo-runtime/experience-smoke
export BIOS_BACKUP_HOST_DIR=../demo-runtime/experience-smoke/backups
export BIOS_APP_BIND=127.0.0.1
export BIOS_APP_PORT=18000
export BIOS_COPILOT_DEPLOY_PAID_COMPARISON_PERMIT=0
# Use the same project name, files and environment for every command below.
docker compose -p berry-experience-smoke --env-file deploy/.env -f deploy/docker-compose.yml -f deploy/docker-compose.copilot.yml config --quiet
docker compose -p berry-experience-smoke --env-file deploy/.env -f deploy/docker-compose.yml -f deploy/docker-compose.copilot.yml build app copilot
docker compose -p berry-experience-smoke --env-file deploy/.env -f deploy/docker-compose.yml -f deploy/docker-compose.copilot.yml up -d --wait app copilot
docker compose -p berry-experience-smoke --env-file deploy/.env -f deploy/docker-compose.yml -f deploy/docker-compose.copilot.yml ps
```

Before these commands, confirm those isolated runtime/backup paths and unused
host port on the Docker host, and keep deployment permit `0`. Environment
precedence is described in the [official Compose reference](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/).
The existing entrypoint seeds/additively
syncs trusted data into that runtime and creates its inbox directories; it must
not be pointed at production mounts during local smoke. Do not seed private
inbox from the image. If realistic private source bodies are needed, provision
only a separately reviewed rehearsal snapshot through existing tools.

Record the candidate source SHA, built asset fingerprints and image IDs. Check
that the main image contains `app/static/investigation/index.html` from its Vite
stage, source-only runtime image contains no app runtime mounts, and no generated
`static/investigation` appears in public `generated/` output. The root
`.dockerignore` excludes local artifacts, harness runtimes, logs, secrets,
dependency stores and prebuilt investigation assets; required source, lockfiles,
schemas, trusted data and bundled fonts remain available to their build stages.

The no-model-turn smoke must establish:

1. FastAPI and Node health become healthy. Node health performs only the guarded
   SDK `info` request and verifies the `default` agent. `/healthz` alone does not
   establish Node/gateway readiness.
2. Anonymous native/deep Learn/API requests reach the session gate. Log in via
   the real `/login` form; preserve exact context through its safe return URL.
3. The authenticated status endpoint reports configured, and an authenticated
   same-origin `{method:'info'}` gateway POST returns 200 with `default`. No
   `agent/run` is submitted. Direct, wrong-token access to Node is rejected;
   Node has no externally published port.
4. Built assets load; populated Landscape, native navigation, Reader/history,
   grid account layout, saved investigation and explicit PDF flows use current
   domain APIs. Ordinary browsing issues zero `agent/run` requests.
5. Stop just the smoke `copilot` service and verify the direct application and
   Reader remain usable with an honest unavailable command state. Restart only
   for metadata checks with permit still `0`.
6. Retain only safe status, event counts, fingerprints and allowlisted runtime
   receipts. An `info` success is not a successful provider turn. Any paid turn
   remains a separate, explicitly approved acceptance step.

To stop the isolated smoke, run the same Compose command prefix with
`stop copilot app`; optionally remove only those stopped containers with
`rm -f copilot app`. Do not use `down --volumes`, delete bind mounts, or replace
the real deployment's containers as part of this local plan. A later release
rollback stops the command sidecar, restores the prior approved app image and
configuration, and reuses the existing data/inbox/backup mounts. Rollback never
rewinds or overwrites governed/runtime records. The release owner must capture
and approve those concrete image IDs and mount paths before production changes.
