import os
import sys
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_state(tmpdir, change_name="test-change", txn_status="in_progress", txn_phase="plan", lock_phase="plan", gate_token=None):
    change_dir = os.path.join(tmpdir, ".state-guard", "changes", change_name)
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "2")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", txn_status)
    config.set("Transaction", "txn_phase", txn_phase)
    config.add_section("Graph")
    config.set("Graph", "lock_phase", lock_phase)
    config.set("Graph", "current_phase", "none")
    config.set("Graph", "completed_phases", "")
    config.set("Graph", "pending_phases", "plan, execute, verify")
    if gate_token:
        config.add_section("Gate")
        config.set("Gate", "plan_gate_token", gate_token)
        
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return change_dir, state_path


def test_commit_valid_transition_with_gate(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), txn_phase="plan", gate_token="valid_token")
    args = Namespace(change="test-change", next_phase="execute")
    
    state_manager.cmd_commit(args)
    
    config = configparser.ConfigParser()
    config.read(os.path.join(tmpdir, ".state-guard", "changes", "test-change", "state.ini"))
    assert config.get("Transaction", "txn_status") == "idle"
    assert config.get("Graph", "lock_phase") == "execute"
    assert "plan" in config.get("Graph", "completed_phases")
    assert config.has_option("Gate", "plan_gate_token") is False
    assert "fase_completada=plan" in config.get("Session", "session_summary")


def test_commit_plan_without_gate_raises_exit_gate_required(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv("SPECGUARD_GATE_MODE", "strict")
    create_mock_state(str(tmpdir), txn_phase="plan", gate_token=None)
    args = Namespace(change="test-change", next_phase="execute")
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_commit(args)
    assert exc_info.value.code == state_manager.EXIT_GATE_REQUIRED


def test_commit_invalid_transition_outside_dag(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), txn_phase="execute", gate_token=None)
    args = Namespace(change="test-change", next_phase="plan")  # Invalid: execute -> plan
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_commit(args)
    assert exc_info.value.code == state_manager.EXIT_BAD_TRANSITION


def test_commit_without_in_progress_transaction(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), txn_status="idle", txn_phase="None")
    args = Namespace(change="test-change", next_phase="execute")
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_commit(args)
    assert exc_info.value.code == state_manager.EXIT_GENERIC
