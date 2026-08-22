"""Runtime directory and remote-demo authentication configuration.

Local development keeps today's layout: `data/` and `inbox/` under the repo
root. Remote interactive demo sets `BIOS_RUNTIME_DIR` (and optionally
`BIOS_DATA_DIR` / `BIOS_INBOX_DIR`) so the same application code runs against
a bound, persistent runtime tree.

`BIOS_REMOTE_INTERACTIVE=true` enables application-session authentication
driven by `BIOS_REVIEW_USERNAME` / `BIOS_REVIEW_PASSWORD` and signed with
`BIOS_SESSION_SECRET`. There is no default password. Missing credentials or
signing secret fail closed at startup. HTTP Basic Auth is opt-in via
`BIOS_BASIC_AUTH` and is off by default.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TRUE_VALUES = {"1", "true", "yes", "on"}

PUBLIC_WHEN_REMOTE = {"/healthz", "/login", "/logout"}
PUBLIC_PREFIXES = ("/healthz", "/static/")

WEAK_SESSION_SECRETS = {
    "",
    "replace-me",
    "replace-me-with-openssl-rand-hex-32",
    "changeme",
    "secret",
}

MIN_SESSION_SECRET_LENGTH = 32


class RemoteInteractiveMisconfigured(RuntimeError):
    """Remote interactive mode is on but required secrets are missing."""


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUE_VALUES


def env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def remote_interactive_enabled() -> bool:
    return env_flag("BIOS_REMOTE_INTERACTIVE")


def basic_auth_enabled() -> bool:
    """Emergency browser prompt. Off unless explicitly enabled."""

    return env_flag("BIOS_BASIC_AUTH")


def review_username() -> str:
    return os.environ.get("BIOS_REVIEW_USERNAME", "").strip()


def review_password() -> str:
    # Keep the raw value (including leading/trailing spaces) so operators can
    # choose such a password. Only username is stripped.
    return os.environ.get("BIOS_REVIEW_PASSWORD", "")


def session_secret() -> str:
    return os.environ.get("BIOS_SESSION_SECRET", "")


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
    secret = session_secret()
    if secret in WEAK_SESSION_SECRETS or len(secret) < MIN_SESSION_SECRET_LENGTH:
        raise RemoteInteractiveMisconfigured(
            "BIOS_REMOTE_INTERACTIVE is enabled but BIOS_SESSION_SECRET is "
            "missing or too weak. Refusing to start."
        )
    if secrets.compare_digest(secret, review_password()):
        raise RemoteInteractiveMisconfigured(
            "BIOS_SESSION_SECRET must not be the same value as "
            "BIOS_REVIEW_PASSWORD. Refusing to start."
        )


def path_is_protected(path: str, method: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in PUBLIC_WHEN_REMOTE or path.startswith(PUBLIC_PREFIXES):
        return False
    if path == "/static":
        return False
    if not remote_interactive_enabled():
        return False
    # The remote interactive host is the private review instance. GitHub Pages
    # remains the public trusted snapshot. Protect the whole app except the
    # login surface and healthz.
    return True


def credentials_match(username: str, password: str) -> bool:
    expected_user = review_username()
    expected_password = review_password()
    if not expected_user or not expected_password:
        return False
    user_ok = secrets.compare_digest(username, expected_user)
    password_ok = secrets.compare_digest(password, expected_password)
    return user_ok and password_ok
