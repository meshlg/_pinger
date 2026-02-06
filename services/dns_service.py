from __future__ import annotations

import socket
import time
from typing import Optional

from config import DNS_SLOW_THRESHOLD, DNS_TEST_DOMAIN, t


class DNSService:
    """Service for DNS resolution monitoring."""

    def __init__(self) -> None:
        pass

    def check_dns_resolve(self, domain: str | None = None) -> tuple[bool, Optional[float], str]:
        """Check DNS resolution, return (success, time_ms, localized_status)."""
        domain = domain or DNS_TEST_DOMAIN
        
        try:
            start = time.time()
            socket.gethostbyname(domain)
            ms = (time.time() - start) * 1000
            status = t("slow") if ms > DNS_SLOW_THRESHOLD else t("ok")
            return True, ms, status
        except Exception:
            return False, None, t("failed")
