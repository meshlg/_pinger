"""Version check service - queries GitHub for latest release.

This module provides functionality to check for application updates by querying
the GitHub Tags API. It includes caching, retry logic, and Prometheus metrics.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Final

import requests

from config import VERSION
from infrastructure.metrics import VERSION_CHECK_TOTAL, VERSION_CHECK_LATENCY_MS


# Constants
GITHUB_API_URL: Final[str] = "https://api.github.com/repos/meshlg/_pinger/tags"
DEFAULT_TIMEOUT: Final[float] = 5.0
DEFAULT_CACHE_TTL: Final[int] = 3600  # 1 hour
MAX_RETRIES: Final[int] = 3
RETRY_BACKOFF_FACTOR: Final[float] = 0.5  # Start with 0.5s, double each retry
USER_AGENT: Final[str] = f"Pinger/{VERSION}"


@dataclass(frozen=True)
class VersionInfo:
    """Immutable version information container."""
    current: str
    latest: str | None
    update_available: bool
    
    def __bool__(self) -> bool:
        """Return True if version info is available (latest is not None)."""
        return self.latest is not None


class VersionService:
    """Service for checking application version updates.
    
    Features:
    - Queries GitHub Tags API for latest release
    - Caches results to minimize API calls
    - Retry logic with exponential backoff
    - Prometheus metrics integration
    - Semantic version comparison
    
    Example:
        service = VersionService()
        info = service.check_for_update()
        if info.update_available:
            print(f"Update available: {info.current} -> {info.latest}")
    """
    
    def __init__(
        self,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        """Initialize the version service.
        
        Args:
            cache_ttl: Cache time-to-live in seconds.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._max_retries = max_retries
        self._cache: str | None = None
        self._last_check_time: float = 0
    
    def clear_cache(self) -> None:
        """Clear the version cache."""
        self._cache = None
        self._last_check_time = 0
    
    @staticmethod
    def _parse_version(version_str: str) -> tuple[int, ...]:
        """Parse version string into a tuple of integers for comparison.
        
        Args:
            version_str: Version string to parse.
            
        Returns:
            Tuple of integer version components.
        """
        clean = version_str.lstrip("vV")
        parts: list[int] = []
        for part in clean.split("."):
            match = re.match(r"^(\d+)", part)
            if match:
                parts.append(int(match.group(1)))
        return tuple(parts)
    
    @staticmethod
    def _compare_versions(current: str, latest: str) -> bool:
        """Compare two version strings.
        
        Args:
            current: Current version string.
            latest: Latest version string.
            
        Returns:
            True if latest > current.
        """
        current_parts = list(VersionService._parse_version(current))
        latest_parts = list(VersionService._parse_version(latest))
        
        # Pad to same length for proper comparison
        max_len = max(len(current_parts), len(latest_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        
        return latest_parts > current_parts
    
    def _fetch_with_retry(self) -> str | None:
        """Fetch latest version from GitHub with retry logic.
        
        Returns:
            Latest version string or None if all attempts fail.
        """
        last_exception: Exception | None = None
        
        for attempt in range(self._max_retries):
            start_time = time.perf_counter()
            
            try:
                response = requests.get(
                    GITHUB_API_URL,
                    timeout=self._timeout,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": USER_AGENT,
                    },
                )
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                VERSION_CHECK_LATENCY_MS.observe(elapsed_ms)
                
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    VERSION_CHECK_TOTAL.labels(status="empty").inc()
                    return None
                
                # Find the latest semantic version tag
                versions: list[tuple[tuple[int, ...], str]] = []
                for tag_data in data:
                    tag_name = tag_data.get("name", "")
                    clean_name = tag_name.lstrip("v")
                    try:
                        parsed = self._parse_version(clean_name)
                        if parsed:
                            versions.append((parsed, clean_name))
                    except (ValueError, TypeError):
                        continue
                
                if not versions:
                    VERSION_CHECK_TOTAL.labels(status="no_valid_tags").inc()
                    return None
                
                # Sort by parsed version tuple, take highest
                versions.sort(key=lambda x: x[0], reverse=True)
                latest = versions[0][1]
                
                VERSION_CHECK_TOTAL.labels(status="success").inc()
                return latest
                
            except requests.exceptions.Timeout:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                VERSION_CHECK_LATENCY_MS.observe(elapsed_ms)
                VERSION_CHECK_TOTAL.labels(status="timeout").inc()
                last_exception = TimeoutError("GitHub API request timed out")
                logging.debug(f"Version check timeout (attempt {attempt + 1}/{self._max_retries})")
                
            except requests.exceptions.HTTPError as exc:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                VERSION_CHECK_LATENCY_MS.observe(elapsed_ms)
                status = f"http_{exc.response.status_code}" if exc.response else "http_error"
                VERSION_CHECK_TOTAL.labels(status=status).inc()
                last_exception = exc
                logging.debug(f"Version check HTTP error (attempt {attempt + 1}): {exc}")
                # Don't retry on 4xx client errors
                if exc.response and 400 <= exc.response.status_code < 500:
                    break
                    
            except requests.exceptions.RequestException as exc:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                VERSION_CHECK_LATENCY_MS.observe(elapsed_ms)
                VERSION_CHECK_TOTAL.labels(status="network_error").inc()
                last_exception = exc
                logging.debug(f"Version check network error (attempt {attempt + 1}): {exc}")
            
            except (ValueError, KeyError) as exc:
                VERSION_CHECK_TOTAL.labels(status="parse_error").inc()
                last_exception = exc
                logging.debug(f"Version check parse error: {exc}")
                break
            
            # Wait before retry with exponential backoff
            if attempt < self._max_retries - 1:
                sleep_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(sleep_time)
        
        if last_exception:
            logging.debug(f"Version check failed after {self._max_retries} attempts: {last_exception}")
        
        return None
    
    def get_latest_version(self) -> str | None:
        """Get the latest version from GitHub with caching.
        
        Returns cached result if still valid, otherwise fetches from GitHub.
        
        Returns:
            Latest version string or None if unavailable.
        """
        current_time = time.time()
        
        # Return cached version if still valid
        if self._cache and (current_time - self._last_check_time) < self._cache_ttl:
            return self._cache
        
        # Fetch new version
        latest = self._fetch_with_retry()
        
        if latest:
            self._cache = latest
            self._last_check_time = current_time
            return latest
        
        # Return stale cache on failure (better than nothing)
        return self._cache
    
    def check_for_update(self) -> VersionInfo:
        """Check if an update is available.
        
        Returns:
            VersionInfo with current version, latest version, and update status.
        """
        latest = self.get_latest_version()
        
        if latest is None:
            return VersionInfo(
                current=VERSION,
                latest=None,
                update_available=False,
            )
        
        try:
            update_available = self._compare_versions(VERSION, latest)
        except (ValueError, TypeError) as exc:
            logging.debug(f"Cannot compare versions: {exc}")
            update_available = False
        
        return VersionInfo(
            current=VERSION,
            latest=latest,
            update_available=update_available,
        )


# Module-level cache variables for backward compatibility
_LATEST_VERSION_CACHE: str | None = None
_LAST_CHECK_TIME: float = 0


# Backward-compatible module-level functions
def clear_cache() -> None:
    """Clear the version cache (useful for testing)."""
    global _LATEST_VERSION_CACHE, _LAST_CHECK_TIME
    _LATEST_VERSION_CACHE = None
    _LAST_CHECK_TIME = 0


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string into a tuple of integers for comparison.
    
    This is a backward-compatible wrapper around the class method.
    """
    return VersionService._parse_version(version_str)


def get_latest_version() -> str | None:
    """Fetch latest version from GitHub tags with caching.
    
    This is a backward-compatible module-level function.
    """
    global _LATEST_VERSION_CACHE, _LAST_CHECK_TIME
    
    current_time = time.time()
    
    # Return cached version if still valid
    if _LATEST_VERSION_CACHE and (current_time - _LAST_CHECK_TIME) < DEFAULT_CACHE_TTL:
        return _LATEST_VERSION_CACHE
    
    # Create a temporary service instance to fetch
    service = VersionService()
    latest = service._fetch_with_retry()
    
    if latest:
        _LATEST_VERSION_CACHE = latest
        _LAST_CHECK_TIME = current_time
        return latest
    
    # Return stale cache on failure
    return _LATEST_VERSION_CACHE


def check_update_available() -> tuple[bool, str, str | None]:
    """Check if update is available.
    
    This is a backward-compatible module-level function.
    
    Returns:
        (update_available: bool, current_version: str, latest_version: Optional[str])
    """
    latest = get_latest_version()
    
    if latest is None:
        return False, VERSION, None
    
    try:
        update_available = VersionService._compare_versions(VERSION, latest)
    except (ValueError, TypeError) as exc:
        logging.debug(f"Cannot compare versions: {exc}")
        update_available = False
    
    return update_available, VERSION, latest
