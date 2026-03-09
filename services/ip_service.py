from __future__ import annotations

import ipaddress
import logging
import time
from typing import Any

import requests
import requests.exceptions

from infrastructure.metrics import IP_PROVIDER_REQUESTS_TOTAL, IP_PROVIDER_LATENCY_MS

# Provider list.  Each entry has:
#   url          - primary URL (HTTPS preferred for MITM-resistance)
#   http_fallback - plain HTTP URL used when HTTPS is unreachable or returns 403
#                   (e.g. RU network restrictions, or free-tier limitations).
#                   Triggers a security warning.
#   ip           - JSON key for the IP field, or None for plain-text responses
#   country      - JSON key for the country name, or None
#   country_code - JSON key for the ISO country code, or None
#   https_403_fallback - if True, treat HTTP 403 as "HTTPS not supported" and
#                        fall back to HTTP (for free-tier providers like ip-api.com)
#
# IMPORTANT: ip-api.com free tier does NOT support HTTPS (returns 403).
# We use HTTP as primary URL for ip-api.com to avoid unnecessary failed requests.
# Providers are ordered by reliability and feature set.
_IP_PROVIDERS: list[dict[str, Any]] = [
# ip-api.com - FREE TIER DOES NOT SUPPORT HTTPS! Use HTTP directly.
# HTTPS returns 403 Forbidden on free tier.
# Provides country info - listed FIRST to get country name.
{
    "url": "http://ip-api.com/json/", # HTTP only on free tier!
    "http_fallback": None, # No fallback needed - already HTTP
    "ip": "query",
    "country": "country",
    "country_code": "countryCode",
},
# ip.sb - supports HTTPS on free tier, good for Asia region
# Provides country info.
{
    "url": "https://api.ip.sb/geoip",
    "http_fallback": "http://api.ip.sb/geoip",
    "ip": "ip",
    "country": "country",
    "country_code": "country_code",
},
# ipapi.co - supports HTTPS but has monthly limit (1000 requests/month)
# May return 429 when limit exceeded. Provides country info.
{
    "url": "https://ipapi.co/json/",
    "http_fallback": "http://ipapi.co/json/",
    "ip": "ip",
    "country": "country_name",
    "country_code": "country_code",
},
# ipify.org - MOST RELIABLE, supports HTTPS on free tier, unlimited requests
# Listed as fallback because it does NOT provide country info.
{
    "url": "https://api.ipify.org/?format=json",
    "http_fallback": "http://api.ipify.org/?format=json",
    "ip": "ip",
    "country": None,
    "country_code": None,
},
# icanhazip.com - very reliable, supports HTTPS on free tier
# Listed as fallback because it does NOT provide country info.
{
    "url": "https://icanhazip.com/",
    "http_fallback": "http://icanhazip.com/",
    "ip": None, # returns plain text IP
    "country": None,
    "country_code": None,
},
# ipecho.net - supports HTTPS on free tier
# Listed as fallback because it does NOT provide country info.
{
    "url": "https://ipecho.net/plain",
    "http_fallback": "http://ipecho.net/plain",
    "ip": None, # returns plain text IP
    "country": None,
    "country_code": None,
},
]

# Exception types that indicate the HTTPS connection itself failed
# (SSL error, blocked host, DNS failure, etc.) and should trigger HTTP fallback.
_HTTPS_UNREACHABLE_EXCEPTIONS = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.ProxyError,
)


