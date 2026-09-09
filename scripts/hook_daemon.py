#!/usr/bin/env python3
"""Shim de compatibilidad hacia spec_guard.daemon.hook_daemon."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spec_guard.daemon.hook_daemon as _real_daemon
from spec_guard.daemon.hook_daemon import *

for _attr in dir(_real_daemon):
    if not _attr.startswith("__"):
        globals()[_attr] = getattr(_real_daemon, _attr)

if __name__ == "__main__":
    main()
