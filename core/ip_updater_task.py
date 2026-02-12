"""IP address update background task."""

from __future__ import annotations

import logging

from config import (
    ENABLE_HOP_MONITORING,
    ENABLE_IP_CHANGE_ALERT,
    IP_CHECK_INTERVAL,
    t,
)
from alerts import add_visual_alert, trigger_alert
from core.background_task import BackgroundTask
from services import IPService, HopMonitorService


class IPUpdaterTask(BackgroundTask):
    """Periodically check public IP and detect changes."""

    def __init__(self, *, ip_service: IPService, hop_monitor_service: HopMonitorService, **kw) -> None:
        super().__init__(
            name="IPUpdater",
            interval=IP_CHECK_INTERVAL,
            enabled=ENABLE_IP_CHANGE_ALERT,
            **kw,
        )
        self.ip_service = ip_service
        self.hop_monitor_service = hop_monitor_service

    async def execute(self) -> None:
        ip, country, code = await self.run_blocking(
            self.ip_service.get_public_ip_info
        )

        # Check for IP change
        change_info = self.ip_service.check_ip_change(ip, country, code)
        if change_info:
            add_visual_alert(
                self.stats_repo.lock,
                self.stats_repo.get_stats(),
                f"[i] {t('alert_ip_changed').format(old=change_info['old_ip'], new=change_info['new_ip'])}",
                "info",
            )
            trigger_alert(self.stats_repo.lock, self.stats_repo.get_stats(), "ip")
            # Trigger immediate hop re-discovery on IP change
            if ENABLE_HOP_MONITORING:
                self.hop_monitor_service.request_rediscovery()

        # Update stats
        self.stats_repo.update_public_ip(ip, country, code)
