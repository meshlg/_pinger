"""Style constants, Unicode elements, and color palette for the UI."""

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

# ═══════════════════════════════════════════════════════════════════════════════
# Theme instance
# NOTE: Theme is resolved once at import time from the UI_THEME env variable.
# For runtime theme switching, call reload_theme().
# ═══════════════════════════════════════════════════════════════════════════════

theme = get_theme(UI_THEME)

# ═══════════════════════════════════════════════════════════════════════════════
# Color palette – dynamic from theme
# ═══════════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════════
# Unicode elements
# ═══════════════════════════════════════════════════════════════════════════════

SPARK_CHARS = "▁▂▃▄▅▆▇█"
BAR_FULL = "━"
BAR_EMPTY = "╌"
DOT_OK = "●"
DOT_WARN = "▲"
DOT_WAIT = "○"

# ═══════════════════════════════════════════════════════════════════════════════
# Layout tier type aliases
# ═══════════════════════════════════════════════════════════════════════════════

LayoutTier = Literal["compact", "standard", "wide"]
HeightTier = Literal["minimal", "short", "standard", "full"]


def reload_theme(theme_name: str | None = None) -> None:
    """Reload the theme at runtime, updating all module-level color constants.

    Args:
        theme_name: Theme name to load. If None, re-reads UI_THEME from config.
    """
    global theme, BG, BG_PANEL, ACCENT, ACCENT_DIM, TEXT, TEXT_DIM
    global GREEN, YELLOW, RED, WHITE, CRITICAL_BG

    if theme_name is None:
        try:
            from config import UI_THEME as _current_theme
        except ImportError:
            from ..config import UI_THEME as _current_theme  # type: ignore[no-redef]
        theme_name = _current_theme

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
