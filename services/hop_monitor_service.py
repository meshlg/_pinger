"""Hop Monitor Service — auto-discover hops via traceroute and ping each periodically."""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config import TARGET_IP, TRACEROUTE_MAX_HOPS, t


@dataclass
class HopStatus:
    """Status of a single hop."""
    hop_number: int
    ip: str
    hostname: str
    last_latency: Optional[float] = None
    avg_latency: float = 0.0
    min_latency: float = float("inf")
    max_latency: float = 0.0
    loss_count: int = 0
    total_pings: int = 0
    last_ok: bool = True
    latency_history: list = field(default_factory=list)

    @property
    def loss_pct(self) -> float:
        return (self.loss_count / self.total_pings * 100) if self.total_pings else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hop": self.hop_number,
            "ip": self.ip,
            "hostname": self.hostname,
            "last_latency": self.last_latency,
            "avg_latency": self.avg_latency,
            "min_latency": self.min_latency if self.min_latency != float("inf") else None,
            "max_latency": self.max_latency,
            "loss_pct": self.loss_pct,
            "total_pings": self.total_pings,
            "last_ok": self.last_ok,
        }


class HopMonitorService:
    """Service that discovers hops via traceroute and monitors each with ping."""

    LATENCY_HISTORY_SIZE = 30

    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self._executor = executor
        self._lock = threading.RLock()
        self._hops: List[HopStatus] = []
        self._discovered = False
        self._discovering = False
        self._last_discovery: float = 0.0

    # ── Discovery ──

    def discover_hops(self, target: str) -> List[HopStatus]:
        """Run traceroute and parse hops."""
        self._discovering = True
        try:
            output = self._run_traceroute(target)
            hops = self._parse_hops(output)
            with self._lock:
                self._hops = hops
                self._discovered = True
                self._last_discovery = time.time()
            logging.info(f"Hop discovery: found {len(hops)} hops")
            return hops
        except Exception as exc:
            logging.error(f"Hop discovery failed: {exc}")
            return []
        finally:
            self._discovering = False

    def _run_traceroute(self, target: str) -> str:
        """Run traceroute command."""
        if sys.platform == "win32":
            cmd = ["tracert", "-h", str(TRACEROUTE_MAX_HOPS), "-w", "1000", target]
            encoding = "oem"
        else:
            tr = shutil.which("traceroute")
            if not tr:
                return ""
            cmd = ["traceroute", "-m", str(TRACEROUTE_MAX_HOPS), "-w", "1", target]
            encoding = "utf-8"

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding=encoding,
                errors="replace",
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return ""
        except Exception as exc:
            logging.error(f"Traceroute exec failed: {exc}")
            return ""

    def _parse_hops(self, output: str) -> List[HopStatus]:
        """Parse traceroute output into HopStatus list."""
        hops: List[HopStatus] = []
        seen_ips: set = set()

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            hop_match = re.match(r"^\s*(\d+)\s+", line)
            if not hop_match:
                continue

            hop_num = int(hop_match.group(1))

            # Skip lines with only timeouts
            if re.fullmatch(r"\s*\d+\s+(\*\s*)+", line):
                continue

            # Extract IP address
            ip_match = re.search(r"\[?((?:\d{1,3}\.){3}\d{1,3})\]?", line)
            if not ip_match:
                continue

            ip = ip_match.group(1)

            # Skip duplicate IPs and target IP itself
            if ip in seen_ips or ip == TARGET_IP:
                continue
            seen_ips.add(ip)

            # Extract hostname (text before IP in brackets, or IP itself)
            hostname_match = re.search(r"(\S+)\s+\[" + re.escape(ip) + r"\]", line)
            hostname = hostname_match.group(1) if hostname_match else ip

            hops.append(HopStatus(
                hop_number=hop_num,
                ip=ip,
                hostname=hostname,
            ))

        return hops

    # ── Ping hops ──

    def ping_all_hops(self) -> None:
        """Ping each discovered hop and update status."""
        with self._lock:
            hops = list(self._hops)

        for hop in hops:
            ok, latency = self._ping_host(hop.ip)
            self._update_hop_status(hop, ok, latency)

    def _ping_host(self, ip: str) -> Tuple[bool, Optional[float]]:
        """Single ping to a hop IP."""
        try:
            if sys.platform == "win32":
                cmd = ["ping", "-n", "1", "-w", "1000", ip]
                encoding = "oem"
            else:
                cmd = ["ping", "-c", "1", "-W", "1", ip]
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

            match_time = re.search(
                r"(?:time|время)\s*[=<>]*\s*([0-9]+[.,]?[0-9]*)",
                stdout,
                re.IGNORECASE,
            )
            if match_time:
                return True, float(match_time.group(1).replace(",", "."))

            if re.search(r"time\s*<\s*1\s*(?:ms|мс)?", stdout, re.IGNORECASE):
                return True, 0.5

            if result.returncode == 0:
                return True, 0.0
            return False, None

        except (subprocess.TimeoutExpired, Exception):
            return False, None

    def _update_hop_status(self, hop: HopStatus, ok: bool, latency: Optional[float]) -> None:
        """Update hop stats after ping."""
        with self._lock:
            hop.total_pings += 1
            hop.last_ok = ok
            if ok and latency is not None:
                hop.last_latency = latency
                hop.latency_history.append(latency)
                if len(hop.latency_history) > self.LATENCY_HISTORY_SIZE:
                    hop.latency_history = hop.latency_history[-self.LATENCY_HISTORY_SIZE:]
                hop.min_latency = min(hop.min_latency, latency)
                hop.max_latency = max(hop.max_latency, latency)
                hop.avg_latency = sum(hop.latency_history) / len(hop.latency_history)
            else:
                hop.loss_count += 1
                hop.last_latency = None

    # ── Public API ──

    def get_hops_snapshot(self) -> List[Dict[str, Any]]:
        """Get immutable snapshot of all hops for UI."""
        with self._lock:
            return [h.to_dict() for h in self._hops]

    @property
    def is_discovered(self) -> bool:
        return self._discovered

    @property
    def is_discovering(self) -> bool:
        return self._discovering

    @property
    def hop_count(self) -> int:
        with self._lock:
            return len(self._hops)
