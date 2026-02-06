from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from typing import Optional, Tuple

import requests


class IPService:
    """Service for public IP information and change detection."""

    def __init__(self) -> None:
        self._previous_ip: Optional[str] = None

    def get_public_ip_info(self) -> Tuple[str, str, Optional[str]]:
        """Get public IP, country, and country code."""
        try:
            response = requests.get(
                "http://ip-api.com/json/",
                timeout=3,
            )
            if response.status_code == 200:
                data = response.json()
                return (
                    data.get("query", "N/A"),
                    data.get("country", "N/A"),
                    data.get("countryCode", None),
                )
        except Exception:
            pass
        return "Error", "Error", None

    def check_ip_change(self, new_ip: str, country: str, code: Optional[str]) -> Optional[dict]:
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

    def get_previous_ip(self) -> Optional[str]:
        """Get the previously known IP."""
        return self._previous_ip
