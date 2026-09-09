import os
import sys
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_state(tmpdir, txn_status="in_progress", txn_phase="plan"):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "2")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", txn_status)
    config.set("Transaction", "txn_phase", txn_phase)
    config.add_section("Graph")
    config.set("Graph", "lock_phase", "plan")
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return state_path


def test_rollback_active_transaction(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    state_path = create_mock_state(str(tmpdir), txn_status="in_progress", txn_phase="execute")
    args = Namespace(change="test-change")
    
    state_manager.cmd_rollback(args)
    
    config = configparser.ConfigParser()
    config.read(state_path)
    assert config.get("Transaction", "txn_status") == "idle"
    assert config.get("Transaction", "txn_phase") == "None"


def test_rollback_no_active_transaction(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), txn_status="idle", txn_phase="None")
    args = Namespace(change="test-change")
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_rollback(args)
    assert exc_info.value.code == state_manager.EXIT_GENERIC
