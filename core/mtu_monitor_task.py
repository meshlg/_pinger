"""MTU monitoring background task."""

from __future__ import annotations

import logging

from config import (
    ENABLE_MTU_MONITORING,
    MTU_CHECK_INTERVAL,
    MTU_CLEAR_CONSECUTIVE,
    MTU_DIFF_THRESHOLD,
    MTU_ISSUE_CONSECUTIVE,
    TARGET_IP,
    PATH_MTU_CHECK_INTERVAL,
    t,
)
from core.background_task import BackgroundTask
from infrastructure import METRICS_AVAILABLE, MTU_PROBLEMS_TOTAL, MTU_STATUS_GAUGE
from services import MTUService


class MTUMonitorTask(BackgroundTask):
    """Periodically check MTU with hysteresis-based status transitions."""

    def __init__(self, *, mtu_service: MTUService, **kw) -> None:
        super().__init__(
            name="MTUMonitor",
            interval=MTU_CHECK_INTERVAL,
            enabled=ENABLE_MTU_MONITORING,
            **kw,
        )
        self.mtu_service = mtu_service
        self._last_path_check = 0.0
        self._last_known_path_mtu = None

    async def execute(self) -> None:
        import time
        
        # Determine if we should check Path MTU
        now = time.time()
        should_check_path = (now - self._last_path_check) >= PATH_MTU_CHECK_INTERVAL
        
        # Get MTU info
        mtu_info = await self.run_blocking(
            self.mtu_service.check_mtu, 
            TARGET_IP, 
            discover_path=should_check_path
        )

        local_mtu = mtu_info["local_mtu"]
        path_mtu = mtu_info["path_mtu"]
        
        # Update path MTU state
        if should_check_path:
            self._last_path_check = now
            if path_mtu:
                self._last_known_path_mtu = path_mtu
        elif path_mtu is None:
            # Use cached value if we skipped check
            path_mtu = self._last_known_path_mtu

        # Determine status
        status = t("mtu_ok")
        if local_mtu and path_mtu:
            diff = local_mtu - path_mtu
            if path_mtu < 1000:
                status = t("mtu_fragmented")
            elif diff >= MTU_DIFF_THRESHOLD and path_mtu < local_mtu:
                status = t("mtu_low")

        # Update hysteresis counters via repository
        is_issue = status in [t("mtu_low"), t("mtu_fragmented")]
        current = self.stats_repo.get_mtu_status()
        
        # Fast-track first update by bypassing hysteresis
        is_first_run = self.stats_repo.get_stats().get("local_mtu") is None
        if is_first_run:
            self.stats_repo.update_mtu(local_mtu, path_mtu, status)
            self.stats_repo.set_mtu_status_change_time()
            # Update hysteresis tracking locally to seed the state
            self.stats_repo.update_mtu_hysteresis(is_issue)
            logging.info(f"MTU initial status: {status}")
            if METRICS_AVAILABLE:
                try:
                    if is_issue:
                        MTU_PROBLEMS_TOTAL.inc()
                    MTU_STATUS_GAUGE.set(0 if not is_issue else (1 if status == t("mtu_low") else 2))
                except Exception:
                    pass
            return

        cons_issues, cons_ok = self.stats_repo.update_mtu_hysteresis(is_issue)

        # Apply hysteresis
        if is_issue:
            if cons_issues >= MTU_ISSUE_CONSECUTIVE and current != status:
                self.stats_repo.update_mtu(local_mtu, path_mtu, status)
                self.stats_repo.set_mtu_status_change_time()
                logging.info(f"MTU problem: {status}")
                if METRICS_AVAILABLE:
                    try:
                        MTU_PROBLEMS_TOTAL.inc()
                        MTU_STATUS_GAUGE.set(1 if status == t("mtu_low") else 2)
                    except Exception:
                        pass
        else:
            if cons_ok >= MTU_CLEAR_CONSECUTIVE and current != t("mtu_ok"):
                self.stats_repo.update_mtu(local_mtu, path_mtu, t("mtu_ok"))
                self.stats_repo.set_mtu_status_change_time()
                logging.info("MTU status cleared")
                if METRICS_AVAILABLE:
                    try:
                        MTU_STATUS_GAUGE.set(0)
                    except Exception:
                        pass
