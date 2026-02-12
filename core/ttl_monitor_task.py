"""TTL monitoring background task."""

from __future__ import annotations

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
        ttl, hops = await self.run_blocking(self.ping_service.extract_ttl, TARGET_IP)
        self.stats_repo.update_ttl(ttl, hops)
