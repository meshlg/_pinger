from __future__ import annotations

import sys
import logging
import re
import statistics
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import (
    HOP_TIMEOUT_THRESHOLD,
    ROUTE_HISTORY_SIZE,
    t,
)


class RouteAnalyzer:
    """Analyzes network routes and identifies problematic hops."""

    def __init__(self) -> None:
        self.route_history: deque[Dict[str, Any]] = deque(maxlen=ROUTE_HISTORY_SIZE)
        self.last_route: List[Dict[str, Any]] = []

    def parse_traceroute_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse traceroute output and extract hop information."""
        hops = []
        lines = output.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("Traceroute") or line.startswith("Hops"):
                continue

            # Parse hop number and latency
            hop_match = re.search(r"^\s*(\d+)\s+([^\s]+)", line)
            if not hop_match:
                continue

            hop_num = int(hop_match.group(1))
            ip_or_host = hop_match.group(2)

            # Extract latencies (multiple probes per hop)
            latency_matches = re.findall(r"(\d+(?:\.\d+)?)\s*ms", line)
            latencies = [float(l) for l in latency_matches]

            if latencies:
                avg_latency = statistics.mean(latencies)
                max_latency = max(latencies)
            else:
                avg_latency = None
                max_latency = None

            # Check for timeout
            is_timeout = "*" in line or "Request timed out" in line

            hops.append({
                "hop": hop_num,
                "ip": ip_or_host,
                "latencies": latencies,
                "avg_latency": avg_latency,
                "max_latency": max_latency,
                "is_timeout": is_timeout,
            })

        return hops

    def identify_problematic_hop(self, hops: List[Dict[str, Any]]) -> Optional[int]:
        """Identify the problematic hop in the route.
        
        Avoids false positives: single timeout hops are common (routers that
        don't respond to ICMP) and are NOT considered problematic by themselves.
        """
        consecutive_timeouts = 0
        for hop in hops:
            is_timeout = hop.get("is_timeout", False)
            latencies = hop.get("latencies", [])

            # Track consecutive timeout-only hops (2+ in a row = real problem)
            if is_timeout and not latencies:
                consecutive_timeouts += 1
                if consecutive_timeouts >= 2:
                    return hop["hop"]
                continue
            else:
                consecutive_timeouts = 0

            # Check for high latency
            avg_latency = hop.get("avg_latency")
            if avg_latency and avg_latency > HOP_TIMEOUT_THRESHOLD:
                return hop["hop"]

            # Check for high variance in latencies
            if len(latencies) >= 2:
                variance = statistics.stdev(latencies)
                if variance > 100:  # High variance
                    return hop["hop"]

        return None

    def compare_routes(self, current_route: List[Dict[str, Any]]) -> tuple[bool, int, list[int]]:
        """Compare current route with previous route and return (changed, diff_count, diff_indices)."""
        if not self.last_route:
            self.last_route = current_route
            return False, 0, []

        diff_indices: list[int] = []
        min_len = min(len(current_route), len(self.last_route))
        for i in range(min_len):
            if current_route[i].get("ip") != self.last_route[i].get("ip"):
                diff_indices.append(i)

        # Account for length differences
        if len(current_route) != len(self.last_route):
            for i in range(min_len, max(len(current_route), len(self.last_route))):
                diff_indices.append(i)

        changed = bool(diff_indices)
        self.last_route = current_route
        return changed, len(diff_indices), diff_indices

    def analyze_route(self, hops: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze route and return analysis results."""
        problematic_hop = self.identify_problematic_hop(hops)
        changed, diff_count, diff_indices = self.compare_routes(hops)

        # Calculate average latency across all hops
        latencies: list[float] = [h["avg_latency"] for h in hops if h.get("avg_latency") is not None]
        avg_route_latency = statistics.mean(latencies) if latencies else None

        # Save route to history
        route_record = {
            "timestamp": datetime.now(timezone.utc),
            "hops": hops,
            "hop_count": len(hops),
            "problematic_hop": problematic_hop,
            "avg_latency": avg_route_latency,
            "route_changed": changed,
            "diff_count": diff_count,
            "diff_indices": diff_indices,
        }
        self.route_history.append(route_record)

        return {
            "hops": hops,
            "hop_count": len(hops),
            "problematic_hop": problematic_hop,
            "route_changed": changed,
            "avg_latency": avg_route_latency,
            "diff_count": diff_count,
            "diff_indices": diff_indices,
        }

    def get_route_summary(self) -> Dict[str, Any]:
        """Get summary of route history."""
        if not self.route_history:
            return {"total": 0, "avg_hop_count": 0, "changes": 0}

        total_routes = len(self.route_history)
        hop_counts = [r.get("hop_count", 0) for r in self.route_history]
        avg_hop_count = statistics.mean(hop_counts) if hop_counts else 0

        # Count route changes
        changes = sum(1 for r in self.route_history if r.get("route_changed", False))

        return {
            "total": total_routes,
            "avg_hop_count": avg_hop_count,
            "changes": changes,
        }


__all__ = ["RouteAnalyzer"]
