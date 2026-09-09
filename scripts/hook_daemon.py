#!/usr/bin/env python3
"""Shim de compatibilidad hacia spec_guard.daemon.hook_daemon."""
import os
import sys

_real_path = os.path.realpath(__file__)
_parent_dir = os.path.dirname(os.path.dirname(_real_path))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
_installed_dir = os.path.expanduser("~/.agents/skills/spec-guard")
if os.path.exists(_installed_dir) and _installed_dir not in sys.path:
    sys.path.append(_installed_dir)

import spec_guard.daemon.hook_daemon as _real_daemon
from spec_guard.daemon.hook_daemon import *

for _attr in dir(_real_daemon):
    if not _attr.startswith("__"):
        globals()[_attr] = getattr(_real_daemon, _attr)

if __name__ == "__main__":
    main()
