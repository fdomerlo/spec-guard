#!/usr/bin/env python3
"""Shim de compatibilidad hacia spec_guard.cli."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spec_guard.cli import *

if __name__ == "__main__":
    main()
