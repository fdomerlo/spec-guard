"""Shim de compatibilidad hacia spec_guard.core.locking."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spec_guard.core.locking import *
