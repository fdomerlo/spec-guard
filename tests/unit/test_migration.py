import os
import sys
import tempfile
import configparser
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_v1_state(tmpdir, lock_phase_v1="explore", completed_v1=""):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "1")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", "idle")
    config.set("Transaction", "txn_phase", "None")
    config.add_section("Graph")
    config.set("Graph", "lock_phase", lock_phase_v1)
    config.set("Graph", "current_phase", lock_phase_v1)
    config.set("Graph", "completed_phases", completed_v1)
    config.set("Graph", "pending_phases", "explore, propose, spec, design, tasks, apply, verify, archive")
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return state_path, config


def test_migration_no_progress(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    state_path, config = create_v1_state(str(tmpdir), lock_phase_v1="explore", completed_v1="")
    
    new_config, _ = state_manager._migrate_v1_to_v2(config, state_path)
    
    assert new_config.get("Graph", "lock_phase") == "plan"
    assert new_config.get("Graph", "completed_phases") == ""
    assert new_config.get("Graph", "pending_phases") == "plan, execute, verify"
    assert new_config.get("Session", "migrated_from_schema") == "v1"


def test_migration_partial_progress(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    # v1 had explore, propose, spec completed, currently on tasks (which maps to execute)
    state_path, config = create_v1_state(
        str(tmpdir),
        lock_phase_v1="tasks",
        completed_v1="explore, propose, spec, tasks"
    )
    
    new_config, _ = state_manager._migrate_v1_to_v2(config, state_path)
    
    assert new_config.get("Graph", "lock_phase") == "execute"
    assert "plan" in state_manager.get_list(new_config, "Graph", "completed_phases")
    assert "execute" not in state_manager.get_list(new_config, "Graph", "completed_phases")
    assert "execute" in state_manager.get_list(new_config, "Graph", "pending_phases")


def test_migration_full_progress(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    # v1 had all phases including verify and archive completed
    state_path, config = create_v1_state(
        str(tmpdir),
        lock_phase_v1="archive",
        completed_v1="explore, propose, spec, design, tasks, apply, verify, archive"
    )
    
    new_config, _ = state_manager._migrate_v1_to_v2(config, state_path)
    
    completed = state_manager.get_list(new_config, "Graph", "completed_phases")
    assert "plan" in completed
    assert "execute" in completed
    assert "verify" in completed
    assert state_manager.get_list(new_config, "Graph", "pending_phases") == []


def test_cmd_migrate_cli(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    state_path, _ = create_v1_state(str(tmpdir), lock_phase_v1="propose", completed_v1="explore")
    args = Namespace(change="test-change")
    
    state_manager.cmd_migrate(args)
    captured = capsys.readouterr()
    assert '"status": "SUCCESS"' in captured.out
    assert '"lock_phase_v2": "plan"' in captured.out
