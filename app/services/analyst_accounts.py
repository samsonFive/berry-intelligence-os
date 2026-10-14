"""Private SQLite accounts, compatible with the first live account release."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path


def account_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / "auth" / "users.sqlite3"


@contextmanager
def _database(inbox_dir: Path):
    path = account_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    db = sqlite3.connect(path, timeout=10)
    try:
        # Serialize additive migrations and retain every existing hash/timestamp.
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, first_login_at TEXT)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
            if "enabled" not in columns:
                db.execute("ALTER TABLE users ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
        yield db
    finally:
        db.close()


def load_accounts(inbox_dir: Path, *, strict: bool = False) -> dict:
    if not account_path(inbox_dir).exists():
        return {}
    try:
        with _database(inbox_dir) as db:
            return {username: {"enabled": bool(enabled), "first_login": first_login is None,
                               "first_login_at": first_login}
                    for username, first_login, enabled in db.execute("SELECT username, first_login_at, enabled FROM users")}
    except (OSError, sqlite3.DatabaseError):
        if strict:
            raise ValueError("Account store could not be read; existing accounts were preserved") from None
        return {}


def password_digest(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt),
                          n=16384, r=8, p=1, dklen=32).hex()


def create_account(inbox_dir: Path, username: str, password: str) -> None:
    username = username.strip()
    if not username or len(username) > 100 or any(ord(c) < 32 for c in username):
        raise ValueError("Invalid username")
    if not password or len(password.encode("utf-8")) > 1024:
        raise ValueError("Invalid password")
    from app.runtime_config import review_username
    if username == review_username():
        raise ValueError("Username already exists")
    salt = secrets.token_hex(16)
    encoded = f"scrypt${salt}${password_digest(password, salt)}"
    try:
        with _database(inbox_dir) as db:
            with db:
                db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, encoded))
    except sqlite3.IntegrityError:
        raise ValueError("Username already exists") from None
    except (OSError, sqlite3.DatabaseError):
        raise ValueError("Account store could not be read; existing accounts were preserved") from None


def account_credentials_match(inbox_dir: Path, username: str, password: str) -> bool:
    from app.runtime_config import review_username
    if username == review_username() or not account_path(inbox_dir).exists() or len(password.encode("utf-8")) > 1024:
        return False
    try:
        with _database(inbox_dir) as db:
            account = db.execute("SELECT password_hash, enabled FROM users WHERE username = ?", (username,)).fetchone()
        if not account or not account[0] or not account[1]:
            return False
        method, salt, digest = account[0].split("$")
        return method == "scrypt" and hmac.compare_digest(password_digest(password, salt), digest)
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        return False


def first_login_destination(inbox_dir: Path, username: str, destination: str) -> str:
    try:
        with _database(inbox_dir) as db:
            with db:
                db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
                updated = db.execute("UPDATE users SET first_login_at = ? WHERE username = ? AND first_login_at IS NULL",
                                     (datetime.now(UTC).isoformat(), username)).rowcount
    except (OSError, sqlite3.DatabaseError):
        raise ValueError("Account store could not be read; existing accounts were preserved") from None
    return "/guide" if updated else destination


def set_account_enabled(inbox_dir: Path, username: str, enabled: bool) -> None:
    with _database(inbox_dir) as db:
        with db:
            if not db.execute("UPDATE users SET enabled = ? WHERE username = ?", (int(enabled), username)).rowcount:
                raise ValueError("Account not found")
