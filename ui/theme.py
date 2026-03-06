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

__all__ = [
    "get_theme",
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
