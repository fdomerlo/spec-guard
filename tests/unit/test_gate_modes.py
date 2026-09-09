import os
import sys
import pytest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../spec_guard")))
import core.state_manager as sm


def setup_plan_change(tmpdir):
    guard_dir = Path(tmpdir) / ".spec-guard"
    change_dir = guard_dir / "changes" / "test-gate-change"
    change_dir.mkdir(parents=True, exist_ok=True)

    state_file = change_dir / "state.ini"
    state_file.write_text(
        "[Metadata]\nschema_version = 2\n\n"
        "[Transaction]\ntxn_status = in_progress\ntxn_phase = plan\n\n"
        "[Graph]\ncurrent_phase = none\nlock_phase = plan\n"
        "completed_phases = \npending_phases = plan, execute, verify\n"
    )
    return change_dir


def test_gate_mode_chat_default(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.delenv("SPECGUARD_GATE_MODE", raising=False)
    monkeypatch.delenv("STATEGUARD_GATE_MODE", raising=False)

    setup_plan_change(str(tmpdir))

    # Verificar que el modo por defecto es 'chat'
    assert sm.get_gate_mode("test-gate-change") == "chat"

    # En modo chat, commit de plan -> execute pasa sin exigir token out-of-band
    args = Namespace(change="test-gate-change", next_phase="execute")
    sm.cmd_commit(args)

    cfg, _ = sm.load_state("test-gate-change")
    assert cfg.get("Graph", "lock_phase") == "execute"
    assert cfg.get("Graph", "current_phase") == "plan"
    assert cfg.get("Gate", "plan_approved_by") == "chat"
    assert cfg.get("Gate", "gate_mode") == "chat"


def test_gate_mode_strict_missing_token_fails(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv("SPECGUARD_GATE_MODE", "strict")

    setup_plan_change(str(tmpdir))
    assert sm.get_gate_mode("test-gate-change") == "strict"

    args = Namespace(change="test-gate-change", next_phase="execute")
    with pytest.raises(SystemExit) as exc_info:
        sm.cmd_commit(args)
    assert exc_info.value.code == sm.EXIT_GATE_REQUIRED


def test_gate_mode_strict_with_token_passes(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv("SPECGUARD_GATE_MODE", "strict")

    change_dir = setup_plan_change(str(tmpdir))
    # Inyectar token simulando confirmación humana previa
    state_file = change_dir / "state.ini"
    content = state_file.read_text()
    state_file.write_text(content + "\n[Gate]\nplan_gate_token = token_hash_123\n")

    args = Namespace(change="test-gate-change", next_phase="execute")
    sm.cmd_commit(args)

    cfg, _ = sm.load_state("test-gate-change")
    assert cfg.get("Graph", "lock_phase") == "execute"
    assert cfg.get("Graph", "current_phase") == "plan"
    # El token se consume post-commit
    assert cfg.get("Gate", "plan_gate_token", fallback=None) is None


def test_gate_mode_from_config_yaml(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.delenv("SPECGUARD_GATE_MODE", raising=False)
    monkeypatch.delenv("STATEGUARD_GATE_MODE", raising=False)

    guard_dir = Path(tmpdir) / ".spec-guard"
    guard_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = guard_dir / "config.yaml"

    setup_plan_change(str(tmpdir))

    # Configurado como strict
    cfg_file.write_text("schema: spec-driven\ngate:\n  mode: strict\n")
    assert sm.get_gate_mode("test-gate-change") == "strict"

    # Configurado como chat
    cfg_file.write_text("schema: spec-driven\ngate:\n  mode: chat\n")
    assert sm.get_gate_mode("test-gate-change") == "chat"
