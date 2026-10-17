"""Tests para el comando sg context (CRIT-21)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import run_cli, write_root_project  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402


def test_crit_21_context_extracts_root_documents(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project)

    rc, out = run_cli(project, "context", "--root", str(project))
    assert rc == 0, out
    assert out["mode"] == "root"

    # Glosario
    terms = {g["term"]: g for g in out["glossary"]}
    assert "Historia Clínica" in terms
    assert "Historial" in terms["Historia Clínica"]["forbidden"]
    assert "Ficha médica" in terms["Historia Clínica"]["forbidden"]
    assert "Evolución" in terms

    # Stack y secciones
    assert "Django 5.x" in out["stack"]
    assert "Odontólogo" in out["roles"]
    assert "pasarelas de pago" in out["out_of_scope"]

    # Progreso de RF
    progress = out["rf_progress"]
    assert progress["total"] == 2
    assert progress["done"] == 1
    assert progress["pending"] == 1
    assert progress["rfs"][0]["id"] == "RF-101"
    assert progress["rfs"][0]["checked"] is False
    assert progress["rfs"][1]["id"] == "RF-102"
    assert progress["rfs"][1]["checked"] is True


def test_crit_21_context_legacy_mode_fallback(tmpdir):
    project = Path(str(tmpdir))
    # No requirements.md
    rc, out = run_cli(project, "context", "--root", str(project))
    assert rc == 0
    assert out["mode"] == "legacy"
    assert out["glossary"] == []
    assert out["rf_progress"]["total"] == 0


def test_crit_01_no_mcp_dependency_or_module():
    repo_root = Path(__file__).resolve().parents[2]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "mcp" not in pyproject.lower(), "pyproject.toml should not depend on or expose mcp"
    assert not (repo_root / "spec_guard" / "mcp").exists(), "spec_guard/mcp directory should be removed"
    assert not (repo_root / "scripts" / "mcp_server.py").exists(), "scripts/mcp_server.py shim should be removed"
    assert not (repo_root / "tests" / "unit" / "test_mcp_server.py").exists(), "test_mcp_server.py should be removed"


def test_crit_02_docs_sync_and_no_mcp():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    manual = (repo_root / "MANUAL.md").read_text(encoding="utf-8")

    assert "spec-guard-mcp" not in readme
    assert "spec-guard-mcp" not in manual
    assert "## Servidor MCP" not in manual
    assert "--approval-text" in readme
    assert "--task-id" in readme
    assert "sg context [--json]" not in readme
    assert "sg glossary-check [--staged]" not in readme
    assert not manual.lstrip().startswith("-##"), "MANUAL.md should not have '-##' typo"
    assert "txn_status: failed" not in manual


def test_crit_03_skills_and_install_sync():
    repo_root = Path(__file__).resolve().parents[2]
    skill_main = (repo_root / "SKILL.md").read_text(encoding="utf-8")
    install_sh = (repo_root / "install.sh").read_text(encoding="utf-8")

    assert "--approval-text" in skill_main
    assert "sg context" in skill_main
    assert "sg glossary-check" in skill_main
    assert "sg next-rf-id" in skill_main
    assert "glossary-check" in install_sh
    assert "context" in install_sh
    assert not (repo_root / "phases").exists()
    assert not (repo_root / "skills").exists()
    assert not (repo_root / "scripts").exists()


def test_crit_04_concurrency_test_cleans_up_temp_changes():
    repo_root = Path(__file__).resolve().parents[2]
    conc_py = (repo_root / "tests" / "concurrency_test.py").read_text(encoding="utf-8")
    assert "cleanup_test_changes" in conc_py


def test_crit_26_condensed_dod_and_security_references_exist():
    repo_root = Path(__file__).resolve().parents[2]
    skill_file = repo_root / "SKILL.md"
    assert skill_file.exists()

    content = skill_file.read_text(encoding="utf-8")
    assert "Definition of Done" in content
    assert "Security Checklist" in content
    assert "glossary-check" in content


