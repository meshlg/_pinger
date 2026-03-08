"""Footer panel renderer."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG, LayoutTier, TEXT_DIM, YELLOW

try:
    from config import LOG_FILE, VERSION, t
except ImportError:
    from ...config import LOG_FILE, VERSION, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_footer(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the lower status rail with log path and update state."""
    log_path = LOG_FILE.replace(os.path.expanduser("~"), "~")
    body = Text.from_markup(f"[{TEXT_DIM}]{t('footer').format(log_file=log_path)}[/{TEXT_DIM}]")

    latest_version = snap.get("latest_version")
    if latest_version:
        body.append("  |  ", style=ACCENT)
        body.append(f"v{VERSION} -> v{latest_version}", style=YELLOW)

    return Panel(
        body,
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {BG}",
        padding=(0, 1),
    )
