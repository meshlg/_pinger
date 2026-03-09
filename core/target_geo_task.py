"""Target IP geolocation background task.

Fetches geolocation for the target IP address once at startup.
"""

from __future__ import annotations

import logging

from config import TARGET_IP
from core.background_task import BackgroundTask
from services import GeoService

logger = logging.getLogger(__name__)


class TargetGeoTask(BackgroundTask):
    """Fetch geolocation for target IP address.

    This task runs once at startup to get the country information
    for the configured TARGET_IP.
    """

    def __init__(self, *, geo_service: GeoService, **kw) -> None:
        super().__init__(
            name="TargetGeo",
            interval=3600,  # Check every hour (but only updates if needed)
            enabled=True,
            **kw,
        )
        self.geo_service = geo_service
        self._initialized = False

    async def execute(self) -> None:
        """Fetch target IP geolocation."""
        # Only fetch once at startup, then just verify periodically
        geo_info = await self.run_blocking(self.geo_service.get_geo, TARGET_IP)

        if geo_info:
            self.stats_repo.update_target_geo(geo_info.country, geo_info.country_code)
            if not self._initialized:
                logger.info(f"Target {TARGET_IP} geolocation: {geo_info.country} ({geo_info.country_code})")
                self._initialized = True
        elif not self._initialized:
            logger.debug(f"Could not fetch geolocation for target {TARGET_IP}")
