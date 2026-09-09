import os
import sys
import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))
import hook_daemon


def test_should_skip_excluded_prefixes(monkeypatch, tmpdir):
    monkeypatch.setattr(hook_daemon, "REPO_ROOT", Path(tmpdir))
    handler = hook_daemon.HookHandler([])
    
    spec_guard_path = os.path.join(tmpdir, ".spec-guard", "somefile.txt")
    git_path = os.path.join(tmpdir, ".git", "HEAD")
    
    assert handler._should_skip(spec_guard_path) is True
    assert handler._should_skip(git_path) is True


def test_should_skip_forbidden_patterns(monkeypatch, tmpdir):
    monkeypatch.setattr(hook_daemon, "REPO_ROOT", Path(tmpdir))
    handler = hook_daemon.HookHandler([])
    
    objective_path = os.path.join(tmpdir, "changes", "my-change", "objective.md")
    design_path = os.path.join(tmpdir, "changes", "my-change", "design.md")
    
    assert handler._should_skip(objective_path) is True
    assert handler._should_skip(design_path) is True


def test_should_skip_normal_file_and_debounce(monkeypatch, tmpdir):
    monkeypatch.setattr(hook_daemon, "REPO_ROOT", Path(tmpdir))
    handler = hook_daemon.HookHandler([])
    
    normal_path = os.path.join(tmpdir, "src", "main.py")
    
    # Primer evento -> no debe skippearse (devuelve False)
    assert handler._should_skip(normal_path) is False
    
    # Inmediatamente después (< 2s) -> debe skippearse por debounce (devuelve True)
    assert handler._should_skip(normal_path) is True


def test_load_rules_malformed_yaml(monkeypatch, tmpdir):
    monkeypatch.setattr(hook_daemon, "RULES_FILE", Path(tmpdir) / "hooks.yaml")
    
    # Archivo de reglas malformado o vacío
    with open(Path(tmpdir) / "hooks.yaml", "w", encoding="utf-8") as f:
        f.write("invalid: yaml: [content")
        
    try:
        rules = hook_daemon._load_rules()
        assert rules == [] or isinstance(rules, list)
    except Exception:
        pytest.fail("_load_rules crashed on malformed YAML")


def test_fire_mocked_subprocess(monkeypatch, tmpdir):
    monkeypatch.setattr(hook_daemon, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(hook_daemon, "LOG_FILE", Path(tmpdir) / "hooks.log.jsonl")
    
    handler = hook_daemon.HookHandler([])
    rule = {
        "name": "test-rule",
        "pattern": "*.py",
        "events": ["on_save"],
        "prompt": "Fix {path}",
        "agent_command": ["echo", "test"],
        "timeout": 10
    }
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        handler._fire(rule, "src/index.py")
        
        mock_run.assert_called_once_with(
            ["echo", "test", "Fix src/index.py"],
            cwd=str(tmpdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
    assert (Path(tmpdir) / "hooks.log.jsonl").exists()
