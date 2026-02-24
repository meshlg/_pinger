"""Hop Monitor Service — auto-discover hops via traceroute and ping each periodically."""
from __future__ import annotations

import logging
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from config import (
    TARGET_IP,
    TRACEROUTE_MAX_HOPS,
    HOP_PING_TIMEOUT,
    t,
)
from infrastructure import get_process_manager


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
    # new fields for stage 1
    jitter: float = 0.0
    prev_latency: Optional[float] = None
    latency_delta: float = 0.0
    # new fields for stage 3 - geolocation
    country: str = ""
    country_code: str = ""
    asn: str = ""

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
            # new fields
            "jitter": self.jitter,
            "latency_delta": self.latency_delta,
            # for sparkline rendering - last 10 values
            "latency_history": self.latency_history[-10:] if self.latency_history else [],
            # geolocation fields
            "country": self.country,
            "country_code": self.country_code,
            "asn": self.asn,
        }


# Type alias for route health status
RouteHealth = Literal["healthy", "degraded", "critical", "unknown"]


@dataclass(frozen=True)
class RouteStats:
    """Aggregated statistics for the entire route.
    
    Provides a summary of route health and performance metrics,
    useful for dashboards, alerts, and logging.
    
    Attributes:
        hop_count: Total number of discovered hops.
        total_loss_pct: Average packet loss percentage across all hops.
        avg_latency: Average latency across all responding hops (ms).
        max_latency: Maximum latency observed on any hop (ms).
        worst_hop: Hop number with the highest packet loss.
        worst_hop_loss: Packet loss percentage on the worst hop.
        route_health: Overall route health status.
        problem_hops: List of hop numbers with significant issues.
        responding_hops: Number of hops that respond to pings.
        last_updated: Timestamp of the last statistics update.
    
    Example:
        stats = hop_monitor.get_route_stats()
        if stats.route_health == "critical":
            logging.warning(f"Route degraded: {stats.problem_hops}")
    """
    hop_count: int
    total_loss_pct: float
    avg_latency: float
    max_latency: float
    worst_hop: int
    worst_hop_loss: float
    route_health: RouteHealth
    problem_hops: Tuple[int, ...]
    responding_hops: int
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hop_count": self.hop_count,
            "total_loss_pct": round(self.total_loss_pct, 2),
            "avg_latency": round(self.avg_latency, 2) if self.avg_latency else None,
            "max_latency": round(self.max_latency, 2) if self.max_latency else None,
            "worst_hop": self.worst_hop,
            "worst_hop_loss": round(self.worst_hop_loss, 2),
            "route_health": self.route_health,
            "problem_hops": list(self.problem_hops),
            "responding_hops": self.responding_hops,
            "last_updated": self.last_updated.isoformat(),
        }
    
    def __bool__(self) -> bool:
        """Return True if route has any discovered hops."""
        return self.hop_count > 0


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
        self._rediscovery_requested = threading.Event()
        self._on_hop_callback = None  # called when a new hop is discovered
        self._geo_service = None  # lazy-loaded geolocation service
        self.process_manager = get_process_manager()

    def enable_geo(self) -> None:
        """Enable geolocation lookups for hops."""
        if self._geo_service is None:
            from .geo_service import GeoService
            self._geo_service = GeoService()
            logging.info("Hop geolocation enabled")

    # ── Discovery ──

    def set_on_hop_callback(self, callback) -> None:
        """Set callback(hops_snapshot) called each time a new hop is discovered."""
        self._on_hop_callback = callback

    def request_rediscovery(self) -> None:
        """Request immediate hop re-discovery (e.g. on IP change)."""
        logging.info("Hop re-discovery requested (IP change detected)")
        self._rediscovery_requested.set()

    @property
    def rediscovery_requested(self) -> bool:
        return self._rediscovery_requested.is_set()

    def clear_rediscovery(self) -> None:
        self._rediscovery_requested.clear()

    async def discover_hops(self, target: str) -> List[HopStatus]:
        """Run traceroute with streaming output — hops appear instantly."""
        self._discovering = True
        self._rediscovery_requested.clear()
        try:
            logging.info(f"Starting hop discovery for target: {target}")
            with self._lock:
                self._hops = []

            hops = await self._run_traceroute_streaming(target)

            logging.info(f"Hop discovery complete: {len(hops)} hops")
            with self._lock:
                self._hops = hops
                self._discovered = True
                self._last_discovery = time.time()
            
            # Fetch geolocation for all discovered hops (in background)
            if self._geo_service is not None:
                for hop in hops:
                    self._update_hop_geo(hop)
            
            return hops
        except Exception as exc:
            logging.error(f"Hop discovery failed: {exc}", exc_info=True)
            return []
        finally:
            self._discovering = False

    async def _run_traceroute_streaming(self, target: str) -> List[HopStatus]:
        """Run traceroute and parse hops line-by-line as they appear."""
        if sys.platform == "win32":
            # Windows: -d (do not resolve addresses) speed up discovery significantly!
            cmd = ["tracert", "-d", "-h", str(TRACEROUTE_MAX_HOPS), "-w", "500", target]
            encoding = "oem"
        else:
            tr = shutil.which("traceroute")
            if not tr:
                return []
            # Linux: -n (do not resolve addresses)
            cmd = ["traceroute", "-n", "-m", str(TRACEROUTE_MAX_HOPS), "-w", "1", target]
            encoding = "utf-8"

        hops: List[HopStatus] = []
        seen_ips: set = set()

        try:
            # Use creationflags on Windows to prevent orphan processes
            popen_kwargs: dict[str, Any] = {}
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

            # Use ProcessManager to create process
            proc = await self.process_manager.create_process(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **popen_kwargs,
            )
            
            # self._active_proc = proc # ProcessManager handles tracking now

            deadline = time.time() + 60

            if proc.stdout is None:
                return hops

            # Read line by line asynchronously
            while True:
                if time.time() > deadline:
                     logging.warning("Traceroute streaming timeout, stopping")
                     proc.terminate()
                     break
                
                try:
                    line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
                except asyncio.TimeoutError:
                    # No output for 5 seconds? check if process is done
                    if proc.returncode is not None:
                        break
                    continue
                
                if not line_bytes:
                    break

                line = line_bytes.decode(encoding, errors="replace").strip()
                if not line:
                    continue

                hop = self._parse_single_line(line, seen_ips)
                if hop:
                    hops.append(hop)
                    # Trigger async hostname resolution for this hop
                    self._resolve_hostname_bg(hop)
                    
                    # Update hops list immediately so UI sees new hop
                    with self._lock:
                        self._hops = list(hops)
                    if self._on_hop_callback:
                        try:
                            self._on_hop_callback(self.get_hops_snapshot())
                        except Exception:
                            pass
                    logging.debug(f"Hop {hop.hop_number}: {hop.ip} (resolving...)")

            await proc.wait()
        except Exception as exc:
            logging.error(f"Traceroute exec failed: {exc}")
        finally:
             # IMPORTANT: Unregister process to prevent memory leak and release semaphore
             if 'proc' in locals():
                 await self.process_manager.unregister(proc)

        logging.debug(f"Total hops parsed: {len(hops)}")
        return hops

    def _resolve_hostname_bg(self, hop: HopStatus) -> None:
        """Resolve hostname in background."""
        
        def _resolve():
            import socket
            try:
                # This blocks, so run in executor
                hostname, _, _ = socket.gethostbyaddr(hop.ip)
                if hostname:
                    with self._lock:
                        hop.hostname = hostname
                    # Notify UI of update
                    if self._on_hop_callback:
                        try:
                            self._on_hop_callback(self.get_hops_snapshot())
                        except Exception:
                            pass
            except Exception:
                pass # Hostname resolution failed, keep IP

        self._executor.submit(_resolve)

    def _parse_single_line(self, line: str, seen_ips: set) -> Optional[HopStatus]:
        """Parse a single traceroute output line into a HopStatus or None."""
        hop_match = re.match(r"^\s*(\d+)\s+", line)
        if not hop_match:
            return None

        hop_num = int(hop_match.group(1))

        # Skip lines with only timeouts
        if re.fullmatch(r"\s*\d+\s+(\*\s*)+", line):
            return None

        # Extract IP address
        ip_match = re.search(r"\[?((?:\d{1,3}\.){3}\d{1,3})\]?", line)
        if not ip_match:
            return None

        ip = ip_match.group(1)

        # Skip duplicate IPs and target IP itself
        if ip in seen_ips or ip == TARGET_IP:
            return None
        seen_ips.add(ip)

        # Extract hostname (text before IP in brackets, or IP itself)
        hostname_match = re.search(r"(\S+)\s+\[" + re.escape(ip) + r"\]", line)
        hostname = hostname_match.group(1) if hostname_match else ip

        return HopStatus(hop_number=hop_num, ip=ip, hostname=hostname)

    # ── Ping hops ──



    async def ping_all_hops(self) -> None:
        """Ping each discovered hop in parallel and update status."""
        with self._lock:
            hops = list(self._hops)

        if not hops:
            return

        # Limit concurrency to avoid starving the main ping/traceroute
        # Global limit is 50 (ProcessManager), so 20 leaves plenty of headroom
        sem = asyncio.Semaphore(20)

        async def _ping_with_limit(hop_ip: str) -> Tuple[bool, Optional[float]]:
            async with sem:
                return await self._ping_host(hop_ip)

        # Ping all hops in parallel but limited by semaphore
        tasks = [_ping_with_limit(hop.ip) for hop in hops]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for hop, result in zip(hops, results):
            try:
                if isinstance(result, Exception):
                    logging.debug(f"Hop ping failed for {hop.ip}: {result}")
                    self._update_hop_status(hop, False, None)
                else:
                    if result:
                        ok, latency = result
                        self._update_hop_status(hop, ok, latency)
                    else:
                        self._update_hop_status(hop, False, None)
            except Exception as exc:
                logging.debug(f"Error updating hop status: {exc}")

    async def _ping_host(self, ip: str) -> Tuple[bool, Optional[float]]:
        """Single ping to a hop IP with fast timeout."""
        try:
            if sys.platform == "win32":
                # Windows: -w is timeout in milliseconds
                cmd = ["ping", "-n", "1", "-w", str(int(HOP_PING_TIMEOUT * 1000)), ip]
                encoding = "oem"
            else:
                # Linux/Mac: -W is timeout in seconds
                cmd = ["ping", "-c", "1", "-W", str(HOP_PING_TIMEOUT), ip]
                encoding = "utf-8"

            # Use creationflags on Windows to prevent orphan processes
            run_kwargs: dict[str, Any] = {}
            if sys.platform == "win32":
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

            # Use ProcessManager
            stdout, _, returncode = await self.process_manager.run_command(
                cmd,
                timeout=HOP_PING_TIMEOUT + 0.5,
                encoding=encoding,
                errors="replace",
                **run_kwargs,
            )
            
            stdout_str = str(stdout)

            match_time = re.search(
                r"(?:time|время)\s*[=<>]*\s*([0-9]+[.,]?[0-9]*)",
                stdout_str,
                re.IGNORECASE,
            )
            if match_time:
                return True, float(match_time.group(1).replace(",", "."))

            if re.search(r"time\s*<\s*1\s*(?:ms|мс)?", stdout_str, re.IGNORECASE):
                return True, 0.5

            if returncode == 0:
                return True, 0.0
            return False, None

        except (asyncio.TimeoutError, Exception):
            return False, None

    def _update_hop_status(self, hop: HopStatus, ok: bool, latency: Optional[float]) -> None:
        """Update hop stats after ping."""
        with self._lock:
            hop.total_pings += 1
            hop.last_ok = ok
            if ok and latency is not None:
                hop.last_latency = latency
                
                # Calculate delta (change vs previous ping)
                if hop.prev_latency is not None:
                    hop.latency_delta = latency - hop.prev_latency
                hop.prev_latency = latency
                
                # Add to history and maintain size limit
                hop.latency_history.append(latency)
                if len(hop.latency_history) > self.LATENCY_HISTORY_SIZE:
                    hop.latency_history = hop.latency_history[-self.LATENCY_HISTORY_SIZE:]
                
                # Update min/max
                hop.min_latency = min(hop.min_latency, latency)
                hop.max_latency = max(hop.max_latency, latency)
                
                # Calculate avg
                hop.avg_latency = sum(hop.latency_history) / len(hop.latency_history)
                
                # Calculate jitter (standard deviation) when we have enough samples
                if len(hop.latency_history) >= 2:
                    hop.jitter = statistics.stdev(hop.latency_history)
            else:
                hop.loss_count += 1
                hop.last_latency = None
                # Reset delta on failure
                hop.latency_delta = 0.0

    def _update_hop_geo(self, hop: HopStatus) -> None:
        """Update geolocation for a hop (if enabled and not already set)."""
        if self._geo_service is None:
            return
        if hop.country_code:  # Already have geo data
            return
        
        # Run in background to not block ping loop
        def _fetch_geo():
            try:
                info = self._geo_service.get_geo(hop.ip)
                if info:
                    with self._lock:
                        hop.country = info.country
                        hop.country_code = info.country_code
                        hop.asn = info.asn
            except Exception as exc:
                logging.debug(f"Geo fetch failed for {hop.ip}: {exc}")
        
        # Schedule geo lookup in background
        self._executor.submit(_fetch_geo)

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
    
    def get_route_stats(self) -> RouteStats:
        """Get aggregated statistics for the entire route.
        
        Calculates summary metrics across all discovered hops including
        overall health status, average latency, packet loss, and identifies
        problematic hops.
        
        Returns:
            RouteStats with aggregated route metrics.
        
        Example:
            stats = hop_monitor.get_route_stats()
            print(f"Route: {stats.hop_count} hops, health: {stats.route_health}")
            if stats.problem_hops:
                print(f"Problem hops: {stats.problem_hops}")
        """
        with self._lock:
            hops = list(self._hops)
        
        now = datetime.now(timezone.utc)
        
        # No hops discovered yet
        if not hops:
            return RouteStats(
                hop_count=0,
                total_loss_pct=0.0,
                avg_latency=0.0,
                max_latency=0.0,
                worst_hop=0,
                worst_hop_loss=0.0,
                route_health="unknown",
                problem_hops=(),
                responding_hops=0,
                last_updated=now,
            )
        
        # Calculate aggregated metrics
        total_loss = 0.0
        total_latency = 0.0
        max_latency = 0.0
        responding_hops = 0
        worst_hop = 0
        worst_hop_loss = 0.0
        problem_hops: list[int] = []
        
        for hop in hops:
            loss_pct = hop.loss_pct
            total_loss += loss_pct
            
            if hop.avg_latency > 0:
                total_latency += hop.avg_latency
                responding_hops += 1
            
            if hop.max_latency > max_latency:
                max_latency = hop.max_latency
            
            # Track worst hop by loss percentage
            if loss_pct > worst_hop_loss:
                worst_hop_loss = loss_pct
                worst_hop = hop.hop_number
            
            # Mark as problem hop if loss > 5%
            if loss_pct > 5.0:
                problem_hops.append(hop.hop_number)
        
        # Calculate averages
        avg_loss = total_loss / len(hops) if hops else 0.0
        avg_latency = total_latency / responding_hops if responding_hops else 0.0
        
        # Determine route health
        if responding_hops == 0:
            health: RouteHealth = "unknown"
        elif avg_loss < 1.0 and not problem_hops:
            health = "healthy"
        elif avg_loss < 5.0 and len(problem_hops) <= 1:
            health = "degraded"
        else:
            health = "critical"
        
        return RouteStats(
            hop_count=len(hops),
            total_loss_pct=avg_loss,
            avg_latency=avg_latency,
            max_latency=max_latency,
            worst_hop=worst_hop,
            worst_hop_loss=worst_hop_loss,
            route_health=health,
            problem_hops=tuple(problem_hops),
            responding_hops=responding_hops,
            last_updated=now,
        )
