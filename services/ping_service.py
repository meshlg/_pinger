from __future__ import annotations

import asyncio
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
from infrastructure import get_process_manager

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
        self.process_manager = get_process_manager()

    def _check_ping_available(self) -> bool:
        """Check if ping command is available on the system."""
        if self._ping_available is not None:
            return self._ping_available
        self._ping_available = shutil.which("ping") is not None
        return self._ping_available

    async def _detect_ipv6_async(self, host: str) -> bool:
        """Detect if host is IPv6 address or resolves to IPv6 (async)."""
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
                loop = asyncio.get_running_loop()
                # socket.getaddrinfo is blocking, run in executor
                infos = await loop.run_in_executor(
                    None, 
                    lambda: socket.getaddrinfo(host, None)
                )
                is_ipv6 = any(info[0] == socket.AF_INET6 for info in infos)
                with self._dns_cache_lock:
                    self._dns_cache[cache_key] = {
                        "is_ipv6": is_ipv6,
                        "timestamp": time.time(),
                    }
                return is_ipv6
            except Exception:
                return False

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

    def _build_ping_command(self, host: str, is_ipv6: bool | None = None) -> Tuple[list[str], str, dict[str, Any]] | None:
        """Build the ping command, encoding and kwargs."""
        ping_cmd = shutil.which("ping")
        if not ping_cmd:
            return None
            
        # Security check: prevent argument injection
        if host.strip().startswith("-"):
            logging.error(f"Security: Invalid host '{host}' (starts with hyphen)")
            return None
        
        # We assume is_ipv6 is passed or we default to False if unknown in async context
        # (calling sync _detect_ipv6 here would block)
        if is_ipv6 is None:
             # Safety fallback - assume IPv4 if not provided, 
             # preventing blocking call. Caller should resolve first.
             is_ipv6 = False
        
        if sys.platform == "win32":
            cmd = [ping_cmd, "-n", "1", "-w", "1000", host]
            encoding = "oem"
        else:
            if is_ipv6:
                cmd = [ping_cmd, "-6", "-c", "1", host]
            else:
                cmd = [ping_cmd, "-c", "1", host]
            encoding = "utf-8"
        
        # Use creationflags on Windows to prevent orphan processes
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            
        return cmd, encoding, kwargs

    # _run_ping_command (sync) removed.

    async def _run_ping_command_async(self, host: str, is_ipv6: bool | None = None) -> Tuple[str | None, int | None]:
        """Execute system ping command asynchronously."""
        if is_ipv6 is None:
            is_ipv6 = await self._detect_ipv6_async(host)

        built = self._build_ping_command(host, is_ipv6)
        if not built:
            return None
        cmd, encoding, kwargs = built
        
        try:
            # timeout=2.0 seconds matches synchronous timeout
            stdout, _, returncode = await self.process_manager.run_command(
                cmd,
                timeout=2.0,
                encoding=encoding,
                errors="replace",
                **kwargs
            )
            return str(stdout), returncode
        except asyncio.TimeoutError:
            return None, None
        except Exception as exc:
            logging.error(f"async ping command failed: {exc}")
            return None, None

    async def ping_host_async(self, host: str) -> Tuple[bool, Optional[float]]:
        """Ping a host asynchronously and return (success, latency_ms)."""
        # Basic check for ping availability
        if not self._check_ping_available():
            # todo: implement pythonping async fallback? for now just return failure or use sync fallback in executor?
            # pythonping is blocking. simpler to fail or wrap it.
            # For now, let's assume system ping is available as PER REQUIREMENTS.
            return False, None

        is_ipv6 = await self._detect_ipv6_async(host)
        
        stdout, returncode = await self._run_ping_command_async(host, is_ipv6)
        if stdout is None:
            return False, None
            
        return self._parse_ping_output(stdout, returncode)

    def _parse_ping_output(self, stdout: str, returncode: int | None = 0) -> Tuple[bool, Optional[float]]:

        """Parse ping output for latency."""
        if returncode is not None and returncode != 0:
            return False, None

        failure_patterns = [
            "request timed out",
            "unreachable",
            "заданный узел недоступен",
            "превышен интервал",
            "100% packet loss",
            "100% loss",
            "переданный",
        ]
        stdout_lower = stdout.lower()
        for pattern in failure_patterns:
            if pattern in stdout_lower:
                return False, None

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
        
        # If we got output but couldn't parse latency, assume success
        if stdout.strip():
            return True, 0.0
        return False, None


    async def extract_ttl_async(self, host: str) -> tuple[int | None, int | None]:
        """
        Extract TTL from ping response and estimate hop count asynchronously.
        
        Args:
            host: Target host to ping
            
        Returns:
            Tuple of (ttl, estimated_hops) or (None, None) on error
        """
        stdout, _ = await self._run_ping_command_async(host)
        if stdout is None:
            return None, None
        
        ttl_match = re.search(r"TTL[=:\s]+(\d+)", stdout, re.IGNORECASE)
        if ttl_match:
            ttl = int(ttl_match.group(1))
            common_initial_ttl_values = [64, 128, 255]
            estimated_hops = None
            for initial_ttl in common_initial_ttl_values:
                if ttl <= initial_ttl:
                    estimated_hops = initial_ttl - ttl
                    break
            return ttl, estimated_hops
        return None, None

    def is_available(self) -> bool:
        """Check if ping functionality is available."""
        return self._check_ping_available() or PYTHONPING_AVAILABLE
