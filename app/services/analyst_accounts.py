"""Additional analyst logins in the private runtime; workspace data stays shared."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
import secrets
from pathlib import Path

from app.services.analyst_state_io import atomic_json, serialized_write


def account_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / "auth" / "analyst_accounts.json"


def load_accounts(inbox_dir: Path, *, strict: bool = False) -> dict:
    try:
        payload = json.loads(account_path(inbox_dir).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid account store")
        return payload
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        if strict:
            raise ValueError("Account store could not be read; existing accounts were preserved") from None
        return {}


def password_digest(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                          n=16384, r=8, p=1, dklen=32).hex()


@serialized_write
def create_account(inbox_dir: Path, username: str, password: str) -> None:
    username = username.strip()
    if not username or len(username) > 100 or any(ord(c) < 32 for c in username):
        raise ValueError("Invalid username")
    if not password or len(password.encode("utf-8")) > 1024:
        raise ValueError("Invalid password")
    from app.runtime_config import review_username
    accounts = load_accounts(inbox_dir, strict=True)
    if username == review_username() or username in accounts:
        raise ValueError("Username already exists")
    salt = secrets.token_hex(16)
    accounts[username] = {"salt": salt, "password_hash": password_digest(password, salt),
                          "enabled": True, "first_login": True,
                          "created_at": datetime.now(UTC).isoformat()}
    atomic_json(account_path(inbox_dir), accounts)
    # This file never belongs in source control or public/static output.
    account_path(inbox_dir).chmod(0o600)


def account_credentials_match(inbox_dir: Path, username: str, password: str) -> bool:
    account = load_accounts(inbox_dir).get(username)
    if not isinstance(account, dict) or account.get("enabled") is not True:
        return False
    if len(password.encode("utf-8")) > 1024:
        return False
    try:
        return hmac.compare_digest(password_digest(password, account["salt"]), account["password_hash"])
    except (KeyError, TypeError, ValueError):
        return False


@serialized_write
def first_login_destination(inbox_dir: Path, username: str, destination: str) -> str:
    accounts = load_accounts(inbox_dir, strict=True)
    account = accounts.get(username)
    if not isinstance(account, dict) or not account.get("first_login"):
        return destination
    account["first_login"] = False
    account["first_login_at"] = datetime.now(UTC).isoformat()
    atomic_json(account_path(inbox_dir), accounts)
    return "/guide"
