from __future__ import annotations

import sys


def play_alert_sound() -> None:
    """Play alert sound (platform-dependent)."""
    from config import ENABLE_SOUND_ALERTS
    
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
