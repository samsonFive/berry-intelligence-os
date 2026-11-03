"""Private, authenticated derived bytes; reads never create or repair files.

Only an explicit preparation command may call ``write``. These disposable
artifacts are not source records or review decisions. Callers must bind every
current input and the executing code/schema version into ModelKey, then use a
class-denying decoder after authentication. Unsupported platforms simply miss.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import struct
import uuid

_MAGIC = b"BIOSDM01"
_PREFIX = struct.Struct(">8sHI32s")
_MAX_HEADER = 1024
MAX_PAYLOAD = 16_000_000
MAX_BYTES = 128_000_000
MAX_ENTRIES = 32
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_FILE = re.compile(r"[0-9a-f]{64}\.snapshot\Z")
_LEAF = "derived-read-models-v1"


@dataclass(frozen=True)
class ModelKey:
    namespace: str
    input_digest: str
    code_digest: str
    day: str

    def __post_init__(self):
        if any(type(value) is not str or not _HEX.fullmatch(value)
               for value in (self.namespace, self.input_digest, self.code_digest)):
            raise ValueError("Invalid derived-model identity")
        if type(self.day) is not str or date.fromisoformat(self.day).isoformat() != self.day:
            raise ValueError("Invalid derived-model day")


@dataclass(frozen=True)
class DerivedModelStore:
    """An explicit private inbox root and a purpose-specific signing key.

    No environment or application-session state is read here. Configuration,
    key derivation, private-route scoping and an explicit writer belong to the
    integration layer. POSIX descriptor-relative operations prevent symlink
    replacement from redirecting an artifact operation outside this leaf.
    """
    inbox_dir: Path
    context_digest: str
    signing_key: bytes = field(repr=False)
    max_bytes: int = MAX_BYTES
    max_entries: int = MAX_ENTRIES

    def __post_init__(self):
        if type(self.signing_key) is not bytes or len(self.signing_key) < 32:
            raise ValueError("A private derived-model signing key is required")
        if type(self.context_digest) is not str or not _HEX.fullmatch(self.context_digest):
            raise ValueError("Invalid derived-model context")
        if (type(self.max_bytes) is not int or type(self.max_entries) is not int
                or not 0 < self.max_bytes <= MAX_BYTES or not 0 < self.max_entries <= MAX_ENTRIES):
            raise ValueError("Invalid derived-model budget")
        inbox = Path(self.inbox_dir)
        if not inbox.is_absolute() or ".." in inbox.parts:
            raise ValueError("An explicit absolute private inbox is required")
        object.__setattr__(self, "inbox_dir", inbox)

    def _header(self, key):
        return json.dumps({**key.__dict__, "context_digest": self.context_digest},
                          sort_keys=True, separators=(",", ":")).encode("ascii")

    @staticmethod
    def _name(header):
        return hashlib.sha256(header).hexdigest() + ".snapshot"

    @staticmethod
    def _private(info, *, directory=False):
        kind = stat.S_ISDIR if directory else stat.S_ISREG
        return (kind(info.st_mode) and info.st_uid == os.geteuid()
                and not info.st_mode & (stat.S_IRWXG | stat.S_IRWXO))

    @contextmanager
    def _directory(self, *, create=False):
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
            yield None
            return
        root_fd = None
        parent_fd = None
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            # Never create an inbox or its parents on a read or write.
            # Open every ancestor without following symlinks, then keep all
            # artifact operations relative to the verified leaf descriptor.
            parent_fd = os.open(self.inbox_dir.anchor, flags)
            for part in self.inbox_dir.parts[1:]:
                child_fd = os.open(part, flags, dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = child_fd
            if create:
                try:
                    os.mkdir(_LEAF, mode=0o700, dir_fd=parent_fd)
                except FileExistsError:
                    pass
            root_fd = os.open(_LEAF, flags, dir_fd=parent_fd)
            if not self._private(os.fstat(root_fd), directory=True):
                raise OSError("Derived-model directory is not private")
        except OSError:
            if root_fd is not None:
                os.close(root_fd)
                root_fd = None
        finally:
            if parent_fd is not None:
                os.close(parent_fd)
        try:
            yield root_fd
        finally:
            if root_fd is not None:
                os.close(root_fd)

    def _read(self, directory, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not self._private(info) or not _PREFIX.size < info.st_size <= _PREFIX.size + _MAX_HEADER + MAX_PAYLOAD:
                return None
            prefix = stream.read(_PREFIX.size)
            if len(prefix) != _PREFIX.size:
                return None
            magic, header_size, payload_size, signature = _PREFIX.unpack(prefix)
            if magic != _MAGIC or not 0 < header_size <= _MAX_HEADER or not 0 < payload_size <= MAX_PAYLOAD:
                return None
            if info.st_size != _PREFIX.size + header_size + payload_size:
                return None
            header = stream.read(header_size)
            payload = stream.read(payload_size)
            if len(payload) != payload_size or stream.read(1):
                return None
        expected = hmac.digest(self.signing_key, _MAGIC + header + b"\0" + payload, "sha256")
        if not hmac.compare_digest(signature, expected) or name != self._name(header):
            return None
        return header, payload, info

    def load(self, key: ModelKey) -> bytes | None:
        """Authenticate only this complete input/version/day/context; no writes."""
        header = self._header(key)
        with self._directory() as directory:
            if directory is None:
                return None
            try:
                row = self._read(directory, self._name(header))
                return row[1] if row is not None and row[0] == header else None
            except (OSError, ValueError, struct.error):
                return None

    def _owned_header(self, header):
        try:
            metadata = json.loads(header)
            if metadata.pop("context_digest") != self.context_digest:
                return False
            key = ModelKey(**metadata)
            return self._header(key) == header
        except (TypeError, ValueError, KeyError, AttributeError):
            return False

    def _reserve(self, directory, name, size):
        # Unknown files count against the budget but are never removed. Only
        # authenticated, regular files in this exact private leaf can expire.
        total = count = 0
        expendable = []
        with os.scandir(directory) as entries:
            for scanned, entry in enumerate(entries, start=1):
                if scanned > MAX_ENTRIES * 4:
                    return False
                if entry.name == ".writer.lock":
                    continue
                info = entry.stat(follow_symlinks=False)
                row = None
                if _FILE.fullmatch(entry.name):
                    try:
                        row = self._read(directory, entry.name)
                    except OSError:
                        pass
                owned = row is not None and self._owned_header(row[0])
                if entry.name == name:
                    if not owned:
                        return False
                    continue
                count += 1
                total += info.st_size
                if owned:
                    expendable.append((info.st_mtime_ns, entry.name, info.st_size))
        for _, old_name, old_size in sorted(expendable):
            if count + 1 <= self.max_entries and total + size <= self.max_bytes:
                break
            os.unlink(old_name, dir_fd=directory)
            count -= 1
            total -= old_size
        return count + 1 <= self.max_entries and total + size <= self.max_bytes

    def write(self, key: ModelKey, payload: bytes) -> bool:
        """Explicit writer only; bounded, nonblocking and atomically published."""
        if type(payload) is not bytes or not 0 < len(payload) <= MAX_PAYLOAD:
            return False
        header = self._header(key)
        signature = hmac.digest(self.signing_key, _MAGIC + header + b"\0" + payload, "sha256")
        prefix = _PREFIX.pack(_MAGIC, len(header), len(payload), signature)
        name = self._name(header)
        with self._directory(create=True) as directory:
            if directory is None:
                return False
            lock_fd = None
            temporary = None
            try:
                import fcntl
                lock_fd = os.open(".writer.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                  0o600, dir_fd=directory)
                if not self._private(os.fstat(lock_fd)):
                    return False
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if not self._reserve(directory, name, len(prefix) + len(header) + len(payload)):
                    return False
                temporary = "." + uuid.uuid4().hex + ".tmp"
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(prefix)
                    stream.write(header)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
                temporary = None
                os.fsync(directory)
                return True
            except (OSError, ValueError, struct.error):
                return False
            finally:
                if temporary is not None:
                    try:
                        os.unlink(temporary, dir_fd=directory)
                    except OSError:
                        pass
                if lock_fd is not None:
                    os.close(lock_fd)
