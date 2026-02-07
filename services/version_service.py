"""Version check service - queries GitHub for latest release."""
import requests
import logging
from typing import Optional

from config import VERSION


def get_latest_version() -> Optional[str]:
    """Fetch latest version from GitHub tags."""
    try:
        response = requests.get(
            "https://api.github.com/repos/meshlg/_pinger/tags",
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            latest = data[0].get("name", "").lstrip("v")
            return latest if latest else None
        return None
    except Exception as exc:
        logging.debug(f"Version check failed: {exc}")
        return None


def check_update_available() -> tuple[bool, str, Optional[str]]:
    """Check if update is available.
    
    Returns:
        (update_available: bool, current_version: str, latest_version: Optional[str])
    """
    latest = get_latest_version()
    if latest is None:
        return False, VERSION, None
    
    # Simple version comparison (assumes semver format X.Y.Z)
    current_parts = [int(x) for x in VERSION.split(".")]
    latest_parts = [int(x) for x in latest.split(".")]
    
    # Pad to same length
    while len(current_parts) < len(latest_parts):
        current_parts.append(0)
    while len(latest_parts) < len(current_parts):
        latest_parts.append(0)
    
    update_available = latest_parts > current_parts
    return update_available, VERSION, latest
