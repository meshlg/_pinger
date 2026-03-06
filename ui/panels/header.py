"""Header panel renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel

from ui.theme import (
    ACCENT,
    ACCENT_DIM,
    BG,
    CRITICAL_BG,
    GREEN,
    LayoutTier,
    TEXT_DIM,
    WHITE,
    YELLOW,
)

try:
    from config import TARGET_IP, VERSION, t
except ImportError:
    from ...config import TARGET_IP, VERSION, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_header(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the top header bar with title, target, version, and clock."""
    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
    latest_version = snap.get("latest_version")
    version_up_to_date = snap.get("version_up_to_date", False)

    if latest_version:
        ver = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}] [{YELLOW}]→ v{latest_version}[/{YELLOW}]"
    elif version_up_to_date:
        ver = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}] [{GREEN}]✓[/{GREEN}]"
    else:
        ver = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}]"

    if tier == "compact":
        txt = (
            f"[bold {WHITE}]{t('title')}[/bold {WHITE}]  "
            f"[{ACCENT}]{TARGET_IP}[/{ACCENT}]  "
            f"[{TEXT_DIM}]{now}[/{TEXT_DIM}]"
        )
    else:
        txt = (
            f"[bold {WHITE}]{t('title')}[/bold {WHITE}]  [{TEXT_DIM}]›[/{TEXT_DIM}]  "
            f"[bold {ACCENT}]{TARGET_IP}[/bold {ACCENT}]    "
            f"[{TEXT_DIM}]│[/{TEXT_DIM}]    {ver}    "
            f"[{TEXT_DIM}]│[/{TEXT_DIM}]    [{TEXT_DIM}]{now}[/{TEXT_DIM}]"
        )
    bg_col = CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else BG
    return Panel(
        txt, border_style=ACCENT_DIM, box=box.SIMPLE, width=width,
        style=f"on {bg_col}",
        padding=(0, 1),
    )
