"""Tests para el cálculo determinista del próximo ID de RF (CRIT-31)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import run_cli, write_root_project  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402


def test_crit_31_next_rf_id_sequential():
    text = (
        "### [ ] RF-101: Primera tarea\n"
        "### [x] RF-102: Segunda tarea\n"
    )
    assert root_docs.next_rf_id(text) == "RF-103"


def test_crit_31_next_rf_id_with_module_prefix():
    text = (
        "### [ ] RF-101: Tarea 101\n"
        "### [x] RF-102: Tarea 102\n"
        "### [ ] RF-201: Tarea 201\n"
    )
    assert root_docs.next_rf_id(text, module_prefix="RF-100") == "RF-103"
    assert root_docs.next_rf_id(text, module_prefix="RF-200") == "RF-202"
    assert root_docs.next_rf_id(text, module_prefix="RF-300") == "RF-301"


def test_crit_31_next_rf_id_empty_requirements_defaults_to_rf_101():
    assert root_docs.next_rf_id("") == "RF-101"
    assert root_docs.next_rf_id("# PRD sin requerimientos") == "RF-101"
    assert root_docs.next_rf_id("", module_prefix="RF-200") == "RF-201"


def test_crit_31_cli_next_rf_id_command(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project)  # Contains RF-101 and RF-102

    rc, out = run_cli(project, "next-rf-id", "--root", str(project))
    assert rc == 0, out
    assert out["ok"] is True
    assert out["next_rf_id"] == "RF-103"

    rc, out = run_cli(project, "next-rf-id", "--root", str(project), "--module", "RF-200")
    assert rc == 0, out
    assert out["next_rf_id"] == "RF-201"


def test_crit_32_spec_intake_protocol_exists():
    repo_root = Path(__file__).resolve().parents[2]
    skill_file = repo_root / "SKILL.md"
    assert skill_file.exists(), "SKILL.md must exist at repository root"

    content = skill_file.read_text(encoding="utf-8")
    assert "INTAKE" in content
    assert "CONFLICT SCAN" in content
    assert "ASK" in content or "DOUBT" in content
    assert "DRAFT" in content
    assert "REVIEW" in content
    assert "next-rf-id" in content

