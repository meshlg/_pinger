"""Footer panel renderer."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel

from ui.theme import ACCENT_DIM, BG, DOT_WARN, LayoutTier, TEXT_DIM, YELLOW

try:
    from config import LOG_FILE, VERSION, t
except ImportError:
    from ...config import LOG_FILE, VERSION, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_footer(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the footer bar with log path and optional update notice."""
    log_path = LOG_FILE.replace(os.path.expanduser("~"), "~")
    txt = f"[{TEXT_DIM}]{t('footer').format(log_file=log_path)}[/{TEXT_DIM}]"
    latest_version = snap.get("latest_version")
    if latest_version:
        txt += f"    [{YELLOW}]{DOT_WARN} {t('update_available').format(current=VERSION, latest=latest_version)}[/{YELLOW}]"
    return Panel(txt, border_style=ACCENT_DIM, box=box.SIMPLE, width=width, style=f"on {BG}", padding=(0, 1))
