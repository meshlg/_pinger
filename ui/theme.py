"""Theme constants and shared visual primitives for the terminal UI."""

from __future__ import annotations

from typing import Literal

try:
    from config import UI_THEME
except ImportError:
    from ..config import UI_THEME  # type: ignore[no-redef]

try:
    from config.ui_theme import get_theme
except ImportError:
    from ..config.ui_theme import get_theme  # type: ignore[assignment]

theme = get_theme(UI_THEME)

BG = theme.bg
BG_PANEL = theme.bg_panel
ACCENT = theme.accent
ACCENT_DIM = theme.accent_dim
TEXT = theme.text
TEXT_DIM = theme.text_dim
GREEN = theme.green
YELLOW = theme.yellow
RED = theme.red
WHITE = theme.white
CRITICAL_BG = theme.critical_bg

# Keep the source ASCII-only while still rendering premium-looking glyphs.
SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
BAR_FULL = "\u2588"
BAR_EMPTY = "\u2591"
DOT_OK = "\u25cf"
DOT_WARN = "\u25b2"
DOT_WAIT = "\u25cb"

LayoutTier = Literal["compact", "standard", "wide"]
HeightTier = Literal["minimal", "short", "standard", "full"]


def reload_theme(theme_name: str | None = None) -> None:
    """Reload the active theme and update module-level color constants."""
    global theme, BG, BG_PANEL, ACCENT, ACCENT_DIM, TEXT, TEXT_DIM
    global GREEN, YELLOW, RED, WHITE, CRITICAL_BG

    if theme_name is None:
        try:
            from config import UI_THEME as current_theme
        except ImportError:
            from ..config import UI_THEME as current_theme  # type: ignore[no-redef]
        theme_name = current_theme

    theme = get_theme(theme_name)
    BG = theme.bg
    BG_PANEL = theme.bg_panel
    ACCENT = theme.accent
    ACCENT_DIM = theme.accent_dim
    TEXT = theme.text
    TEXT_DIM = theme.text_dim
    GREEN = theme.green
    YELLOW = theme.yellow
    RED = theme.red
    WHITE = theme.white
    CRITICAL_BG = theme.critical_bg


__all__ = [
    "get_theme",
    "reload_theme",
    "UI_THEME",
    "theme",
    "BG",
    "BG_PANEL",
    "ACCENT",
    "ACCENT_DIM",
    "TEXT",
    "TEXT_DIM",
    "GREEN",
    "YELLOW",
    "RED",
    "WHITE",
    "CRITICAL_BG",
    "SPARK_CHARS",
    "BAR_FULL",
    "BAR_EMPTY",
    "DOT_OK",
    "DOT_WARN",
    "DOT_WAIT",
    "LayoutTier",
    "HeightTier",
]
