from __future__ import annotations

import ipaddress
import logging
from typing import Any

import requests


# HTTP providers (more reliable, IP-only or with geo info)
_IP_PROVIDERS: list[dict[str, Any]] = [
    {
        "url": "http://ip-api.com/json/",
        "ip": "query",
        "country": "country",
        "country_code": "countryCode",
    },
    {
        "url": "http://ifconfig.me/ip",
        "ip": None,  # returns plain text IP
        "country": None,
        "country_code": None,
    },
    {
        "url": "http://icanhazip.com/",
        "ip": None,  # returns plain text IP
        "country": None,
        "country_code": None,
    },
    {
        "url": "http://ipecho.net/plain",
        "ip": None,  # returns plain text IP
        "country": None,
        "country_code": None,
    },
]


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

    def get_public_ip_info(self) -> tuple[str, str, str | None]:
        """Get public IP, country, and country code via HTTP APIs.

        Tries multiple providers in order for resilience.
        """
        for provider in _IP_PROVIDERS:
            try:
                response = requests.get(
                    provider["url"],
                    timeout=5,
                    headers={"Accept": "application/json, text/plain"},
                )
                if response.status_code == 200:
                    # Handle plain text responses
                    if provider["ip"] is None:
                        clean_ip = self._normalize_ip(response.text)
                        if clean_ip:
                            return clean_ip, "N/A", None
                        logging.warning(f"Invalid IP returned by {provider['url']}: {response.text.strip()}")
                    else:
                        data = response.json()
                        ip = data.get(provider["ip"], "")
                        country = data.get(provider["country"], "N/A") if provider["country"] else "N/A"
                        country_code = data.get(provider["country_code"]) if provider["country_code"] else None
                        clean_ip = self._normalize_ip(ip)
                        if clean_ip:
                            return clean_ip, country, country_code
                        logging.warning(f"Invalid IP returned by {provider['url']}: {ip}")
            except Exception as exc:
                logging.debug(f"IP provider {provider['url']} failed: {exc}")
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
