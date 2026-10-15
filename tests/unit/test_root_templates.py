"""C1 CRIT-11 / CRIT-12 / CRIT-18: root templates, sg init and ephemeral-file locations."""
import json
import os
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import REPO_PKG_ROOT, run_cli, write_root_project  # noqa: E402
from spec_guard import cli  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402

TEMPLATES = Path(REPO_PKG_ROOT) / "spec_guard" / "templates"


def test_crit_11_init_creates_root_docs_with_project_name(tmpdir):
    project = Path(str(tmpdir)) / "clinica-demo"
    project.mkdir()
    rc, out = run_cli(project, "init")
    assert rc == 0, out
    req = project / "requirements.md"
    des = project / "design.md"
    assert req.exists() and des.exists()
    for f in (req, des):
        text = f.read_text(encoding="utf-8")
        assert "clinica-demo" in text
        assert "PROJECT_NAME" not in text


def test_crit_11_init_never_overwrites_existing_root_docs(tmpdir):
    project = Path(str(tmpdir))
    (project / "requirements.md").write_text("# mine\n", encoding="utf-8")
    (project / "design.md").write_text("# my design\n", encoding="utf-8")
    rc, out = run_cli(project, "init", "--force")
    assert rc == 0, out
    assert (project / "requirements.md").read_text(encoding="utf-8") == "# mine\n"
    assert (project / "design.md").read_text(encoding="utf-8") == "# my design\n"


def test_crit_12_templates_contain_default_stack():
    design = (TEMPLATES / "design.md.template").read_text(encoding="utf-8")
    for token in ["Django", "HTMX", "Alpine.js", "Tailwind", "PostgreSQL", "MariaDB",
                  "LXC", "Docker", "Proxmox VE", "services.py"]:
        assert token in root_docs.strip_html_comments(design), token


def test_crit_12_template_examples_only_in_comments():
    req = (TEMPLATES / "requirements.md.template").read_text(encoding="utf-8")
    assert "RF-101" in req and "Historia Clínica" in req  # example exists...
    stripped = root_docs.strip_html_comments(req)
    assert root_docs.parse_rfs(stripped) == []  # ...but only inside comments
    assert root_docs.parse_glossary(stripped) == []
    design = (TEMPLATES / "design.md.template").read_text(encoding="utf-8")
    assert "HistoriaClinica" not in root_docs.strip_html_comments(design)


def test_crit_12_fresh_template_fails_root_validation(tmpdir):
    project = Path(str(tmpdir))
    assert run_cli(project, "init")[0] == 0
    assert run_cli(project, "init-change", "--change", "c1", "--rf", "RF-101")[0] == 0
    rc, out = run_cli(project, "validate-spec", "--change", "c1")
    assert rc == 4
    kinds = {i["issue"] for i in out["issues"]}
    assert "UNRESOLVED_PLACEHOLDER" in kinds
    assert "EMPTY_GLOSSARY" in kinds
    assert "RF_NOT_FOUND" in kinds


def test_crit_18_init_installs_verify_crit_inside_spec_guard(tmpdir):
    project = Path(str(tmpdir))
    rc, out = run_cli(project, "init")
    assert rc == 0, out
    script = project / ".spec-guard" / "bin" / "verify-crit.sh"
    assert script.exists()
    assert os.access(str(script), os.X_OK)
    assert not (project / "scripts").exists()


def test_crit_18_session_checkpoint_writes_inside_spec_guard(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    write_root_project(project, lock_phase="execute")
    monkeypatch.chdir(str(project))
    monkeypatch.setattr(cli, "REPO_ROOT", project)
    monkeypatch.setattr(cli, "SG_DIR", project / ".spec-guard")
    monkeypatch.setattr(cli, "CHANGES_DIR", project / ".spec-guard" / "changes")
    args = Namespace(change="demo", action="Next", completed=None, working_state=None,
                     decisions=None, tests=None)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_session_checkpoint(args)
    assert exc.value.code in (0, None)
    res = json.loads(capsys.readouterr().out)
    assert res["ok"] is True
    assert (project / ".spec-guard" / "SESSION.md").exists()
    assert (project / ".spec-guard" / "changes" / "demo" / "SESSION.md").exists()
    assert not (project / "SESSION.md").exists()
    assert not (project / "SESSION.md.tmp").exists()
