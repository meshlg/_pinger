from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _notification_dir() -> Path:
    """Return a per-user notification directory under temp."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "default"
    safe_user = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in user)
    base_dir = Path(tempfile.gettempdir()) / f"pinger-{safe_user}"
    base_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return base_dir


def _notification_path() -> Path:
    return _notification_dir() / "notification.txt"


def _notify_running_instance(message: str) -> bool:
    """Notify the running instance by atomically writing a notification file."""
    try:
        notification_path = _notification_path()
        temp_path = notification_path.with_suffix(".tmp")

        # Write to a temp file first, then atomically replace destination.
        fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(message)
                f.flush()
                os.fsync(f.fileno())
        finally:
            if os.path.exists(temp_path):
                os.replace(temp_path, notification_path)

        return True
    except Exception:
        return False


def check_instance_notification() -> str | None:
    """Check for notification from another instance trying to start.

    Uses O_NOFOLLOW on POSIX to atomically refuse symlink targets,
    eliminating the TOCTOU window between exists()/is_symlink() and open().
    """
    try:
        notification_path = _notification_path()

        # Fast pre-check: skip obvious non-files before attempting open.
        if not notification_path.exists():
            return None

        # Read limit: protect against file-bomb (notification should be tiny).
        _READ_LIMIT = 4096

        try:
            # O_NOFOLLOW causes ELOOP/OSError if path is a symlink (POSIX).
            # This closes the TOCTOU window between is_symlink() and open().
            o_nofollow = getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(str(notification_path), os.O_RDONLY | o_nofollow)
        except (OSError, AttributeError):
            # O_NOFOLLOW not available (Windows) or path is a symlink (POSIX).
            # On Windows, symlink creation requires special privileges, so
            # a plain is_file() + is_symlink() guard is sufficient.
            if notification_path.is_symlink() or not notification_path.is_file():
                return None
            try:
                fd = os.open(str(notification_path), os.O_RDONLY)
            except OSError:
                return None

        try:
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read(_READ_LIMIT)
                message = content.strip()
        except Exception:
            return None
        finally:
            # Always attempt to remove the notification file so it is not
            # re-read on the next check cycle.
            notification_path.unlink(missing_ok=True)

        return message if message else None
    except Exception:
        return None
