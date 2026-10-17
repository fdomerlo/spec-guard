import os
import sys
import json
import pytest
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from spec_guard import cli


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
    import configparser
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

    assert not (Path(tmpdir) / ".spec-guard" / "SESSION.md").exists()
    assert not (Path(tmpdir) / "SESSION.md").exists()
    state_file = Path(tmpdir) / ".spec-guard" / "changes" / "test-crit" / "state.ini"
    cfg = configparser.ConfigParser()
    cfg.read(state_file, encoding="utf-8")
    assert cfg.get("Session", "next_action") == "Implementar CRIT-02"
    assert "CRIT-01 completado" in cfg.get("Session", "completed")
    assert "Implementar CRIT-02" in cfg.get("Session", "session_summary")


def test_init_sh_bootstrap(tmpdir):
    import subprocess
    repo_root = Path(__file__).resolve().parents[2]
    cli_script = repo_root / "spec_guard" / "cli.py"
    assert cli_script.exists()

    # Pre-populate custom AGENTS.md
    custom_agents = "# Custom Team Rules\n- Use 4 spaces.\n"
    target_agents = Path(tmpdir) / "AGENTS.md"
    target_agents.write_text(custom_agents, encoding="utf-8")

    # Run sg init -d <tmpdir>
    res = subprocess.run(
        [sys.executable, str(cli_script), "init", "-d", str(tmpdir)],
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

    # Verify .spec-guard/bin/verify-crit.sh (no scripts/ dir in the project root)
    verify_crit = Path(tmpdir) / ".spec-guard" / "bin" / "verify-crit.sh"
    assert verify_crit.exists()
    assert os.access(str(verify_crit), os.X_OK)
    assert not (Path(tmpdir) / "scripts").exists()

    # Verify root documents created from templates
    assert (Path(tmpdir) / "requirements.md").exists()
    assert (Path(tmpdir) / "design.md").exists()


def test_crit_01_blocking_git_hooks(monkeypatch, tmpdir, capsys):
    import subprocess
    repo_dir = Path(tmpdir)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    monkeypatch.chdir(repo_dir)
    monkeypatch.setattr(cli, "REPO_ROOT", repo_dir)
    monkeypatch.setattr(cli, "SG_DIR", repo_dir / ".spec-guard")
    monkeypatch.setattr(cli, "CHANGES_DIR", repo_dir / ".spec-guard" / "changes")

    args = Namespace(force=True)
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_install_hooks(args)
    assert exc_info.value.code == 0
    capsys.readouterr()

    pre_commit = repo_dir / ".git" / "hooks" / "pre-commit"
    commit_msg = repo_dir / ".git" / "hooks" / "commit-msg"
    assert pre_commit.exists() and os.access(str(pre_commit), os.X_OK)
    assert commit_msg.exists() and os.access(str(commit_msg), os.X_OK)

    # Set up a change in lock_phase = plan
    change_dir = repo_dir / ".spec-guard" / "changes" / "feat-hooks"
    change_dir.mkdir(parents=True, exist_ok=True)
    state_file = change_dir / "state.ini"
    state_file.write_text(
        "[Metadata]\nschema_version = 2\n\n"
        "[Transaction]\ntxn_status = in_progress\ntxn_phase = plan\n\n"
        "[Graph]\ncurrent_phase = none\nlock_phase = plan\n",
        encoding="utf-8",
    )

    # Staging a code file in plan phase must be blocked by pre-commit
    (repo_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=str(repo_dir), check=True)
    res_block = subprocess.run([str(pre_commit)], cwd=str(repo_dir), capture_output=True, text=True)
    assert res_block.returncode != 0

    # Unstage app.py, stage only markdown -> pre-commit must allow
    subprocess.run(["git", "rm", "--cached", "app.py"], cwd=str(repo_dir), check=True, capture_output=True)
    (repo_dir / "README.md").write_text("# Doc\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    res_allow = subprocess.run([str(pre_commit)], cwd=str(repo_dir), capture_output=True, text=True)
    assert res_allow.returncode == 0

    # Switch to lock_phase = execute and test commit-msg hook
    state_file.write_text(
        "[Metadata]\nschema_version = 2\n\n"
        "[Transaction]\ntxn_status = in_progress\ntxn_phase = execute\n\n"
        "[Graph]\ncurrent_phase = plan\nlock_phase = execute\n",
        encoding="utf-8",
    )
    msg_file = repo_dir / "COMMIT_EDITMSG"
    # Invalid conventional commit
    msg_file.write_text("bad commit message\n", encoding="utf-8")
    assert subprocess.run([str(commit_msg), str(msg_file)], cwd=str(repo_dir), capture_output=True).returncode != 0
    # Valid conventional commit but missing change/RF token in execute phase
    msg_file.write_text("feat: add endpoint\n", encoding="utf-8")
    assert subprocess.run([str(commit_msg), str(msg_file)], cwd=str(repo_dir), capture_output=True).returncode != 0
    # Valid conventional commit with active change name
    msg_file.write_text("feat(feat-hooks): add endpoint\n", encoding="utf-8")
    assert subprocess.run([str(commit_msg), str(msg_file)], cwd=str(repo_dir), capture_output=True).returncode == 0


def test_crit_02_spec_hash_integrity(monkeypatch, tmpdir, capsys):
    from spec_guard.core import state_manager
    repo_dir = Path(tmpdir)
    monkeypatch.chdir(repo_dir)
    monkeypatch.setattr(cli, "REPO_ROOT", repo_dir)
    monkeypatch.setattr(cli, "SG_DIR", repo_dir / ".spec-guard")
    monkeypatch.setattr(cli, "CHANGES_DIR", repo_dir / ".spec-guard" / "changes")

    tasks = "- [ ] CRIT-01: Validate spec hash\n"
    design = "# Design\n## Decisiones de Arquitectura\nArch\n"
    setup_change(str(repo_dir), tasks_content=tasks, design_content=design)
    change_dir = repo_dir / ".spec-guard" / "changes" / "test-crit"
    (change_dir / "objective.md").write_text("# Objective\nOriginal spec\n", encoding="utf-8")

    # Compute and store spec_hash via compute_spec_hash
    spec_hash = state_manager.compute_spec_hash(repo_dir, "test-crit")
    assert len(spec_hash) == 64

    cfg, path = state_manager.load_state("test-crit")
    cfg.set("Transaction", "spec_hash", spec_hash)
    state_manager.save_state(cfg, path)

    test_dir = repo_dir / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_spec.py").write_text("def test_CRIT_01_hash(): pass\n", encoding="utf-8")

    # Unmodified spec -> passes verify_crit
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_verify_crit(Namespace(change="test-crit"))
    assert exc_info.value.code == 0
    res_ok = json.loads(capsys.readouterr().out)
    assert res_ok["ok"] is True
    assert res_ok.get("spec_hash_valid") is True

    # Tamper with objective.md during execute -> fails verify_crit with code 2
    (change_dir / "objective.md").write_text("# Objective\nTampered spec!\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info2:
        cli.cmd_verify_crit(Namespace(change="test-crit"))
    assert exc_info2.value.code == 2
    res_fail = json.loads(capsys.readouterr().out)
    assert res_fail["ok"] is False
    assert res_fail.get("spec_hash_valid") is False


def test_crit_03_bypass_audit_and_run_tests(monkeypatch, tmpdir, capsys):
    import subprocess
    repo_dir = Path(tmpdir)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)

    monkeypatch.chdir(repo_dir)
    monkeypatch.setattr(cli, "REPO_ROOT", repo_dir)
    monkeypatch.setattr(cli, "SG_DIR", repo_dir / ".spec-guard")
    monkeypatch.setattr(cli, "CHANGES_DIR", repo_dir / ".spec-guard" / "changes")

    (repo_dir / "README.md").write_text("# Init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial"], cwd=str(repo_dir), check=True, capture_output=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_dir), check=True, capture_output=True, text=True
    ).stdout.strip()

    setup_change(str(repo_dir), tasks_content="- [ ] CRIT-01: Audit bypass and run tests\n")
    state_file = repo_dir / ".spec-guard" / "changes" / "test-crit" / "state.ini"
    state_file.write_text(
        "[Metadata]\nschema_version = 2\n\n"
        f"[Transaction]\ntxn_status = in_progress\ntxn_phase = execute\nbase_commit = {base_sha}\n\n"
        "[Graph]\ncurrent_phase = plan\nlock_phase = execute\n",
        encoding="utf-8",
    )

    test_dir = repo_dir / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_bypass.py").write_text("def test_CRIT_01_bypass(): pass\n", encoding="utf-8")

    # 1. Test --run-tests with passing command configured in config.yaml
    cfg_file = repo_dir / ".spec-guard" / "config.yaml"
    cfg_file.write_text("project:\n  test_command: 'python3 -c \"import sys; sys.exit(0)\"'\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_pass:
        cli.cmd_verify_crit(Namespace(change="test-crit", run_tests=True))
    assert exc_pass.value.code == 0
    res_pass = json.loads(capsys.readouterr().out)
    assert res_pass["tests_passed"] is True

    # 2. Test --run-tests with failing command configured in config.yaml
    cfg_file.write_text("project:\n  test_command: 'python3 -c \"import sys; sys.exit(1)\"'\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_fail_test:
        cli.cmd_verify_crit(Namespace(change="test-crit", run_tests=True))
    assert exc_fail_test.value.code == 2
    res_fail_test = json.loads(capsys.readouterr().out)
    assert res_fail_test["tests_passed"] is False

    # 3. Test bypass audit: commit a code file without referencing 'test-crit' or 'RF-'
    (repo_dir / "sneaky.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "sneaky.py"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-m", "feat: sneaky commit without token"], cwd=str(repo_dir), check=True, capture_output=True)

    with pytest.raises(SystemExit) as exc_bypass:
        cli.cmd_verify_crit(Namespace(change="test-crit", run_tests=False))
    assert exc_bypass.value.code == 2
    res_bypass = json.loads(capsys.readouterr().out)
    assert res_bypass["ok"] is False
    assert len(res_bypass.get("bypass_commits", [])) == 1


def test_crit_04_discipline_flow_removed_and_docs_synced():
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "revision" / "discipline-flow").exists()
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    manual = (repo_root / "MANUAL.md").read_text(encoding="utf-8")
    assert "pre-commit" in readme and "commit-msg" in readme
    assert "spec_hash" in manual and "--run-tests" in manual


