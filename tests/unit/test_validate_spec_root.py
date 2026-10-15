"""C1 CRIT-14 / CRIT-15: RF scope and validate-spec root mode."""
import configparser
import json
import os
import sys
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import FILLED_DESIGN, FILLED_REQUIREMENTS, run_cli, write_root_project  # noqa: E402
from spec_guard.core import state_manager  # noqa: E402


def _validate(monkeypatch, project, capsys, change="demo"):
    monkeypatch.chdir(str(project))
    with pytest.raises(SystemExit) as exc:
        state_manager.cmd_validate_spec(Namespace(change=change))
    return exc.value.code, json.loads(capsys.readouterr().out)


def _kinds(res):
    return {i["issue"] for i in res["issues"]}


def test_crit_14_init_change_persists_rf_scope(tmpdir):
    project = Path(str(tmpdir))
    rc, out = run_cli(project, "init-change", "--change", "c1", "--rf", "RF-101, RF-102")
    assert rc == 0, out
    cfg = configparser.ConfigParser()
    cfg.read(project / ".spec-guard" / "changes" / "c1" / "state.ini", encoding="utf-8")
    assert cfg.get("Scope", "rf_ids") == "RF-101, RF-102"
    assert out["rf_ids"] == ["RF-101", "RF-102"]


def test_crit_14_init_change_rejects_invalid_rf_ids(tmpdir):
    project = Path(str(tmpdir))
    rc, out = run_cli(project, "init-change", "--change", "c1", "--rf", "RF-101,FOO")
    assert rc == 4
    assert out["ok"] is False
    assert not (project / ".spec-guard" / "changes" / "c1").exists()


def test_crit_15_root_mode_valid_documents_pass(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    write_root_project(project)
    code, res = _validate(monkeypatch, project, capsys)
    assert res["issues"] == []
    assert code == state_manager.EXIT_OK
    assert res["mode"] == "root"


def test_crit_15_detects_missing_scope(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    write_root_project(project, rf_ids=None)
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    assert "MISSING_RF_SCOPE" in _kinds(res)


def test_crit_15_detects_rf_not_found(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    write_root_project(project, rf_ids="RF-101, RF-999")
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    assert [i["detail"] for i in res["issues"] if i["issue"] == "RF_NOT_FOUND"] == ["RF-999"]


def test_crit_15_detects_missing_section_and_empty_glossary(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    req = FILLED_REQUIREMENTS.split("## 2.")[0] + "## 2. Glosario\n| A | B | C |\n| :- | :- | :- |\n" + \
        "## 4." + FILLED_REQUIREMENTS.split("## 4.")[1]
    req = req.replace("## 5. Fuera del Alcance (Out of Scope)\n- NO implementar pasarelas de pago.\n", "")
    design = FILLED_DESIGN.replace("## 5. Infraestructura y Seguridad", "## 5. Otros")
    write_root_project(project, requirements=req, design=design)
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    missing = {(i["file"], i["detail"]) for i in res["issues"] if i["issue"] == "MISSING_SECTION"}
    assert ("requirements.md", "roles") in missing
    assert ("requirements.md", "out_of_scope") in missing
    assert ("design.md", "security") in missing
    assert "EMPTY_GLOSSARY" in _kinds(res)


def test_crit_15_detects_rf_quality_issues(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    bad_rf = (
        "### [ ] RF-103: Sin calidad\n"
        "- **Criterios de Aceptación:**\n"
        "  - [ ] CRIT-999-1 [automated]: ID que no corresponde.\n"
    )
    req = FILLED_REQUIREMENTS.replace("## 5. Fuera", bad_rf + "\n## 5. Fuera")
    write_root_project(project, requirements=req, rf_ids="RF-103")
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    kinds = _kinds(res)
    assert {"MISSING_DESCRIPTION", "INSUFFICIENT_CRITERIA", "CRIT_ID_MISMATCH"} <= kinds


def test_crit_15_detects_blocking_open_question(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    req = FILLED_REQUIREMENTS.replace("- Ninguna.", "- [!] ¿Quién aprueba?")
    write_root_project(project, requirements=req)
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    assert "BLOCKING_OPEN_QUESTION" in _kinds(res)


def test_crit_15_legacy_mode_unchanged_when_objective_present(monkeypatch, tmpdir, capsys):
    project = Path(str(tmpdir))
    change_dir = write_root_project(project)
    (change_dir / "objective.md").write_text("# Objective\n## Intención\nX\n", encoding="utf-8")
    code, res = _validate(monkeypatch, project, capsys)
    assert code == state_manager.EXIT_VALIDATION
    assert res["mode"] == "legacy"
    assert any(i["file"] == "objective.md" and i["issue"] == "MISSING_SECTION" for i in res["issues"])
