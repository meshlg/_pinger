"""Version checking background task."""

from __future__ import annotations

import logging

from config import ENABLE_VERSION_CHECK, VERSION_CHECK_INTERVAL, t
from core.background_task import BackgroundTask


class VersionCheckerTask(BackgroundTask):
    """Periodically check for application updates."""

    def __init__(self, **kw) -> None:
        super().__init__(
            name="VersionChecker",
            interval=VERSION_CHECK_INTERVAL,
            enabled=ENABLE_VERSION_CHECK,
            **kw,
        )

    async def execute(self) -> None:
        from services.version_service import check_update_available

        update_available, current, latest = check_update_available()

        if latest:
            if update_available:
                # Update version info only if new version available
                self.stats_repo.set_latest_version(latest, False)
                logging.info(f"Update available: {current} → {latest}")
                # Add visual alert for new version
                self.stats_repo.add_alert(
                    f"[i] {t('update_available').format(current=current, latest=latest)}",
                    "info",
                )
            else:
                # Version is current — clear any previous version info
                self.stats_repo.set_latest_version(None, True)
                logging.debug(f"Version check: current version {current} is up to date")
        else:
            logging.debug("Version check: unable to fetch latest version")
