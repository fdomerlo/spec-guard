import os
import sys
import json
import tempfile
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))

import state_manager


def create_mock_tasks_file(tmpdir, content):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    tasks_path = os.path.join(change_dir, "tasks.md")
    with open(tasks_path, "w", encoding="utf-8") as f:
        f.write(content)
    return tasks_path


def test_next_task_pending_exists(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    tasks_content = "- [x] [T001] Tarea 1\n- [ ] [T002] Tarea 2 pendiente\n- [ ] [T003] Tarea 3 pendiente\n"
    create_mock_tasks_file(str(tmpdir), tasks_content)
    
    args = Namespace(change="test-change")
    state_manager.cmd_next_task(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "OK"
    assert res["task"]["id"] == "T002"
    assert res["task"]["description"] == "Tarea 2 pendiente"


def test_next_task_all_completed(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    tasks_content = "- [x] [T001] Tarea 1\n- [x] [T002] Tarea 2\n"
    create_mock_tasks_file(str(tmpdir), tasks_content)
    
    args = Namespace(change="test-change")
    state_manager.cmd_next_task(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "ALL_COMPLETE"
    assert res["task"] is None


def test_next_task_missing_file(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    args = Namespace(change="test-change")
    state_manager.cmd_next_task(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "NO_TASKS_FILE"
    assert res["task"] is None
