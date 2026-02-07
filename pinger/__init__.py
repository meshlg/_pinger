"""
Module for checking project dependencies.
"""

import sys

def check_project_dependencies() -> None:
    """
    Check all project dependencies before importing external packages.
    """
    required_packages = ["rich", "requests", "dns"]
    missing_packages = []
    
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing_packages.append(pkg)
    
    if missing_packages:
        # Import t() here to avoid circular imports — config only needs stdlib
        from config import t
        print(t("err_missing_deps"))
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print(f"\n{t('install_deps_hint')}")
        print("  pip install -r requirements.txt")
        sys.exit(1)


def main() -> None:
    """CLI entry point for the pinger application."""
    import asyncio
    import logging
    import shutil
    import os

    from config import t, LOG_FILE, LOG_LEVEL, LOG_TRUNCATE_ON_START, LOG_DIR

    # Check dependencies
    check_project_dependencies()

    missing_commands = []
    if shutil.which("ping") is None:
        missing_commands.append("ping")
    if not (shutil.which("traceroute") or shutil.which("tracert")):
        missing_commands.append("traceroute/tracert")

    if missing_commands:
        print(t("err_missing_commands").format(cmds=", ".join(missing_commands)))
        print(f"\n{t('install_commands_hint')}")
        if sys.platform == "win32":
            print(t("win_ping_hint"))
            print(t("win_tracert_hint"))
        else:
            print("  Debian/Ubuntu: sudo apt-get install iputils-ping traceroute")
            print("  RHEL/CentOS: sudo yum install iputils traceroute")
            print("  Alpine: sudo apk add iputils-traceroute")
        sys.exit(1)

    from main import run_async_main

    # Create log directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)

    logging.basicConfig(
        filename=LOG_FILE,
        filemode='w' if LOG_TRUNCATE_ON_START else 'a',
        level=getattr(logging, LOG_LEVEL.upper()),
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )

    asyncio.run(run_async_main())