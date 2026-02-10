from __future__ import annotations

import ipaddress
import logging
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Optional, Tuple

from config import TARGET_IP

try:
    from pythonping import ping as pythonping_ping  # type: ignore[import]
    PYTHONPING_AVAILABLE = True
except Exception:
    pythonping_ping = None
    PYTHONPING_AVAILABLE = False


class PingService:
    """Service for ping operations."""

    def __init__(self) -> None:
        self._ping_available: bool | None = None
        self._dns_cache: dict[str, dict[str, Any]] = {}
        self._dns_cache_lock = threading.Lock()

    def _check_ping_available(self) -> bool:
        """Check if ping command is available on the system."""
        if self._ping_available is not None:
            return self._ping_available
        self._ping_available = shutil.which("ping") is not None
        return self._ping_available

    def _detect_ipv6(self, host: str) -> bool:
        """Detect if host is IPv6 address or resolves to IPv6."""
        try:
            addr = ipaddress.ip_address(host)
            return addr.version == 6
        except Exception:
            cache_key = host
            with self._dns_cache_lock:
                cached = self._dns_cache.get(cache_key)
                if cached and (time.time() - cached["timestamp"]) < 60.0:
                    return cached["is_ipv6"]
            try:
                infos = socket.getaddrinfo(host, None)
                is_ipv6 = any(info[0] == socket.AF_INET6 for info in infos)
                with self._dns_cache_lock:
                    self._dns_cache[cache_key] = {
                        "is_ipv6": is_ipv6,
                        "timestamp": time.time(),
                    }
                return is_ipv6
            except Exception:
                return False

    def ping_host(self, host: str) -> Tuple[bool, Optional[float]]:
        """Ping a host and return (success, latency_ms)."""
        is_ipv6 = self._detect_ipv6(host)

        if not self._check_ping_available():
            # Fallback to pythonping
            if PYTHONPING_AVAILABLE and pythonping_ping:
                return self._ping_with_pythonping(host)
            return False, None

        return self._ping_with_system(host, is_ipv6)

    def _ping_with_pythonping(self, host: str) -> Tuple[bool, Optional[float]]:
        """Fallback ping using pythonping library."""
        try:
            if pythonping_ping is None:
                return False, None
            resp = pythonping_ping(host, count=1, timeout=1)
            
            # Try to extract latency from response
            for attr in ("rtt_avg_ms", "rtt_avg", "avg_rtt", "rtt_ms", "rtt"):
                if hasattr(resp, attr):
                    try:
                        return True, float(getattr(resp, attr))
                    except Exception:
                        continue
            
            # Try iterating response
            try:
                iterator = iter(resp)
            except TypeError:
                iterator = None
            
            if iterator is not None:
                for item in resp:
                    for attr in ("time_elapsed_ms", "time_elapsed", "rtt_ms", "rtt"):
                        if hasattr(item, attr):
                            value = getattr(item, attr)
                            try:
                                if attr == "time_elapsed":
                                    return True, float(value) * 1000.0
                                return True, float(value)
                            except Exception:
                                continue
                    match = re.search(r"time[=<]?\s*([0-9]+[.,]?[0-9]*)", str(item), re.IGNORECASE)
                    if match:
                        return True, float(match.group(1).replace(",", "."))
            
            # Try parsing string representation
            match_resp = re.search(
                r"time[=<]?\s*([0-9]+[.,]?[0-9]*)",
                str(resp),
                re.IGNORECASE,
            )
            if match_resp:
                return True, float(match_resp.group(1).replace(",", "."))
            
            logging.warning("pythonping produced no latency info")
            return False, None
        except Exception as exc:
            logging.error(f"pythonping failed: {exc}")
            return False, None

    def _ping_with_system(self, host: str, is_ipv6: bool) -> Tuple[bool, Optional[float]]:
        """System ping command."""
        ping_cmd = shutil.which("ping")
        try:
            if sys.platform == "win32":
                cmd = [ping_cmd, "-n", "1", "-w", "1000", host]
                encoding = "oem"
            else:
                if is_ipv6:
                    cmd = [ping_cmd, "-6", "-c", "1", host]
                else:
                    cmd = [ping_cmd, "-c", "1", host]
                encoding = "utf-8"
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                encoding=encoding,
                errors="replace",
            )
            stdout = result.stdout or ""
            
            # Parse latency
            match_time = re.search(
                r"(?:time|время)\s*[=<>]*\s*([0-9]+[.,]?[0-9]*)",
                stdout,
                re.IGNORECASE,
            )
            if match_time:
                return True, float(match_time.group(1).replace(",", "."))
            
            if re.search(r"time\s*<\s*1\s*(?:ms|мс)?", stdout, re.IGNORECASE):
                return True, 0.5
            
            match_avg = re.search(
                r"(?:Average|Среднее)\s*[=:]?\s*([0-9]+)[.,]?[0-9]*\s*(?:ms|мс)?",
                stdout,
                re.IGNORECASE,
            )
            if match_avg:
                return True, float(match_avg.group(1))
            
            if result.returncode == 0:
                return True, 0.0
            return False, None
            
        except subprocess.TimeoutExpired:
            return False, None
        except Exception as exc:
            logging.error(f"ping_host exception: {exc}")
            return False, None

    def is_available(self) -> bool:
        """Check if ping functionality is available."""
        return self._check_ping_available() or PYTHONPING_AVAILABLE
