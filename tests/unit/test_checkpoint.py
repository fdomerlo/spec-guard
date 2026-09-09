import os
import sys
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_state(tmpdir):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "2")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", "idle")
    config.add_section("Graph")
    config.set("Graph", "lock_phase", "plan")
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return state_path


def test_checkpoint_normal(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    state_path = create_mock_state(str(tmpdir))
    summary_text = "Progress update: component A completed"
    args = Namespace(change="test-change", summary=summary_text)
    
    state_manager.cmd_checkpoint(args)
    
    config = configparser.ConfigParser()
    config.read(state_path)
    assert config.get("Session", "session_summary") == summary_text


def test_checkpoint_exceeding_max_summary_chars(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    create_mock_state(str(tmpdir))
    too_long_summary = "a" * (state_manager.MAX_SUMMARY_CHARS + 1)
    args = Namespace(change="test-change", summary=too_long_summary)
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_checkpoint(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
