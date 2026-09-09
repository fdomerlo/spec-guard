import os
import sys
import json
from argparse import Namespace
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts")))
import state_manager


def setup_change(tmpdir, objective_content=None, design_content=None):
    change_dir = os.path.join(tmpdir, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    
    if objective_content is not None:
        with open(os.path.join(change_dir, "objective.md"), "w", encoding="utf-8") as f:
            f.write(objective_content)
            
    if design_content is not None:
        with open(os.path.join(change_dir, "design.md"), "w", encoding="utf-8") as f:
            f.write(design_content)


VALID_OBJECTIVE = """# Objective: Test
## Intención
Resolver problema de prueba
## Alcance
### Dentro del Alcance
- Entregable 1
### Fuera del Alcance
- Módulos externos no relacionados
## Criterios de Éxito
- [ ] Test pasa
## Preguntas Abiertas
- Ninguna
"""

VALID_DESIGN = """# Design: Test
## Enfoque Técnico
Estrategia de prueba
## Áreas Afectadas
| Área | Impacto |
## Decisiones de Arquitectura
### Decisión 1
## Flujo de Datos
ASCII diagram
## Archivos Afectados
| Archivo | Acción |
"""


def test_validate_spec_success(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    setup_change(str(tmpdir), VALID_OBJECTIVE, VALID_DESIGN)
    
    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_OK
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["issues"] == []


def test_validate_spec_missing_design_file(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    setup_change(str(tmpdir), objective_content=VALID_OBJECTIVE, design_content=None)
    
    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    issues = res["issues"]
    assert any(i["issue"] == "MISSING_FILE" and i["file"] == "design.md" for i in issues)


def test_validate_spec_blocking_open_question(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    objective_with_blocking = VALID_OBJECTIVE + "\n- [!] Pregunta crítica sin resolver\n"
    setup_change(str(tmpdir), objective_with_blocking, VALID_DESIGN)
    
    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    issues = res["issues"]
    assert any(i["issue"] == "BLOCKING_OPEN_QUESTION" and i["file"] == "objective.md" for i in issues)


def test_validate_spec_missing_section(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    design_missing_section = """# Design: Test
## Enfoque Técnico
Estrategia de prueba
## Áreas Afectadas
| Área | Impacto |
## Decisiones de Arquitectura
### Decisión 1
## Archivos Afectados
| Archivo | Acción |
"""
    setup_change(str(tmpdir), VALID_OBJECTIVE, design_missing_section)
    
    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    issues = res["issues"]
    assert any(i["issue"] == "MISSING_SECTION" and i["detail"] == "## Flujo de Datos" for i in issues)


def test_validate_spec_unresolved_placeholder(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    objective_unresolved = VALID_OBJECTIVE.replace("Resolver problema de prueba", "{Qué problema resuelve y por qué}")
    setup_change(str(tmpdir), objective_unresolved, VALID_DESIGN)
    
    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    issues = res["issues"]
    assert any(i["issue"] == "UNRESOLVED_PLACEHOLDER" and i["file"] == "objective.md" for i in issues)


def test_validate_spec_missing_out_of_scope(monkeypatch, tmpdir, capsys):
    monkeypatch.chdir(tmpdir)
    objective_no_oos = VALID_OBJECTIVE.replace("### Fuera del Alcance\n- Módulos externos no relacionados\n", "")
    setup_change(str(tmpdir), objective_no_oos, VALID_DESIGN)

    args = Namespace(change="test-change")
    with pytest.raises(SystemExit) as exc_info:
        state_manager.cmd_validate_spec(args)
    assert exc_info.value.code == state_manager.EXIT_VALIDATION

    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is False
    issues = res["issues"]
    assert any(i["issue"] == "MISSING_OUT_OF_SCOPE" and i["file"] == "objective.md" for i in issues)
