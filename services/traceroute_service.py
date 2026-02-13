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
from typing import Callable, Optional, TypeVar

from config import TARGET_IP, TRACEROUTE_COOLDOWN, TRACEROUTE_MAX_HOPS, t

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from stats_repository import StatsRepository


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Convert datetime to timezone-aware UTC. If naive, assume local time and convert."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt

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
        
        try:
            if sys.platform == "win32":
                cmd = ["tracert", "-h", str(TRACEROUTE_MAX_HOPS), "-w", "1000", target]
                encoding = "oem"
            else:
                cmd = [
                    "traceroute",
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

    async def traceroute_worker(self, target: str) -> None:
        """Async worker to run traceroute and save to file."""
        loop = asyncio.get_running_loop()
        
        self._stats_repo.set_traceroute_running(True)
        
        self._stats_repo.add_alert(f"[i] {t('traceroute_starting')}", "info")
        logging.info(f"Starting traceroute to {target}")
        
        try:
            data = await loop.run_in_executor(
                self._executor,
                self.run_traceroute,
                target
            )
            
            traceroutes_dir = Path("traceroutes")
            traceroutes_dir.mkdir(exist_ok=True)
            filename = traceroutes_dir / f"traceroute_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(filename, "w", encoding="utf-8") as handle:
                handle.write(
                    f"Traceroute to {target}\nTime: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}\n"
                )
                handle.write("=" * 70 + "\n")
                handle.write(data)
            
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
        if self._stats_repo.is_traceroute_running():
            return False
        
        last = self._stats_repo.get_last_traceroute_time()
        last = _ensure_utc(last)
        if last and (datetime.now(timezone.utc) - last).total_seconds() < TRACEROUTE_COOLDOWN:
            return False
        
        asyncio.create_task(self.traceroute_worker(target))
        return True

    def is_available(self) -> bool:
        """Check if traceroute is available."""
        return self._check_traceroute_available()

