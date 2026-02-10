"""
UI package for pinger.

This package provides:
- protocols: Interface definitions (DIP-compliant)

Note: MonitorUI remains in ui.py for backward compatibility.
"""

from .protocols import StatsDataProvider

__all__ = [
    "StatsDataProvider",
]