def test_crit_01_single_skill_architecture():
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "phases").exists()
    assert not (repo_root / "skills").exists()
    assert (repo_root / "SKILL.md").exists()
    skill_content = (repo_root / "SKILL.md").read_text(encoding="utf-8")
    for required in ("INTAKE", "CONFLICT SCAN", "DRAFT", "REVIEW", "Definition of Done", "Security Checklist"):
        assert required in skill_content


def test_crit_02_session_consolidated_in_state_ini(monkeypatch, tmpdir, capsys):
    import configparser
    monkeypatch.chdir(tmpdir)
    monkeypatch.setattr(cli, "REPO_ROOT", Path(tmpdir))
    monkeypatch.setattr(cli, "CHANGES_DIR", Path(tmpdir) / ".spec-guard" / "changes")
    monkeypatch.setattr(cli, "SG_DIR", Path(tmpdir) / ".spec-guard")

    setup_change(str(tmpdir))
    args = Namespace(
        change="test-crit",
        action="Verify state.ini consolidation",
        completed="- Step 1",
        working_state="- Executing",
        decisions="- Use state.ini",
        tests="108 passed",
    )
    with pytest.raises(SystemExit) as exc_info:
        cli.cmd_session_checkpoint(args)
    assert exc_info.value.code == 0
    res = json.loads(capsys.readouterr().out)
    assert res["ok"] is True
    assert not (Path(tmpdir) / ".spec-guard" / "SESSION.md").exists()
    assert not (Path(tmpdir) / ".spec-guard" / "changes" / "test-crit" / "SESSION.md").exists()
    cfg = configparser.ConfigParser()
    cfg.read(Path(tmpdir) / ".spec-guard" / "changes" / "test-crit" / "state.ini", encoding="utf-8")
    assert cfg.get("Session", "next_action") == "Verify state.ini consolidation"
    assert cfg.get("Session", "tests") == "108 passed"


def test_crit_03_install_and_verify_scripts_clean():
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "scripts").exists()
    install_sh = (repo_root / "install.sh").read_text(encoding="utf-8")
    verify_sh = (repo_root / "spec_guard" / "templates" / "verify-crit.sh").read_text(encoding="utf-8")
    assert "phases/" not in install_sh
    assert "skills/_shared" not in install_sh
    assert "--uninstall" in install_sh
    assert "SESSION.md" not in verify_sh


def test_crit_04_docs_and_agents_template_synced():
    repo_root = Path(__file__).resolve().parents[2]
    for rel in ("AGENTS.md", "spec_guard/templates/AGENTS.md.template", "README.md", "MANUAL.md"):
        content = (repo_root / rel).read_text(encoding="utf-8")
        assert "SESSION.md" not in content, f"{rel} still references SESSION.md"
        assert "state.ini" in content


