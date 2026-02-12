"""Hop monitoring background task."""

from __future__ import annotations

import time as _time

from config import (
    ENABLE_HOP_MONITORING,
    HOP_PING_INTERVAL,
    HOP_REDISCOVER_INTERVAL,
    TARGET_IP,
)
from core.background_task import BackgroundTask
from services import HopMonitorService


class HopMonitorTask(BackgroundTask):
    """Discover route hops and ping them periodically."""

    def __init__(self, *, hop_monitor_service: HopMonitorService, **kw) -> None:
        super().__init__(
            name="HopMonitor",
            interval=HOP_PING_INTERVAL,
            enabled=ENABLE_HOP_MONITORING,
            **kw,
        )
        self.hop_monitor_service = hop_monitor_service
        self._last_discovery: float = 0.0

    async def setup(self) -> None:
        """Initial hop discovery (streaming — hops appear one by one)."""

        def _on_hop_discovered(snapshot):
            self.stats_repo.update_hop_monitor(snapshot, discovering=True)

        self.hop_monitor_service.set_on_hop_callback(_on_hop_discovered)

        self.stats_repo.update_hop_monitor([], discovering=True)
        await self.run_blocking(
            self.hop_monitor_service.discover_hops, TARGET_IP
        )
        self.stats_repo.update_hop_monitor(
            self.hop_monitor_service.get_hops_snapshot(), discovering=False
        )
        self._last_discovery = _time.time()

    async def execute(self) -> None:
        # Check if IP change triggered immediate re-discovery
        need_rediscovery = (
            self.hop_monitor_service.rediscovery_requested
            or _time.time() - self._last_discovery > HOP_REDISCOVER_INTERVAL
        )

        if need_rediscovery:
            self.hop_monitor_service.clear_rediscovery()
            self.stats_repo.update_hop_monitor([], discovering=True)
            await self.run_blocking(
                self.hop_monitor_service.discover_hops, TARGET_IP
            )
            self.stats_repo.update_hop_monitor(
                self.hop_monitor_service.get_hops_snapshot(), discovering=False
            )
            self._last_discovery = _time.time()
        else:
            # Ping all hops
            await self.run_blocking(self.hop_monitor_service.ping_all_hops)
            self.stats_repo.update_hop_monitor(
                self.hop_monitor_service.get_hops_snapshot(), discovering=False
            )
