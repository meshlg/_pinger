from __future__ import annotations


def _notify_running_instance(message: str) -> bool:
    """Notify the running instance by writing to a notification file.
    
    This is called by the second instance when it fails to acquire the lock.
    The running instance will periodically check for this notification.
    
    Args:
        message: The notification message to display.
        
    Returns:
        True if notification was written successfully.
    """
    try:
        import tempfile
        from pathlib import Path
        
        notification_path = Path(tempfile.gettempdir()) / "pinger.notification"
        with open(notification_path, 'w', encoding='utf-8') as f:
            f.write(message)
        return True
    except Exception:
        return False


def check_instance_notification() -> str | None:
    """Check for notification from another instance trying to start.
    
    Returns:
        The notification message if present, None otherwise.
        The notification file is deleted after reading.
    """
    try:
        import tempfile
        from pathlib import Path
        
        notification_path = Path(tempfile.gettempdir()) / "pinger.notification"
        if not notification_path.exists():
            return None
        
        with open(notification_path, 'r', encoding='utf-8') as f:
            message = f.read().strip()
        
        # Delete the notification file after reading
        notification_path.unlink(missing_ok=True)
        return message if message else None
    except Exception:
        return None
