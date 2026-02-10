"""
Legacy config.py - Backward compatibility wrapper.

This file re-exports everything from the config/ package for backward compatibility.
All new code should import directly from the config package:

    from config import VERSION, TARGET_IP, t, create_stats
    # or
    from config.settings import VERSION, TARGET_IP
    from config.i18n import t, LANG
    from config.types import create_stats, StatsDict
"""

# Re-export everything from the config package
from config.settings import *  # noqa: F401, F403
from config.i18n import LANG, t, CURRENT_LANGUAGE, SUPPORTED_LANGUAGES  # noqa: F401
from config.types import (  # noqa: F401
    ThresholdStates,
    StatsDict,
    create_stats,
    create_recent_results,
)

__all__ = [
    "VERSION",
    "TARGET_IP",
    "INTERVAL",
    "WINDOW_SIZE",
    "LATENCY_WINDOW",
    "CURRENT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "LANG",
    "t",
    "ThresholdStates",
    "StatsDict",
    "create_stats",
    "create_recent_results",
]
