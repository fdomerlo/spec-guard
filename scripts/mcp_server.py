#!/usr/bin/env python3
"""Shim de compatibilidad hacia spec_guard.mcp.server."""
import os
import sys

_real_path = os.path.realpath(__file__)
_parent_dir = os.path.dirname(os.path.dirname(_real_path))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
_installed_dir = os.path.expanduser("~/.agents/skills/spec-guard")
if os.path.exists(_installed_dir) and _installed_dir not in sys.path:
    sys.path.append(_installed_dir)

from spec_guard.mcp.server import *

if __name__ == "__main__":
    main()
