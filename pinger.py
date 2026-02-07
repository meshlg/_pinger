"""Entry point for the pinger application.

Delegates to pinger.main() which handles dependency checks,
logging setup, and running the async main loop.
"""
from pinger import main


if __name__ == "__main__":
    main()
