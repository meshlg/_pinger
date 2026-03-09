"""Header panel renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import ACCENT, ACCENT_DIM, BG, CRITICAL_BG, LayoutTier, TEXT_DIM, WHITE, YELLOW

try:
    from config import TARGET_IP, VERSION, t
except ImportError:
    from ...config import TARGET_IP, VERSION, t  # type: ignore[no-redef]

if TYPE_CHECKING:
    from stats_repository import StatsSnapshot


def render_header(snap: StatsSnapshot, width: int, tier: LayoutTier) -> Panel:
    """Render the top identity bar with target, version, and live clock."""
    now = datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")
    latest_version = snap.get("latest_version")
    version_up_to_date = snap.get("version_up_to_date", False)
    public_ip = snap.get("public_ip") or t("na")
    country = snap.get("country")
    country_code = snap.get("country_code")
    # Show full country name if available, otherwise show country code, otherwise just IP
    if country and country != "..." and country != "N/A":
        location = f"{public_ip} ({country})"
    elif country_code:
        location = f"{public_ip} [{country_code}]"
    else:
        location = str(public_ip)

    if latest_version:
        version_text = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}] [{YELLOW}]{t('ui_update')} {latest_version}[/{YELLOW}]"
    elif version_up_to_date:
        version_text = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}] [{ACCENT}]{t('version_up_to_date')}[/{ACCENT}]"
    else:
        version_text = f"[{TEXT_DIM}]v{VERSION}[/{TEXT_DIM}]"

    title = Text.from_markup(
        f"[bold {ACCENT}]{t('ui_app_name')}[/bold {ACCENT}] - "
        f"[bold {WHITE}]{t('title')}[/bold {WHITE}] "
        f"[bold {YELLOW}]{TARGET_IP}[/bold {YELLOW}]"
    )

    if tier == "compact":
        body = Text.from_markup(
            f"[bold {WHITE}]{t('title')}[/bold {WHITE}] "
            f"[{ACCENT}]{TARGET_IP}[/{ACCENT}] "
            f"[{TEXT_DIM}]|[/{TEXT_DIM}] "
            f"[{TEXT_DIM}]{now}[/{TEXT_DIM}]"
        )
    else:
        grid = Table.grid(expand=True)
        grid.add_column(ratio=3)
        grid.add_column(ratio=2, justify="right")
        grid.add_row(title, Text.from_markup(version_text))
        grid.add_row(
            Text.from_markup(f"[{TEXT_DIM}]{t('ui_live_target')}:[/{TEXT_DIM}] [{WHITE}]{location}[/{WHITE}]"),
            Text.from_markup(f"[{TEXT_DIM}]{t('ui_local_time')}:[/{TEXT_DIM}] [{WHITE}]{now}[/{WHITE}]"),
        )
        body = grid

    bg_color = CRITICAL_BG if snap.get("threshold_states", {}).get("connection_lost") else BG
    return Panel(
        body,
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        width=width,
        style=f"on {bg_color}",
        padding=(0, 1),
    )
