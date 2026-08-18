"""Runtime directory and remote-demo authentication configuration.

Local development keeps today's layout: `data/` and `inbox/` under the repo
root. Remote interactive demo sets `BIOS_RUNTIME_DIR` (and optionally
`BIOS_DATA_DIR` / `BIOS_INBOX_DIR`) so the same application code runs against
a bound, persistent runtime tree.

`BIOS_REMOTE_INTERACTIVE=true` enables HTTP Basic Auth driven only by
`BIOS_REVIEW_USERNAME` / `BIOS_REVIEW_PASSWORD`. There is no default
password. Missing credentials fail closed at startup.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

REPO_ROOT = Path(__file__).resolve().parents[1]

TRUE_VALUES = {"1", "true", "yes", "on"}

INTERACTIVE_PREFIXES = (
    "/review",
    "/intake",
    "/work-queue",
)

PUBLIC_WHEN_REMOTE = {"/healthz"}


class RemoteInteractiveMisconfigured(RuntimeError):
    """Remote interactive mode is on but credentials are missing."""


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def remote_interactive_enabled() -> bool:
    return env_flag("BIOS_REMOTE_INTERACTIVE")


def review_username() -> str:
    return os.environ.get("BIOS_REVIEW_USERNAME", "").strip()


def review_password() -> str:
    # Keep the raw value (including leading/trailing spaces) so operators can
    # choose such a password. Only username is stripped.
    return os.environ.get("BIOS_REVIEW_PASSWORD", "")


def resolve_data_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    explicit = env_path("BIOS_DATA_DIR")
    if explicit is not None:
        return explicit
    runtime = env_path("BIOS_RUNTIME_DIR")
    if runtime is not None:
        return runtime / "data"
    return root / "data"


def resolve_inbox_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    explicit = env_path("BIOS_INBOX_DIR")
    if explicit is not None:
        return explicit
    runtime = env_path("BIOS_RUNTIME_DIR")
    if runtime is not None:
        return runtime / "inbox"
    return root / "inbox"


def validate_remote_interactive_config() -> None:
    if not remote_interactive_enabled():
        return
    if not review_username() or not review_password():
        raise RemoteInteractiveMisconfigured(
            "BIOS_REMOTE_INTERACTIVE is enabled but BIOS_REVIEW_USERNAME and "
            "BIOS_REVIEW_PASSWORD are not both set. Refusing to start."
        )


def path_is_protected(path: str, method: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in PUBLIC_WHEN_REMOTE or path.startswith("/healthz"):
        return False
    if not remote_interactive_enabled():
        return False
    # The remote interactive host is the private review instance. GitHub Pages
    # remains the public trusted snapshot. Protect the whole app except healthz.
    return True


def _unauthorized() -> Response:
    return Response(
        content="Authentication required",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Berry Intelligence OS"'},
        media_type="text/plain",
    )


def credentials_match(username: str, password: str) -> bool:
    expected_user = review_username()
    expected_password = review_password()
    if not expected_user or not expected_password:
        return False
    user_ok = secrets.compare_digest(username, expected_user)
    password_ok = secrets.compare_digest(password, expected_password)
    return user_ok and password_ok


async def remote_auth_middleware(request: Request, call_next):
    if not path_is_protected(request.url.path, request.method):
        return await call_next(request)
    try:
        validate_remote_interactive_config()
    except RemoteInteractiveMisconfigured:
        return Response(
            content="Remote interactive mode is misconfigured",
            status_code=503,
            media_type="text/plain",
        )
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth is None or not auth.lower().startswith("basic "):
        return _unauthorized()
    try:
        import base64

        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, OSError):
        return _unauthorized()
    if not credentials_match(username, password):
        return _unauthorized()
    return await call_next(request)
