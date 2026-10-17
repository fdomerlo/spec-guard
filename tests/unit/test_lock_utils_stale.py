import os
import sys
import time
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from spec_guard.core.locking import with_write_lock, _is_write_lock_stale, try_acquire_lockfile


def test_stale_write_lock_dead_pid():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "test.write-lock")

        # Create lockfile with non-existent PID and old timestamp
        dead_pid = 999999
        old_time = time.time() - 3600
        with open(lock_path, "w") as f:
            f.write(f"{dead_pid}\n{old_time}\n")

        assert _is_write_lock_stale(lock_path) is True

        executed = False

        def sample_fn():
            nonlocal executed
            executed = True
            return "ok"

        result = with_write_lock(lock_path, sample_fn)
        assert executed is True
        assert result == "ok"
        assert not os.path.exists(lock_path)


def test_stale_write_lock_old_timestamp():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "test.write-lock")

        # Current PID but old timestamp (> 30s)
        old_time = time.time() - 60
        with open(lock_path, "w") as f:
            f.write(f"{os.getpid()}\n{old_time}\n")

        assert _is_write_lock_stale(lock_path, max_age_seconds=30) is True

        result = with_write_lock(lock_path, lambda: "reclaimed")
        assert result == "reclaimed"


def test_active_write_lock_not_stale():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = os.path.join(tmpdir, "test.write-lock")

        # Current PID and fresh timestamp
        with open(lock_path, "w") as f:
            f.write(f"{os.getpid()}\n{time.time()}\n")

        assert _is_write_lock_stale(lock_path, max_age_seconds=30) is False
