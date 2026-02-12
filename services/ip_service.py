from __future__ import annotations

import logging
from typing import Any

import requests


# HTTPS providers with response field mappings (tried in order)
_IP_PROVIDERS: list[dict[str, Any]] = [
    {
        "url": "https://ipinfo.io/json",
        "ip": "ip",
        "country": "country",
        "country_code": "country",  # ipinfo returns 2-letter code in "country"
    },
    {
        "url": "https://ipapi.co/json/",
        "ip": "ip",
        "country": "country_name",
        "country_code": "country_code",
    },
    {
        "url": "https://ip-api.com/json/",  # has HTTPS on paid plan; free still works via https
        "ip": "query",
        "country": "country",
        "country_code": "countryCode",
    },
]


class IPService:
    """Service for public IP information and change detection."""

    def __init__(self) -> None:
        self._previous_ip: str | None = None

    def get_public_ip_info(self) -> tuple[str, str, str | None]:
        """Get public IP, country, and country code via HTTPS APIs.

        Tries multiple providers in order for resilience.
        """
        for provider in _IP_PROVIDERS:
            try:
                response = requests.get(
                    provider["url"],
                    timeout=5,
                    headers={"Accept": "application/json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    ip = data.get(provider["ip"], "")
                    country = data.get(provider["country"], "N/A")
                    country_code = data.get(provider["country_code"])
                    if ip:
                        return ip, country, country_code
            except Exception as exc:
                logging.debug(f"IP provider {provider['url']} failed: {exc}")
                continue

        return "Error", "Error", None

    def check_ip_change(self, new_ip: str, country: str, code: str | None) -> dict | None:
        """Check if IP changed, return change info or None."""
        if self._previous_ip is None or new_ip == "Error":
            self._previous_ip = new_ip
            return None
        
        if new_ip == self._previous_ip:
            return None
        
        old_ip = self._previous_ip
        self._previous_ip = new_ip
        
        return {
            "old_ip": old_ip,
            "new_ip": new_ip,
            "country": country,
            "country_code": code,
        }

    def get_previous_ip(self) -> str | None:
        """Get the previously known IP."""
        return self._previous_ip
