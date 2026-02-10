"""Single instance enforcement for Pinger application.

Prevents multiple copies of the application from running simultaneously
using a cross-platform file lock mechanism.
"""
from __future__ import annotations

import os
import sys
import tempfile
import atexit
import logging
from pathlib import Path


def _check_stale_lock(lock_path: Path) -> bool:
    """Check if lock file is stale (process no longer running) and remove it.
    
    Returns:
        True if stale lock was removed, False otherwise.
    """
    if not lock_path.exists():
        return False
    
    try:
        # Try to read PID from lock file
        with open(lock_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return False
            pid = int(content)
        
        # Check if process exists using psutil
        try:
            import psutil
            if not psutil.pid_exists(pid):
                # Process is dead, remove stale lock
                lock_path.unlink(missing_ok=True)
                logging.info(f"Removed stale lock (PID {pid} not running)")
                return True
        except ImportError:
            # psutil not available, skip stale check
            pass
    except (ValueError, OSError, IOError):
        # Could not read PID, might be Windows lock or corrupted file
        pass
    
    return False


class SingleInstance:
    """Ensures only one instance of the application runs at a time.
    
    Uses a file lock on Windows and Unix-like systems.
    The lock file is automatically removed on clean exit.
    """

    def __init__(self, lock_name: str = "pinger.lock") -> None:
        self.lock_name = lock_name
        self.lock_path = Path(tempfile.gettempdir()) / lock_name
        self.lock_file: int | None = None
        self._acquired = False

    def _try_lock_windows(self) -> bool:
        """Try to acquire lock using Windows-specific APIs."""
        try:
            import msvcrt
            import ctypes
            from ctypes import wintypes

            # Create or open lock file
            kernel32 = ctypes.windll.kernel32
            GENERIC_READ = 0x80000000
            GENERIC_WRITE = 0x40000000
            CREATE_ALWAYS = 2
            FILE_ATTRIBUTE_NORMAL = 0x80

            handle = kernel32.CreateFileW(
                str(self.lock_path),
                GENERIC_READ | GENERIC_WRITE,
                0,  # No sharing
                None,
                CREATE_ALWAYS,
                FILE_ATTRIBUTE_NORMAL,
                None
            )

            if handle == -1:
                return False

            self.lock_file = handle
            return True
        except Exception:
            return False

    def _try_lock_unix(self) -> bool:
        """Try to acquire lock using Unix flock."""
        try:
            import fcntl

            # Open/create lock file
            fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT)

            # Try to acquire exclusive lock without blocking
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
                self.lock_file = fd
                # Write PID for debugging
                os.write(fd, str(os.getpid()).encode())
                os.fsync(fd)
                return True
            except (OSError, IOError):
                os.close(fd)
                return False
        except Exception:
            return False

    def acquire(self) -> bool:
        """Try to acquire the single instance lock.
        
        Returns:
            True if lock acquired, False if another instance is running.
        """
        # Check for stale lock before attempting to acquire (Unix only, Windows uses handle-based locking)
        if sys.platform != "win32":
            try:
                from config import ENABLE_STALE_LOCK_CHECK
                if ENABLE_STALE_LOCK_CHECK:
                    _check_stale_lock(self.lock_path)
            except Exception:
                pass  # Config not available yet, continue without stale check
        
        if sys.platform == "win32":
            self._acquired = self._try_lock_windows()
        else:
            self._acquired = self._try_lock_unix()

        if self._acquired:
            # Register cleanup on exit
            atexit.register(self.release)

        return self._acquired

    def release(self) -> None:
        """Release the lock and cleanup."""
        if not self._acquired:
            return

        try:
            if sys.platform == "win32":
                if self.lock_file is not None:
                    import ctypes
                    ctypes.windll.kernel32.CloseHandle(self.lock_file)
                    self.lock_file = None
            else:
                if self.lock_file is not None:
                    try:
                        import fcntl
                        fcntl.flock(self.lock_file, fcntl.LOCK_UN)
                        os.close(self.lock_file)
                    except (OSError, IOError):
                        pass
                    self.lock_file = None

            # Try to remove lock file (may fail if locked by other process)
            try:
                self.lock_path.unlink(missing_ok=True)
            except (OSError, IOError):
                pass

            self._acquired = False
        except Exception:
            pass  # Best effort cleanup

    def __enter__(self) -> SingleInstance:
        if not self.acquire():
            raise RuntimeError(f"Another instance is already running (lock: {self.lock_path})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def check_single_instance() -> SingleInstance | None:
    """Check if this is the only instance running.
    
    Returns:
        SingleInstance object if lock acquired, None otherwise.
    """
    locker = SingleInstance()
    if not locker.acquire():
        return None
    return locker
