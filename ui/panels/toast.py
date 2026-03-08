"""Toast notification panel renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.text import Text

from ui.theme import ACCENT, BG, GREEN, RED, WHITE, YELLOW
from ui.helpers import truncate

try:
    from config import SHOW_VISUAL_ALERTS, t
except ImportError:
    from ...config import SHOW_VISUAL_ALERTS, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


ALERT_STYLES = {
    "critical": {"icon": "!", "bg": RED, "fg": WHITE, "priority": 0},
    "warning": {"icon": "^", "bg": YELLOW, "fg": BG, "priority": 1},
    "info": {"icon": "i", "bg": ACCENT, "fg": BG, "priority": 2},
    "success": {"icon": "+", "bg": GREEN, "fg": BG, "priority": 3},
}


def render_toast(snap: StatsSnapshot, width: int) -> Panel | None:
    """Render an alert banner with restrained, premium styling."""
    if not SHOW_VISUAL_ALERTS or not snap.get("active_alerts"):
        return None

    alerts = sorted(
        snap["active_alerts"],
        key=lambda alert: ALERT_STYLES.get(alert.get("type", "info"), ALERT_STYLES["info"])["priority"],
    )
    primary = alerts[0]
    style = ALERT_STYLES.get(primary.get("type", "info"), ALERT_STYLES["info"])

    msg = truncate(primary.get("message", ""), max(20, width - 12))
    text = Text(f" {style['icon']} {msg} ", style=f"bold {style['fg']}")
    if len(alerts) > 1:
        text.append(" ")
        text.append(f"+{len(alerts) - 1} {t('more_alerts')}", style=style["fg"])

    return Panel(
        text,
        border_style=style["bg"],
        box=box.ROUNDED,
        width=width,
        style=f"on {style['bg']}",
        padding=(0, 1),
    )
