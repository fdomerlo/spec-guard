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


def test_crit_25_mcp_server_exports_context_and_glossary_tools():
    server_py = Path(__file__).resolve().parents[2] / "spec_guard" / "mcp" / "server.py"
    content = server_py.read_text(encoding="utf-8")
    assert "def get_project_context" in content
    assert "def check_glossary" in content
    try:
        from spec_guard.mcp import server
        assert hasattr(server, "get_project_context")
        assert hasattr(server, "check_glossary")
    except ModuleNotFoundError:
        pass



def test_crit_26_condensed_dod_and_security_references_exist():
    repo_root = Path(__file__).resolve().parents[2]
    dod = repo_root / "phases" / "_shared" / "definition-of-done.md"
    sec = repo_root / "phases" / "_shared" / "security-checklist.md"
    verify_md = repo_root / "phases" / "verify.md"

    assert dod.exists(), "definition-of-done.md must exist in phases/_shared/"
    assert sec.exists(), "security-checklist.md must exist in phases/_shared/"

    # Condensed (~40-60 lines, not bloated)
    assert len(dod.read_text(encoding="utf-8").splitlines()) < 60
    assert len(sec.read_text(encoding="utf-8").splitlines()) < 60

    # verify.md references them
    verify_content = verify_md.read_text(encoding="utf-8")
    assert "definition-of-done.md" in verify_content
    assert "security-checklist.md" in verify_content
    assert "glossary-check" in verify_content


