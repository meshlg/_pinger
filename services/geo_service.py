"""Geolocation service for IP addresses.

Provides IP geolocation and ASN lookup with caching.
Uses ip-api.com (free tier: 45 requests/minute).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class GeoInfo:
    """Geolocation information for an IP address."""
    country: str
    country_code: str
    city: str
    asn: str
    org: str  # Organization


class GeoService:
    """Service to lookup geolocation and ASN for IP addresses."""

    def __init__(self, cache_ttl: int = 3600) -> None:
        """Initialize geolocation service.

        Args:
            cache_ttl: Time to live for cache entries in seconds (default: 1 hour)
        """
        self._cache: dict[str, tuple[GeoInfo, float]] = {}
        self._cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "pinger/2.0"})

    def get_geo(self, ip: str) -> Optional[GeoInfo]:
        """Get geolocation for IP with caching.

        Args:
            ip: IP address to look up

        Returns:
            GeoInfo if found, None otherwise
        """
        # Check cache
        if ip in self._cache:
            info, cached_at = self._cache[ip]
            if time.time() - cached_at < self._cache_ttl:
                logger.debug(f"Geo cache hit for {ip}")
                return info

        try:
            # Use ip-api.com (free tier: 45 requests/minute, HTTP)
            resp = self._session.get(
                f"http://ip-api.com/json/{ip}",
                params={
                    "fields": "status,country,countryCode,city,as,org"
                },
                timeout=5
            )
            data = resp.json()

            if data.get("status") != "success":
                logger.debug(f"Geo lookup failed for {ip}: {data.get('message', 'unknown')}")
                return None

            info = GeoInfo(
                country=data.get("country", "?"),
                country_code=data.get("countryCode", ""),
                city=data.get("city", ""),
                asn=data.get("as", "").replace("AS", ""),  # Remove "AS" prefix
                org=data.get("org", ""),
            )

            # Cache the result
            self._cache[ip] = (info, time.time())
            logger.debug(f"Geo lookup success for {ip}: {info.country} {info.asn}")
            return info

        except requests.RequestException as exc:
            logger.debug(f"Geo lookup network error for {ip}: {exc}")
        except (ValueError, KeyError) as exc:
            logger.debug(f"Geo lookup parse error for {ip}: {exc}")

        return None

    def clear_cache(self) -> None:
        """Clear the geolocation cache."""
        self._cache.clear()
        logger.debug("Geo cache cleared")
