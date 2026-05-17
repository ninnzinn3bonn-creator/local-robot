"""
utils/encoding.py - Windows console-friendly stdio setup.
"""
from __future__ import annotations

import sys


def configure_utf8_stdio() -> None:
    """Use UTF-8 for captured/redirected stdio so Japanese status output is stable."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
