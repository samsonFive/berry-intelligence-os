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
Rebuild/redeploy replaces the image but not either bind-mounted directory.
Operational state, analyst queue state, Signal candidate audit, and transcripts
all live below the mounted inbox. See
`docs/v2/COLLECTION-RUNTIME-DATA-INTEGRITY.md` for backup/restore procedure.

## Authentication

When `BIOS_REMOTE_INTERACTIVE=true` (compose default):

- Application login at `GET /login` using `BIOS_REVIEW_USERNAME` / `BIOS_REVIEW_PASSWORD`
- Signed HttpOnly session cookie using `BIOS_SESSION_SECRET` (must not be the review password)
- No default password or signing secret; process refuses to start if any required secret is missing
- Unauthenticated visits to Scanner, review, and other app routes redirect to `/login?next=…`
- `/healthz` and `/static/*` stay unauthenticated
- HTTP Basic Auth is **off by default**. Enable only with `BIOS_BASIC_AUTH=true` as an emergency fallback. Do not put Basic Auth in front of `/login`.

Generate the session secret on the host. Do not paste it into chat:

```bash
# append to an existing deploy/.env (value is not printed)
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path("/opt/berry-intelligence-os/deploy/.env")
text = path.read_text()
if "BIOS_SESSION_SECRET=" not in text:
    path.write_text(text.rstrip() + "\nBIOS_SESSION_SECRET=" + secrets.token_hex(32) + "\n")
    path.chmod(0o600)
print("BIOS_SESSION_SECRET is present in", path)
PY
```

## Shortest VPS procedure

Requires a Linux VPS with Docker Engine + Compose plugin. IONOS **shared** hosting is not sufficient.

```bash
python scripts/export_demo_runtime.py --output demo-runtime
# copy repo + demo-runtime to the VPS
cp deploy/.env.example deploy/.env   # set username, password, session secret, BIOS_DEMO_SITE=review.example.com
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

DNS for `review.example.com` (do not hardcode a real customer domain in this repo):

- **A record** `review` → the VPS public IPv4. This is the normal path.
- **AAAA record** `review` → the VPS public IPv6 if the host has one.
- **CNAME** only if `review` should alias another hostname you already control (for example a load-balancer name). Do not CNAME at the Docker container.

IONOS: this stack needs a **Linux VPS / VPS-like host with Docker Engine + Compose**. IONOS shared web hosting (FTP/PHP/CGI, no long-running processes) cannot run FastAPI this way. Do not bend the app into shared-hosting CGI.

Then enable Caddy TLS. The app container is **loopback-only** (`127.0.0.1:8000`). Do not publish port 8000 on `0.0.0.0`.

```bash
BIOS_DEMO_SITE=review.example.com docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile tls up -d --build
```

Open `https://review.example.com/login`, then Scanner at `/work-queue`.

## Local proof without DNS

```bash
python scripts/export_demo_runtime.py --output demo-runtime
BIOS_REVIEW_USERNAME=demo BIOS_REVIEW_PASSWORD=demo-local \
  BIOS_SESSION_SECRET="$(openssl rand -hex 32)" \
  BIOS_DEMO_RUNTIME=../demo-runtime \
  docker compose --env-file /dev/stdin -f deploy/docker-compose.yml up --build -d
# then: curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:8000/work-queue
# expected: 302 to /login?next=/work-queue
```

A Linux VPS bootstrap lives in `scripts/vps_bootstrap.sh`. It binds the app to loopback and puts Caddy on 80/443.