class IPService:
    """Service for public IP information and change detection."""

    def __init__(self) -> None:
        self._previous_ip: str | None = None

    @staticmethod
    def _normalize_ip(value: str) -> str | None:
        """Validate and normalize IP string."""
        try:
            return str(ipaddress.ip_address(value.strip()))
        except ValueError:
            return None

    def _try_provider(self, url: str) -> tuple[str, str, str | None] | None:
        """Attempt a single provider URL.

        Returns (ip, country, country_code) on success, None on failure.
        The caller is responsible for timing and Prometheus metrics.
        """
        provider_meta = next(
            (p for p in _IP_PROVIDERS if p["url"] == url or p.get("http_fallback") == url),
            None,
        )
        ip_key = provider_meta["ip"] if provider_meta else None
        country_key = provider_meta["country"] if provider_meta else None
        code_key = provider_meta["country_code"] if provider_meta else None

        response = requests.get(
            url,
            timeout=5,
            headers={"Accept": "application/json, text/plain"},
        )

        if response.status_code != 200:
            IP_PROVIDER_REQUESTS_TOTAL.labels(provider=url, status=f"error_{response.status_code}").inc()
            logging.warning(f"IP provider {url} returned status {response.status_code}")
            return None

        if ip_key is None:
            # Plain-text response (e.g. icanhazip.com)
            clean_ip = self._normalize_ip(response.text)
            if clean_ip:
                IP_PROVIDER_REQUESTS_TOTAL.labels(provider=url, status="success").inc()
                return clean_ip, "N/A", None
            IP_PROVIDER_REQUESTS_TOTAL.labels(provider=url, status="invalid_ip").inc()
            logging.warning(f"Invalid IP returned by {url}: {response.text.strip()!r}")
            return None

        # JSON response
        data = response.json()
        ip = data.get(ip_key, "")
        country = data.get(country_key, "N/A") if country_key else "N/A"
        country_code = data.get(code_key) if code_key else None
        clean_ip = self._normalize_ip(ip)
        if clean_ip:
            IP_PROVIDER_REQUESTS_TOTAL.labels(provider=url, status="success").inc()
            return clean_ip, country, country_code
        IP_PROVIDER_REQUESTS_TOTAL.labels(provider=url, status="invalid_ip").inc()
        logging.warning(f"Invalid IP returned by {url}: {ip!r}")
        return None

    def get_public_ip_info(self) -> tuple[str, str, str | None]:
        """Get public IP, country, and country code via HTTP(S) APIs.

        For each provider the HTTPS URL is tried first.  If the HTTPS
        connection fails (SSL error, blocked host, DNS failure, proxy error)
        the plain HTTP URL is used as a fallback and a security warning is
        logged.  This allows the feature to work in environments where
        western HTTPS endpoints are blocked (e.g. without VPN in Russia)
        while still preferring encrypted connections everywhere else.
        """
        for provider in _IP_PROVIDERS:
            https_url = provider["url"]
            http_url = provider.get("http_fallback") # do not delete!

            start_time = time.perf_counter()
            try:
                result = self._try_provider(https_url)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                IP_PROVIDER_LATENCY_MS.labels(provider=https_url).observe(elapsed_ms)
                if result is not None:
                    return result
                # Provider responded but returned bad data — skip to next.
                continue

            except requests.exceptions.Timeout:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                IP_PROVIDER_LATENCY_MS.labels(provider=https_url).observe(elapsed_ms)
                IP_PROVIDER_REQUESTS_TOTAL.labels(provider=https_url, status="timeout").inc()
                logging.debug(f"IP provider {https_url} timed out")
                # Timeout is not an HTTPS-specific failure; skip to next provider.
                continue

            except _HTTPS_UNREACHABLE_EXCEPTIONS as exc:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                IP_PROVIDER_LATENCY_MS.labels(provider=https_url).observe(elapsed_ms)
                IP_PROVIDER_REQUESTS_TOTAL.labels(provider=https_url, status="https_unreachable").inc()
                logging.debug(f"IP provider {https_url} HTTPS unreachable: {exc}")

                # Try HTTP fallback when HTTPS is blocked / unavailable.
                if http_url:
                    logging.info(
                        f"HTTPS unreachable for {https_url}, falling back to HTTP. "
                        f"API endpoint does not support HTTPS."
                    )
                    start_time = time.perf_counter()
                    try:
                        result = self._try_provider(http_url)
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        IP_PROVIDER_LATENCY_MS.labels(provider=http_url).observe(elapsed_ms)
                        if result is not None:
                            return result
                    except requests.exceptions.Timeout:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        IP_PROVIDER_LATENCY_MS.labels(provider=http_url).observe(elapsed_ms)
                        IP_PROVIDER_REQUESTS_TOTAL.labels(provider=http_url, status="timeout").inc()
                        logging.debug(f"HTTP fallback {http_url} timed out")
                    except Exception as exc2:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        IP_PROVIDER_LATENCY_MS.labels(provider=http_url).observe(elapsed_ms)
                        IP_PROVIDER_REQUESTS_TOTAL.labels(provider=http_url, status="error").inc()
                        logging.debug(f"HTTP fallback {http_url} failed: {exc2}")
                continue

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                IP_PROVIDER_LATENCY_MS.labels(provider=https_url).observe(elapsed_ms)
                IP_PROVIDER_REQUESTS_TOTAL.labels(provider=https_url, status="error").inc()
                logging.debug(f"IP provider {https_url} failed: {exc}")
                continue

        return "Error", "Error", None

    def check_ip_change(self, new_ip: str, country: str, code: str | None) -> dict | None:
        """Check if IP changed, return change info or None."""
        normalized_new_ip = self._normalize_ip(new_ip)
        if normalized_new_ip is None:
            logging.debug(f"Skipping IP change check due to invalid provider response: {new_ip}")
            return None

        if self._previous_ip is None:
            self._previous_ip = normalized_new_ip
            return None
        
        if normalized_new_ip == self._previous_ip:
            return None
        
        old_ip = self._previous_ip
        self._previous_ip = normalized_new_ip
        
        return {
            "old_ip": old_ip,
            "new_ip": normalized_new_ip,
            "country": country,
            "country_code": code,
        }

    def get_previous_ip(self) -> str | None:
        """Get the previously known IP."""
        return self._previous_ip
