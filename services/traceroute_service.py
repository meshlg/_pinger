from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar
from config import TARGET_IP, TRACEROUTE_COOLDOWN, TRACEROUTE_MAX_HOPS, MAX_TRACEROUTE_FILES, ensure_utc, t
from infrastructure import get_process_manager

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from stats_repository import StatsRepository


try:
    from prometheus_client import Counter  # type: ignore
    METRICS_AVAILABLE = True
    TRACEROUTES_SAVED = Counter("pinger_traceroutes_saved_total", "Traceroutes saved due to route change")
except Exception:
    METRICS_AVAILABLE = False

T = TypeVar('T')


class TracerouteService:
    """Service for traceroute operations."""

    def __init__(
        self,
        stats_repo: StatsRepository,
        executor: ThreadPoolExecutor,
    ) -> None:
        self._stats_repo = stats_repo
        self._executor = executor
        self._traceroute_available: bool | None = None
        self.process_manager = get_process_manager()
        self._trigger_lock = threading.Lock()

    def _check_traceroute_available(self) -> bool:
        """Check if traceroute/tracert command is available."""
        if self._traceroute_available is not None:
            return self._traceroute_available
        self._traceroute_available = bool(
            shutil.which("traceroute") or shutil.which("tracert")
        )
        return self._traceroute_available

    def run_traceroute(self, target: str) -> str:
        """Run traceroute command and return output."""
        if not self._check_traceroute_available():
            return t("traceroute_not_found")
            
        # Security check: prevent argument injection
        if target.strip().startswith("-"):
            return "Security error: Invalid target (starts with hyphen)"
        
        try:
            if sys.platform == "win32":
                # Windows: -d (do not resolve addresses)
                cmd = ["tracert", "-d", "-h", str(TRACEROUTE_MAX_HOPS), "-w", "1000", target]
                encoding = "oem"
            else:
                cmd = [
                    "traceroute",
                    "-n", # Linux: -n (do not resolve addresses)
                    "-m",
                    str(TRACEROUTE_MAX_HOPS),
                    "-w",
                    "1",
                    target,
                ]
                encoding = "utf-8"
            
            # Use creationflags on Windows to prevent orphan processes
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding=encoding,
                errors="replace",
                **kwargs,
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return t("traceroute_timeout")
        except Exception as exc:
            return f"Traceroute error: {exc}"

    async def run_traceroute_async(self, target: str) -> str:
        """Run traceroute command asynchronously."""
        if not self._check_traceroute_available():
            return t("traceroute_not_found")
            
        # Security check: prevent argument injection
        if target.strip().startswith("-"):
            return "Security error: Invalid target (starts with hyphen)"
        
        try:
            if sys.platform == "win32":
                # Windows: -d (do not resolve addresses)
                cmd = ["tracert", "-d", "-h", str(TRACEROUTE_MAX_HOPS), "-w", "1000", target]
                encoding = "oem"
            else:
                cmd = [
                    "traceroute",
                    "-n", # Linux: -n (do not resolve addresses)
                    "-m",
                    str(TRACEROUTE_MAX_HOPS),
                    "-w",
                    "1",
                    target,
                ]
                encoding = "utf-8"
            
            # Use creationflags on Windows to prevent orphan processes
            kwargs: dict[str, Any] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            
            stdout, _, _ = await self.process_manager.run_command(
                cmd,
                timeout=30.0,
                encoding=encoding,
                errors="replace",
                **kwargs
            )
            return str(stdout)
        except asyncio.TimeoutError:
            return t("traceroute_timeout")
        except Exception as exc:
            return f"Traceroute error: {exc}"

    async def traceroute_worker(self, target: str) -> None:
        """Async worker to run traceroute and save to file."""
        loop = asyncio.get_running_loop()

        # Capture start time *before* the traceroute runs so that both the
        # filename and the file header use the same consistent timestamp.
        # Previously the timestamp was sampled twice: once for the filename
        # and once inside _write_and_cleanup(), creating a mismatch when the
        # traceroute took several minutes to complete.
        start_time = datetime.now(timezone.utc)

        self._stats_repo.add_alert(f"[i] {t('traceroute_starting')}", "info")
        logging.info(f"Starting traceroute to {target}")

        try:
            data = await self.run_traceroute_async(target)

            end_time = datetime.now(timezone.utc)

            traceroutes_dir = Path("traceroutes")
            traceroutes_dir.mkdir(exist_ok=True)
            filename = traceroutes_dir / f"traceroute_{start_time.strftime('%Y%m%d_%H%M%S')}.txt"

            # File I/O in executor to avoid blocking event loop
            def _write_and_cleanup():
                # Write new file
                with open(filename, "w", encoding="utf-8") as handle:
                    handle.write(f"Traceroute to {target}\n")
                    handle.write(f"Started:  {start_time:%Y-%m-%d %H:%M:%S} UTC\n")
                    handle.write(f"Finished: {end_time:%Y-%m-%d %H:%M:%S} UTC\n")
                    handle.write("=" * 70 + "\n")
                    handle.write(data)
                
                # Cleanup old files
                try:
                    files = list(traceroutes_dir.glob("traceroute_*.txt"))
                    if len(files) > MAX_TRACEROUTE_FILES:
                        # Sort by modification time (oldest first)
                        files.sort(key=lambda p: p.stat().st_mtime)
                        # Remove excess
                        to_remove = files[:-MAX_TRACEROUTE_FILES]
                        for f in to_remove:
                            try:
                                f.unlink()
                            except Exception:
                                pass
                except Exception as e:
                    logging.error(f"Failed to cleanup traceroutes: {e}")

            await loop.run_in_executor(None, _write_and_cleanup)
            
            self._stats_repo.add_alert(f"[+] {t('traceroute_saved').format(file=filename)}", "success")
            logging.info(f"Traceroute saved: {filename}")
            
            if METRICS_AVAILABLE:
                TRACEROUTES_SAVED.inc()
                
        except Exception as exc:
            self._stats_repo.add_alert(f"[!] {t('traceroute_save_failed')}", "warning")
            logging.error(f"Failed save traceroute: {exc}")
        finally:
            self._stats_repo.set_traceroute_running(False)

    def trigger_traceroute(self, target: str) -> bool:
        """Trigger traceroute if not running and cooldown passed."""
        with self._trigger_lock:
            if self._stats_repo.is_traceroute_running():
                return False

            last = self._stats_repo.get_last_traceroute_time()
            last = ensure_utc(last)
            if last and (datetime.now(timezone.utc) - last).total_seconds() < TRACEROUTE_COOLDOWN:
                return False

            # Reserve single-flight slot atomically before scheduling task.
            self._stats_repo.set_traceroute_running(True)
            try:
                asyncio.create_task(self.traceroute_worker(target))
            except Exception:
                self._stats_repo.set_traceroute_running(False)
                raise
            return True

    def is_available(self) -> bool:
        """Check if traceroute is available."""
        return self._check_traceroute_available()

