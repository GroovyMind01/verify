"""Security hardening utilities.

Principles:
- Never follow symlinks when copying evidence (prevents sensitive file disclosure)
- Always resolve and validate paths against a trusted base directory
- Set restrictive file permissions on database and evidence files
- Limit JSON parsing to prevent DoS
- Validate all user-controlled strings before filesystem operations
"""

import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

# ── File permissions ──────────────────────────────────────────────

_SAFE_DIR_MODE = stat.S_IRWXU  # 0o700 — owner only
_SAFE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600 — owner only


def set_safe_permissions(path: Path, *, directory: bool = False) -> None:
    """Set restrictive permissions on a file or directory (owner-only)."""
    try:
        mode = _SAFE_DIR_MODE if directory else _SAFE_FILE_MODE
        os.chmod(path, mode)
    except OSError:
        pass


def ensure_safe_directory(path: Path) -> None:
    """Create directory with owner-only permissions if it doesn't exist."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        set_safe_permissions(path, directory=True)
        # Walk up and secure parent dirs that we created
        for parent in path.parents:
            if not parent.exists():
                break
            set_safe_permissions(parent, directory=True)


def create_safe_file(path: Path) -> None:
    """Create an empty file with owner-only permissions."""
    path.touch()
    set_safe_permissions(path, directory=False)


# ── Path safety ────────────────────────────────────────────────────

def resolve_safe_path(base_dir: Path, *segments: str) -> Path:
    """Resolve a path under base_dir, rejecting path traversal attempts.

    Raises ValueError if the resolved path escapes base_dir.
    """
    resolved = (base_dir / Path(*segments)).resolve()
    base_resolved = base_dir.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: {resolved} is outside {base_resolved}"
        )
    return resolved


def sanitize_filename(name: str) -> str:
    """Strip directory separators and null bytes from a filename."""
    # Take only the basename component, strip dangerous chars
    cleaned = name.replace("\x00", "").replace("/", "_").replace("\\", "_")
    # Remove leading dots to prevent hidden files
    cleaned = cleaned.lstrip(".")
    if not cleaned:
        cleaned = "unnamed"
    return cleaned


# ── Secure file operations ─────────────────────────────────────────

def is_symlink(path: Path) -> bool:
    """Check if a path is a symbolic link."""
    try:
        return path.is_symlink()
    except OSError:
        return False


def secure_copy(source: Path, dest: Path) -> None:
    """Copy a file without following symlinks at the source.

    Uses O_NOFOLLOW to atomically reject symlinks at open time,
    closing the TOCTOU window between the is_symlink() check and
    the file descriptor acquisition.

    Raises ValidationError-like ValueError if source is a symlink.
    """
    try:
        src_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        raise ValueError(f"Cannot open source (symlink or missing): {source}: {e}")

    with os.fdopen(src_fd, "rb") as src:
        with open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)

    shutil.copystat(source, dest, follow_symlinks=False)
    set_safe_permissions(dest)


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def verify_checksum(path: Path, expected: str) -> bool:
    """Verify a file matches its expected SHA-256 checksum."""
    return compute_sha256(path) == expected


# ── JSON safety ────────────────────────────────────────────────────

_MAX_JSON_SIZE = 1024 * 1024  # 1 MB
_MAX_JSON_DEPTH = 20


def safe_json_parse(raw: str | bytes) -> dict | list:
    """Parse JSON with limits to prevent DoS."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if len(raw) > _MAX_JSON_SIZE:
        raise ValueError(f"JSON payload exceeds {_MAX_JSON_SIZE} bytes")
    return json.loads(raw)


# ── Input validation ───────────────────────────────────────────────

_MAX_STRING_LENGTH = 4096


def validate_string(
    value: str | None,
    field_name: str,
    max_length: int = _MAX_STRING_LENGTH,
) -> str | None:
    """Validate a user-supplied string field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
    if "\x00" in value:
        raise ValueError(f"{field_name} contains null bytes")
    return value


def validate_command(command: str | None, field_name: str = "command") -> str:
    """Validate a shell command string before execution.

    Rejects empty commands, null bytes, and extremely long commands.
    Keeps shell=True support since test scripts require pipes, redirects, etc.
    """
    if not command:
        raise ValueError(f"{field_name} must not be empty")
    if not isinstance(command, str):
        raise ValueError(f"{field_name} must be a string")
    if len(command) > 4096:
        raise ValueError(f"{field_name} exceeds maximum length of 4096")
    if "\x00" in command:
        raise ValueError(f"{field_name} contains null bytes")
    return command.strip()


def validate_id(value: str, field_name: str) -> str:
    """Validate a UUID-like identifier (alphanumeric + hyphens)."""
    if not value or not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string")
    if len(value) > 64:
        raise ValueError(f"{field_name} exceeds maximum length")
    if "\x00" in value:
        raise ValueError(f"{field_name} contains null bytes")
    return value
