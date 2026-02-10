from __future__ import annotations

import sys
import logging
import statistics
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from stats_repository import StatsRepository, StatsSnapshot

from config import (
    PREDICTION_WINDOW,
    PROBLEM_HISTORY_SIZE,
    PROBLEM_LOG_SUPPRESSION_SECONDS,
    t,
)


class ProblemAnalyzer:
    """Analyzes network problems and identifies patterns."""

    def __init__(self, stats_repo: StatsRepository | None = None) -> None:
        self.problem_history: deque[Dict[str, Any]] = deque(maxlen=PROBLEM_HISTORY_SIZE)
        self._stats_repo = stats_repo

    def analyze_current_problem(self) -> str:
        """Analyze current network state and identify problem type."""
        if self._stats_repo is None:
            return t("problem_none")
        
        snap = self._stats_repo.get_snapshot()
        recent_results = self._stats_repo.get_recent_results()
        
        problem_type = t("problem_none")

        # Check for DNS problems
        dns_status = snap.get("dns_status", "")
        if dns_status == t("failed"):
            problem_type = t("problem_dns")
            self._record_problem("dns", snap)
            return problem_type

        # Check for MTU problems
        mtu_status = snap.get("mtu_status", "")
        if mtu_status in [t("mtu_low"), t("mtu_fragmented")]:
            problem_type = t("problem_mtu")
            self._record_problem("mtu", snap)
            return problem_type

        # Check for packet loss
        loss_count = recent_results.count(False)
        loss_percentage = (loss_count / len(recent_results) * 100) if recent_results else 0

        if loss_percentage > 20:
            # High packet loss - determine if ISP or local
            consecutive_losses = snap.get("consecutive_losses", 0)
            if consecutive_losses >= 10:
                problem_type = t("problem_isp")
                self._record_problem("isp", snap)
            else:
                problem_type = t("problem_local")
                self._record_problem("local", snap)
            return problem_type

        # Check for high latency
        if snap.get("success", 0) > 0:
            avg_latency = snap.get("total_latency_sum", 0) / snap.get("success", 1)
            if avg_latency > 200:
                problem_type = t("problem_isp")
                self._record_problem("isp", snap)
                return problem_type

        # Check for high jitter
        jitter = snap.get("jitter", 0)
        if jitter > 50:
            problem_type = t("problem_isp")
            self._record_problem("isp", snap)
            return problem_type

        return problem_type

    def predict_problems(self) -> str:
        """Predict likelihood of problems based on history."""
        if len(self.problem_history) < 5:
            return t("prediction_stable")

        recent_problems = list(self.problem_history)[-10:]
        problem_count = sum(1 for p in recent_problems if p.get("type") != "none")

        if problem_count >= 5:
            return t("prediction_risk")

        # Check for time-based patterns
        if len(self.problem_history) >= 20:
            current_hour = datetime.now().hour
            time_pattern_problems = [
                p for p in self.problem_history
                if p.get("timestamp") and p["timestamp"].hour == current_hour
            ]

            if len(time_pattern_problems) >= 3:
                return t("prediction_risk")

        return t("prediction_stable")

    def identify_pattern(self) -> str:
        """Identify recurring problem patterns."""
        if len(self.problem_history) < 10:
            return "..."

        problem_types = [p.get("type", "none") for p in self.problem_history]
        type_counts = {}
        for pt in problem_types:
            type_counts[pt] = type_counts.get(pt, 0) + 1

        # Find dominant problem type
        if not type_counts:
            return "..."

        dominant_type = max(type_counts, key=lambda k: type_counts[k])
        dominant_count = type_counts[dominant_type]

        if dominant_count >= len(self.problem_history) * 0.5:
            # More than 50% of problems are the same type
            type_names = {
                "isp": t("problem_isp"),
                "local": t("problem_local"),
                "dns": t("problem_dns"),
                "mtu": t("problem_mtu"),
                "none": t("problem_none"),
            }
            return type_names.get(dominant_type, t("problem_unknown"))

        return "..."

    def _record_problem(self, problem_type: str, snap: StatsSnapshot) -> None:
        """Record problem occurrence in history."""
        now = datetime.now()
        last_record = self.problem_history[-1] if self.problem_history else None

        # Suppress duplicate problems within cooldown window
        if last_record and last_record.get("type") == problem_type:
            last_ts = last_record.get("timestamp")
            if last_ts is not None:
                delta = (now - last_ts).total_seconds()
                if delta < PROBLEM_LOG_SUPPRESSION_SECONDS:
                    return

        problem_record = {
            "type": problem_type,
            "timestamp": now,
            "latency": snap.get("last_latency_ms", t("na")),
            "packet_loss": snap.get("failure", 0) / max(snap.get("total", 1), 1) * 100,
            "jitter": snap.get("jitter", 0),
        }
        self.problem_history.append(problem_record)
        logging.info(f"Problem recorded: {problem_type}")

    def get_problem_summary(self) -> Dict[str, Any]:
        """Get summary of problem history."""
        if not self.problem_history:
            return {"total": 0, "by_type": {}}

        by_type: Dict[str, int] = {}
        for p in self.problem_history:
            pt = p.get("type", "unknown")
            by_type[pt] = by_type.get(pt, 0) + 1

        return {
            "total": len(self.problem_history),
            "by_type": by_type,
        }


__all__ = ["ProblemAnalyzer"]
