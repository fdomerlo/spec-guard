import os
import sys
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_change(tmpdir, change_name="test-change", schema_version="2", status="idle", phase="None"):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", change_name)
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", schema_version)
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", status)
    config.set("Transaction", "txn_phase", phase)
    config.add_section("Graph")
    config.set("Graph", "lock_phase", "plan")
    config.set("Graph", "current_phase", "none")
    config.set("Graph", "completed_phases", "")
    config.set("Graph", "pending_phases", "plan, execute, verify")
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return change_dir, state_path


def test_begin_valid_phase(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_change(str(tmpdir))
    args = Namespace(change="test-change", phase="plan", ttl=1800)
    
    state_manager.cmd_begin(args)
    
    config = configparser.ConfigParser()
    config.read(os.path.join(tmpdir, ".spec-guard", "changes", "test-change", "state.ini"))
    assert config.get("Transaction", "txn_status") == "in_progress"
    assert config.get("Transaction", "txn_phase") == "plan"


def test_begin_already_in_progress(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_change(str(tmpdir), status="in_progress", phase="plan")
    
    # Pre-create lockfile to simulate active transaction lock
    lock_file = os.path.join(tmpdir, ".spec-guard", "changes", "test-change", ".lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    with open(lock_file, "w") as f:
        f.write("active")
        
    args = Namespace(change="test-change", phase="plan", ttl=1800)
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_begin(args)
    assert exc_info.value.code == state_manager.EXIT_LOCK_CONFLICT


def test_begin_stale_lock_recovery(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_change(str(tmpdir), status="in_progress", phase="plan")
    
    # Set started_at to old timestamp
    state_path = os.path.join(tmpdir, ".spec-guard", "changes", "test-change", "state.ini")
    config = configparser.ConfigParser()
    config.read(state_path)
    config.set("Transaction", "txn_started_at", "2020-01-01T00:00:00")
    with open(state_path, "w") as f:
        config.write(f)
        
    args = Namespace(change="test-change", phase="execute", ttl=10)
    state_manager.cmd_begin(args)
    
    config.read(state_path)
    assert config.get("Transaction", "txn_status") == "in_progress"
    assert config.get("Transaction", "txn_phase") == "execute"


def test_begin_auto_migrates_v1_to_v2(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_change(str(tmpdir), schema_version="1")
    
    args = Namespace(change="test-change", phase="plan", ttl=1800)
    state_manager.cmd_begin(args)
    
    config = configparser.ConfigParser()
    config.read(os.path.join(tmpdir, ".spec-guard", "changes", "test-change", "state.ini"))
    assert config.get("Metadata", "schema_version") == "2"
