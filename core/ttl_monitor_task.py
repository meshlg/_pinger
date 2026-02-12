"""TTL monitoring background task."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from typing import Any

from config import ENABLE_TTL_MONITORING, TARGET_IP, TTL_CHECK_INTERVAL
from core.background_task import BackgroundTask
from services import PingService


class TTLMonitorTask(BackgroundTask):
    """Periodically extract TTL and estimate hop count."""

    def __init__(self, *, ping_service: PingService, **kw) -> None:
        super().__init__(
            name="TTLMonitor",
            interval=TTL_CHECK_INTERVAL,
            enabled=ENABLE_TTL_MONITORING,
            **kw,
        )
        self.ping_service = ping_service

    async def execute(self) -> None:
        ttl, hops = await self.run_blocking(self._extract_ttl, TARGET_IP)
        self.stats_repo.update_ttl(ttl, hops)

    def _extract_ttl(self, host: str) -> tuple[int | None, int | None]:
        """Extract TTL from ping — using PingService internals."""
        try:
            ping_cmd = shutil.which("ping")
            if not ping_cmd:
                return None, None

            is_ipv6 = self.ping_service._detect_ipv6(host)

            if sys.platform == "win32":
                cmd = [ping_cmd, "-n", "1", "-w", "1000", host]
                encoding = "oem"
            else:
                if is_ipv6:
                    cmd = [ping_cmd, "-6", "-c", "1", host]
                else:
                    cmd = [ping_cmd, "-c", "1", host]
                encoding = "utf-8"

            # Use creationflags on Windows to prevent orphan processes
            kwargs: dict[str, Any] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                encoding=encoding,
                errors="replace",
                **kwargs,
            )

            ttl_match = re.search(r"TTL[=:\s]+(\d+)", result.stdout, re.IGNORECASE)
            if ttl_match:
                ttl = int(ttl_match.group(1))
                common_initial_ttl_values = [64, 128, 255]
                estimated_hops = None
                for initial_ttl in common_initial_ttl_values:
                    if ttl <= initial_ttl:
                        estimated_hops = initial_ttl - ttl
                        break
                return ttl, estimated_hops
        except Exception as exc:
            logging.error(f"TTL extraction failed: {exc}")
        return None, None
