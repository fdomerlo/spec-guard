import os
import sys
import json
import pytest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../spec_guard")))
import cli


def setup_change(tmpdir, tasks_content=None, design_content=None):
    guard_dir = Path(tmpdir) / ".spec-guard"
    change_dir = guard_dir / "changes" / "test-crit"
    change_dir.mkdir(parents=True, exist_ok=True)

    state_file = change_dir / "state.ini"
    state_file.write_text(
        "[Metadata]\nschema_version = 2\n\n"
        "[Transaction]\ntxn_status = in_progress\ntxn_phase = execute\n\n"
        "[Graph]\ncurrent_phase = plan\nlock_phase = execute\n"
    )

    if tasks_content:
        (change_dir / "tasks.md").write_text(tasks_content, encoding="utf-8")
    if design_content:
        (change_dir / "design.md").write_text(design_content, encoding="utf-8")


def test_verify_crit_all_automated_pass(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setattr(cli, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(cli, "CHANGES_DIR", Path(tmpdir) / ".spec-guard" / "changes")
    monkeypatch.setattr(cli, "SG_DIR", Path(tmpdir) / ".spec-guard")

    tasks = """# Tareas
## Fase 1
- [ ] CRIT-01: Validar autenticación
- [ ] CRIT-02: Manejar expiración de token
"""
    setup_change(str(tmpdir), tasks_content=tasks)

    # Crear tests falsos en tests/
    test_dir = Path(tmpdir) / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_auth.py").write_text(
        "def test_CRIT_01_autenticacion(): pass\n"
        "def test_CRIT_02_expiracion(): pass\n"
    )

    args = Namespace(change="test-crit")
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_verify_crit(args)
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["failures"] == 0
    assert len(res["criteria"]) == 2


def test_verify_crit_missing_test_fails(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setattr(cli, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(cli, "CHANGES_DIR", Path(tmpdir) / ".spec-guard" / "changes")
    monkeypatch.setattr(cli, "SG_DIR", Path(tmpdir) / ".spec-guard")

    tasks = """# Tareas
- [ ] CRIT-01: Validar autenticación
- [ ] CRIT-99: Criterio sin test
"""
    setup_change(str(tmpdir), tasks_content=tasks)

    test_dir = Path(tmpdir) / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_auth.py").write_text("def test_CRIT_01_autenticacion(): pass\n")

    args = Namespace(change="test-crit")
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_verify_crit(args)
    assert exc_info.value.code == 2

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    assert res["failures"] == 1


def test_verify_crit_manual_criterion_succeeds(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setattr(cli, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(cli, "CHANGES_DIR", Path(tmpdir) / ".spec-guard" / "changes")
    monkeypatch.setattr(cli, "SG_DIR", Path(tmpdir) / ".spec-guard")

    tasks = """# Tareas
- [ ] CRIT-01: Validar autenticación
- [ ] CRIT-03: (manual) Verificar legibilidad en UI
"""
    setup_change(str(tmpdir), tasks_content=tasks)

    test_dir = Path(tmpdir) / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_auth.py").write_text("def test_CRIT_01_autenticacion(): pass\n")

    args = Namespace(change="test-crit")
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_verify_crit(args)
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["failures"] == 0
    manual_items = [c for c in res["criteria"] if c["type"] == "manual"]
    assert len(manual_items) == 1
    assert manual_items[0]["id"] == "CRIT-03"


def test_session_checkpoint_creation(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setattr(cli, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(cli, "CHANGES_DIR", Path(tmpdir) / ".spec-guard" / "changes")
    monkeypatch.setattr(cli, "SG_DIR", Path(tmpdir) / ".spec-guard")

    setup_change(str(tmpdir))

    args = Namespace(
        change="test-crit",
        action="Implementar CRIT-02",
        completed="- CRIT-01 completado",
        working_state="- Trabajando en auth",
        decisions="- Ninguna",
        tests="pytest: passing",
    )
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_session_checkpoint(args)
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True

    session_file = Path(tmpdir) / "SESSION.md"
    assert session_file.exists()
    content = session_file.read_text()
    assert "Implementar CRIT-02" in content
    assert "CRIT-01 completado" in content


def test_init_sh_bootstrap(tmpdir):
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    init_script = repo_root / "scripts" / "init.sh"
    assert init_script.exists()

    # Pre-populate custom AGENTS.md
    custom_agents = "# Custom Team Rules\n- Use 4 spaces.\n"
    target_agents = Path(tmpdir) / "AGENTS.md"
    target_agents.write_text(custom_agents, encoding="utf-8")

    # Run init.sh
    res = subprocess.run(
        ["bash", str(init_script), "-d", str(tmpdir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0

    # Verify AGENTS.md preserves custom rules and appends SpecGuard block
    content = target_agents.read_text(encoding="utf-8")
    assert "# Custom Team Rules" in content
    assert "<!-- BEGIN SPECGUARD -->" in content
    assert "<!-- END SPECGUARD -->" in content

    # Verify CLAUDE.md
    claude_md = Path(tmpdir) / "CLAUDE.md"
    assert claude_md.exists()
    assert "@AGENTS.md" in claude_md.read_text(encoding="utf-8")

    # Verify scripts/verify-crit.sh
    verify_crit = Path(tmpdir) / "scripts" / "verify-crit.sh"
    assert verify_crit.exists()
    assert os.access(str(verify_crit), os.X_OK)
