"""Geolocation service for IP addresses.

Provides IP geolocation and ASN lookup with caching.
Uses ip-api.com via HTTP (free tier does not support HTTPS).

IMPORTANT: ip-api.com free tier does NOT support HTTPS.
HTTPS endpoint returns 403 Forbidden. We use HTTP directly.
For enhanced security, consider using a VPN or a paid geolocation service.
"""
from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import requests
import requests.exceptions

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
    """Service to lookup geolocation and ASN for IP addresses.

    Features:
    - Uses HTTP directly for ip-api.com (free tier doesn't support HTTPS)
    - LRU cache with configurable TTL and max size
    - Fallback providers for redundancy

    NOTE: ip-api.com free tier returns 403 Forbidden on HTTPS requests.
    We use HTTP directly to avoid unnecessary failed requests.
    """

    # Primary URL is HTTP because ip-api.com free tier doesn't support HTTPS
    _PRIMARY_URL = "http://ip-api.com/json/"
    # Alternative providers for redundancy (all support HTTPS on free tier)
    # Ordered by reliability and rate limit tolerance
    _FALLBACK_PROVIDERS = [
        {
            "url": "https://ip.sb/geoip/{ip}",
            "country_key": "country",
            "country_code_key": "country_code",
            "city_key": "city",
            "asn_key": "asn",
            "org_key": "organization",
        },
        {
            "url": "https://ipapi.co/{ip}/json/",
            "country_key": "country_name",
            "country_code_key": "country_code",
            "city_key": "city",
            "asn_key": "asn",
            "org_key": "org",
        },
    ]
    _MAX_CACHE_SIZE = 500  # Maximum cached IPs (LRU eviction)
    _WARNED_HTTP = False  # Class-level flag to avoid spamming warnings

    def __init__(self, cache_ttl: int = 3600) -> None:
        """Initialize geolocation service.

        Args:
            cache_ttl: Time to live for cache entries in seconds (default: 1 hour)
        """
        self._cache: OrderedDict[str, tuple[GeoInfo, float]] = OrderedDict()
        self._cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "pinger/2.0"})

    def _try_fetch_ip_api(self, ip: str) -> Optional[GeoInfo]:
        """Fetch geo data from ip-api.com (primary, HTTP only).

        Returns GeoInfo on success, None on failure.
        """
        resp = self._session.get(
            f"{self._PRIMARY_URL}{ip}",
            params={"fields": "status,country,countryCode,city,as,org"},
            timeout=5,
        )
        data = resp.json()

        if data.get("status") != "success":
            logger.debug(f"ip-api.com lookup failed for {ip}: {data.get('message', 'unknown')}")
            return None

        return GeoInfo(
            country=data.get("country", "?"),
            country_code=data.get("countryCode", ""),
            city=data.get("city", ""),
            asn=data.get("as", "").replace("AS", ""),  # Remove "AS" prefix
            org=data.get("org", ""),
        )

    def _try_fetch_fallback(self, provider: dict, ip: str) -> Optional[GeoInfo]:
        """Fetch geo data from a fallback provider.

        Returns GeoInfo on success, None on failure.
        """
        url = provider["url"].format(ip=ip)
        resp = self._session.get(url, timeout=5)

        if resp.status_code != 200:
            logger.debug(f"Fallback provider {provider['url']} returned {resp.status_code}")
            return None

        data = resp.json()

        # Check for error responses
        if data.get("error") or data.get("status") == "fail":
            logger.debug(f"Fallback provider error for {ip}: {data.get('reason', data.get('error', 'unknown'))}")
            return None

        return GeoInfo(
            country=data.get(provider["country_key"], "?"),
            country_code=data.get(provider["country_code_key"], ""),
            city=data.get(provider["city_key"], ""),
            asn=str(data.get(provider["asn_key"], "")).replace("AS", ""),
            org=data.get(provider["org_key"], ""),
        )

    def get_geo(self, ip: str) -> Optional[GeoInfo]:
        """Get geolocation for IP with caching and fallback providers.

        Uses ip-api.com via HTTP (free tier doesn't support HTTPS).
        Falls back to alternative providers if primary fails.

        Args:
            ip: IP address to look up

        Returns:
            GeoInfo if found, None otherwise
        """
        # Check cache (with LRU bump)
        if ip in self._cache:
            info, cached_at = self._cache[ip]
            if time.time() - cached_at < self._cache_ttl:
                self._cache.move_to_end(ip)  # LRU: mark as recently used
                logger.debug(f"Geo cache hit for {ip}")
                return info
            else:
                del self._cache[ip]  # Expired

        info = None

        # Log warning about HTTP usage (once per session)
        if not GeoService._WARNED_HTTP:
            logger.info(
                "Using HTTP for ip-api.com geolocation (free tier). "
                "Connection is NOT encrypted — use a VPN for enhanced security."
            )
            GeoService._WARNED_HTTP = True

        # Try primary provider (ip-api.com via HTTP)
        try:
            info = self._try_fetch_ip_api(ip)
        except requests.exceptions.Timeout:
            logger.debug(f"Geo lookup timeout for {ip} via ip-api.com")
        except requests.RequestException as exc:
            logger.debug(f"Geo lookup network error for {ip} via ip-api.com: {exc}")
        except (ValueError, KeyError) as exc:
            logger.debug(f"Geo lookup parse error for {ip} via ip-api.com: {exc}")

        # Try fallback providers if primary failed
        if info is None:
            for fallback in self._FALLBACK_PROVIDERS:
                try:
                    info = self._try_fetch_fallback(fallback, ip)
                    if info is not None:
                        logger.debug(f"Geo lookup succeeded via fallback for {ip}")
                        break
                except requests.exceptions.Timeout:
                    logger.debug(f"Geo lookup timeout for {ip} via {fallback['url']}")
                except requests.RequestException as exc:
                    logger.debug(f"Geo lookup error for {ip} via {fallback['url']}: {exc}")
                except (ValueError, KeyError) as exc:
                    logger.debug(f"Geo lookup parse error for {ip} via {fallback['url']}: {exc}")

        if info is not None:
            # Evict oldest entries if at capacity
            while len(self._cache) >= self._MAX_CACHE_SIZE:
                self._cache.popitem(last=False)  # Remove LRU (oldest) entry
            self._cache[ip] = (info, time.time())
            logger.debug(f"Geo lookup success for {ip}: {info.country} {info.asn}")

        return info

    def clear_cache(self) -> None:
        """Clear the geolocation cache."""
        self._cache.clear()
        logger.debug("Geo cache cleared")
