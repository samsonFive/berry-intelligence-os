# Remote interactive demo (FastAPI)

This is the **private review instance**, not GitHub Pages.

Public trusted snapshot: GitHub Pages (`generated/`).
Interactive Scanner → review → Approve/Save/Reject: this Docker deployment.

## What gets persisted

Bind mounts from `BIOS_DEMO_RUNTIME` (default `../demo-runtime` relative to `deploy/`):

| Host path | Container path | Role |
| --- | --- | --- |
| `demo-runtime/data` | `/app/runtime/data` | Trusted published records (writable so Approve persists) |
| `demo-runtime/inbox` | `/app/runtime/inbox` | Drafts, discovered media, normalized transcripts |

The image does **not** bake `inbox/` or credentials. `BIOS_RUNTIME_DIR=/app/runtime`.

## Authentication

When `BIOS_REMOTE_INTERACTIVE=true` (compose default):

- HTTP Basic Auth using `BIOS_REVIEW_USERNAME` / `BIOS_REVIEW_PASSWORD`
- No default password; process refuses to start if either is missing
- `/healthz` stays unauthenticated
- Every other route, including Scanner and review, requires credentials

## Shortest VPS procedure

Requires a Linux VPS with Docker Engine + Compose plugin. IONOS **shared** hosting is not sufficient.

```bash
python scripts/export_demo_runtime.py --output demo-runtime
# copy repo + demo-runtime to the VPS
cp deploy/.env.example deploy/.env   # set username, password, BIOS_DEMO_SITE=review.example.com
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

DNS for `review.example.com` (do not hardcode a real customer domain in this repo):

- **A record** `review` → the VPS public IPv4. This is the normal path.
- **AAAA record** `review` → the VPS public IPv6 if the host has one.
- **CNAME** only if `review` should alias another hostname you already control (for example a load-balancer name). Do not CNAME at the Docker container.

IONOS: this stack needs a **Linux VPS / VPS-like host with Docker Engine + Compose**. IONOS shared web hosting (FTP/PHP/CGI, no long-running processes) cannot run FastAPI this way. Do not bend the app into shared-hosting CGI.

Then enable Caddy TLS:

```bash
BIOS_DEMO_SITE=review.example.com docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d
```

Open `https://review.example.com/work-queue`.

## Local proof without DNS

```bash
python scripts/export_demo_runtime.py --output demo-runtime
BIOS_REVIEW_USERNAME=demo BIOS_REVIEW_PASSWORD=demo-local \
  BIOS_DEMO_RUNTIME=../demo-runtime \
  docker compose --env-file /dev/stdin -f deploy/docker-compose.yml up --build -d
# then: curl -u demo:demo-local http://127.0.0.1:8000/work-queue
```
