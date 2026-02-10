from __future__ import annotations

import sys
import threading
from datetime import datetime
from typing import Any, Dict

from config import (
    StatsDict,
    ENABLE_SOUND_ALERTS,
    ALERT_COOLDOWN,
    MAX_ACTIVE_ALERTS,
    ALERT_DISPLAY_TIME,
)


def play_alert_sound() -> None:
    if not ENABLE_SOUND_ALERTS:
        return
    try:
        if sys.platform == "win32":
            import winsound  # type: ignore

            winsound.Beep(1000, 200)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


def should_play_alert(stats_lock: threading.RLock, stats: StatsDict) -> bool:
    if not ENABLE_SOUND_ALERTS:
        return False
    with stats_lock:
        last = stats.get("last_alert_time")
    if last is None:
        return True
    return (datetime.now() - last).total_seconds() >= ALERT_COOLDOWN


def trigger_alert(stats_lock: threading.RLock, stats: StatsDict, _kind: str) -> None:
    if should_play_alert(stats_lock, stats):
        play_alert_sound()
        with stats_lock:
            stats["last_alert_time"] = datetime.now()


def add_visual_alert(
    stats_lock: threading.RLock,
    stats: StatsDict,
    message: str,
    alert_type: str = "warning",
) -> None:
    with stats_lock:
        stats.setdefault("active_alerts", []).append(
            {"message": message, "type": alert_type, "time": datetime.now()}
        )
        if len(stats["active_alerts"]) > MAX_ACTIVE_ALERTS:
            stats["active_alerts"].pop(0)


def clean_old_alerts(stats_lock: threading.RLock, stats: StatsDict) -> None:
    now = datetime.now()
    with stats_lock:
        stats["active_alerts"] = [
            a
            for a in stats.get("active_alerts", [])
            if (now - a["time"]).total_seconds() < ALERT_DISPLAY_TIME
        ]
