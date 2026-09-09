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


def test_mark_task_existing_pending(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    tasks_content = "- [ ] [T001] Primera tarea\n- [ ] [T002] Segunda tarea\n"
    tasks_path = create_mock_tasks_file(str(tmpdir), tasks_content)
    
    args = Namespace(change="test-change", task_id="T001")
    state_manager.cmd_mark_task(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "SUCCESS"
    assert res["task_id"] == "T001"
    
    with open(tasks_path, "r", encoding="utf-8") as f:
        new_content = f.read()
    assert "- [x] [T001] Primera tarea" in new_content
    assert "- [ ] [T002] Segunda tarea" in new_content


def test_mark_task_already_done_idempotent(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    tasks_content = "- [x] [T001] Primera tarea\n"
    create_mock_tasks_file(str(tmpdir), tasks_content)
    
    args = Namespace(change="test-change", task_id="T001")
    state_manager.cmd_mark_task(args)
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "ALREADY_DONE"
    assert res["task_id"] == "T001"


def test_mark_task_non_existent_task(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    tasks_content = "- [ ] [T001] Primera tarea\n"
    create_mock_tasks_file(str(tmpdir), tasks_content)
    
    args = Namespace(change="test-change", task_id="T999")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_mark_task(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["status"] == "ERROR"
    assert "no encontrada" in res["message"]


def test_mark_task_missing_tasks_file(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    args = Namespace(change="test-change", task_id="T001")
    
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_mark_task(args)
    assert exc_info.value.code == state_manager.EXIT_GENERIC
