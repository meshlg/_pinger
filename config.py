"""
Legacy config.py - Backward compatibility wrapper.

⚠️  DEPRECATED: This file is a no-op stub.  Python resolves ``import config``
to the ``config/`` package (which has an ``__init__.py``), so this module is
never actually imported.  It is kept solely to prevent confusion if someone
expects a top-level ``config.py`` to exist.

All code should import directly from the config package::

    from config import VERSION, TARGET_IP, t, create_stats
    from config.settings import VERSION, TARGET_IP
    from config.i18n import t, LANG
    from config.types import create_stats, StatsDict
"""

# This file is intentionally left minimal.
# The config/ package __init__.py handles all exports.
