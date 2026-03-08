"""Toast notification panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel

from ui.theme import ACCENT, BG, GREEN, RED, WHITE, YELLOW
from ui.helpers import truncate

try:
    from config import SHOW_VISUAL_ALERTS, t
except ImportError:
    from ...config import SHOW_VISUAL_ALERTS, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_toast(snap: StatsSnapshot, width: int) -> Panel | None:
    """Render toast notification panel with improved visual design."""
    if not SHOW_VISUAL_ALERTS or not snap.get("active_alerts"):
        return None

    alerts = snap["active_alerts"]

    # Map alert types to visual styles and priority order
    type_styles = {
        "critical": {
            "icon": "⚠",
            "bg": RED,
            "fg": WHITE,
            "prefix": "║ CRITICAL ║",
            "priority": 0,
        },
        "warning": {
            "icon": "⚡",
            "bg": YELLOW,
            "fg": BG,
            "prefix": "│",
            "priority": 1,
        },
        "info": {
            "icon": "●",
            "bg": ACCENT,
            "fg": BG,
            "prefix": "│",
            "priority": 2,
        },
        "success": {
            "icon": "✓",
            "bg": GREEN,
            "fg": BG,
            "prefix": "│",
            "priority": 3,
        },
    }

    # Sort alerts by priority (critical first)
    def get_priority(alert: dict) -> int:
        alert_type = alert.get("type", "info")
        return type_styles.get(alert_type, type_styles["info"])["priority"]

    sorted_alerts = sorted(alerts, key=get_priority)
    primary = sorted_alerts[0]
    style = type_styles.get(primary["type"], type_styles["info"])

    # Build toast content
    parts: list[str] = []

    # Primary alert with bold styling
    icon = style["icon"]
    bg_col = style["bg"]
    fg_col = style["fg"]

    # Truncate message if too long
    max_msg_len = width - 8
    msg = truncate(primary["message"], max_msg_len)

    # Main toast line with visual emphasis
    if primary["type"] == "critical":
        # Critical alerts get extra visual weight
        txt = f"[bold {fg_col}]  {icon} {msg}  [/bold {fg_col}]"
    else:
        txt = f"[bold {fg_col}]{icon} {msg}[/bold {fg_col}]"

    parts.append(txt)

    # Show count if multiple alerts
    if len(alerts) > 1:
        more_count = len(alerts) - 1
        more_txt = f"  [{fg_col}]+{more_count} {t('more_alerts')}[/{fg_col}]"
        parts.append(more_txt)

    content = "\n".join(parts)

    # Use themed border for visual distinction
    border_style = bg_col
    box_style = box.HEAVY if primary["type"] == "critical" else box.ROUNDED

    return Panel(
        content,
        border_style=border_style,
        box=box_style,
        width=width,
        style=f"on {bg_col}",
        padding=(0, 1),
    )
