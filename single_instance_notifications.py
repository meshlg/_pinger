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
    """Check for notification from another instance trying to start."""
    try:
        notification_path = _notification_path()
        if not notification_path.exists() or notification_path.is_symlink():
            return None

        # Refuse non-regular files to reduce symlink/hardlink abuse surface.
        st = notification_path.stat()
        if not os.path.isfile(notification_path):
            return None

        with open(notification_path, "r", encoding="utf-8") as f:
            message = f.read().strip()

        notification_path.unlink(missing_ok=True)
        return message if message else None
    except Exception:
        return None
