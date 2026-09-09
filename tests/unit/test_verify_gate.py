import os
import sys
import json
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_state(tmpdir, lock_phase="execute"):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "2")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", "idle")
    config.add_section("Graph")
    config.set("Graph", "lock_phase", lock_phase)
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return state_path


def test_verify_gate_authorized_phase(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), lock_phase="execute")
    args = Namespace(change="test-change", phase="execute")
    
    state_manager.cmd_verify_gate(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["gate_ok"] is True
    assert res["requested_phase"] == "execute"
    assert res["lock_phase"] == "execute"


def test_verify_gate_unauthorized_phase(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir), lock_phase="execute")
    args = Namespace(change="test-change", phase="plan")
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_verify_gate(args)
    assert exc_info.value.code == state_manager.EXIT_BAD_TRANSITION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["gate_ok"] is False
    assert res["requested_phase"] == "plan"
    assert res["lock_phase"] == "execute"
    assert "error" in res
