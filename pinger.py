import asyncio
import logging
import shutil
import sys

from pinger import check_project_dependencies
from config import t, LOG_FILE, LOG_LEVEL, LOG_TRUNCATE_ON_START  # type: ignore


def _check_all_dependencies() -> None:
    """Check Python packages and system commands."""
    check_project_dependencies()

    missing_commands: list[str] = []

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


_check_all_dependencies()

from main import run_async_main  # type: ignore

logging.basicConfig(
    filename=LOG_FILE,
    filemode='w' if LOG_TRUNCATE_ON_START else 'a',
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)


def main() -> None:
    asyncio.run(run_async_main())


if __name__ == "__main__":
    main()
