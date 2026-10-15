"""Tests para el comando sg glossary-check (CRIT-22, CRIT-23, CRIT-24)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import run_cli, write_root_project  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402


def test_crit_22_detects_forbidden_synonyms_in_identifiers(tmpdir):
    """CRIT-22: Detecta sinónimos prohibidos en snake_case, camelCase y PascalCase."""
    project = Path(str(tmpdir))
    write_root_project(project)
    src_dir = project / "src"
    src_dir.mkdir(parents=True)

    # El glosario prohíbe 'Historial' y 'Ficha médica' para 'Historia Clínica',
    # y 'Nota' para 'Evolución'.
    code_snake = "def consultar_historial_paciente(paciente_id):\n    pass\n"
    code_camel = "def obtenerFichaMedica(pacienteId):\n    pass\n"
    code_pascal = "# Uso de NotaClinica como identificador\nnota_val = 1\n"

    (src_dir / "service.py").write_text(code_snake + code_camel + code_pascal, encoding="utf-8")

    rc, out = run_cli(project, "glossary-check", "--root", str(project), "--paths", str(src_dir / "service.py"))
    assert rc == 0  # Solo warnings -> exit 0
    assert out["ok"] is True
    assert out["critical_count"] == 0
    assert out["warning_count"] >= 3

    forbidden_found = [v["forbidden"] for v in out["violations"]]
    assert any("Historial" in f for f in forbidden_found)
    assert any("Ficha médica" in f for f in forbidden_found)
    assert any("Nota" in f for f in forbidden_found)


def test_crit_23_no_false_positives_with_canonical_terms(tmpdir):
    """CRIT-23: No genera falsos positivos con el término canónico permitido ni substrings arbitrarios."""
    project = Path(str(tmpdir))
    write_root_project(project)
    src_dir = project / "src"
    src_dir.mkdir(parents=True)

    # 'Historia Clínica' y 'Evolución' son canónicos permitidos.
    # 'historiador' o 'evolutivo' no deben matchear en límite de palabra.
    code_clean = (
        "class HistoriaClinica(models.Model):\n"
        "    pass\n\n"
        "def registrar_evolucion(historia_clinica_id):\n"
        "    historiador = 'test'\n"
        "    cambio_evolutivo = True\n"
        "    return historia_clinica_id\n"
    )
    (src_dir / "models.py").write_text(code_clean, encoding="utf-8")

    rc, out = run_cli(project, "glossary-check", "--root", str(project), "--paths", str(src_dir / "models.py"))
    assert rc == 0, out
    assert out["ok"] is True
    assert out["critical_count"] == 0
    assert out["warning_count"] == 0
    assert out["violations"] == []


def test_crit_24_class_definition_triggers_critical_exit_4(tmpdir):
    """CRIT-24: Definición de clase/entidad con término prohibido da CRITICAL y exit code 4."""
    project = Path(str(tmpdir))
    write_root_project(project)
    src_dir = project / "src"
    src_dir.mkdir(parents=True)

    # 'Historial' está prohibido para 'Historia Clínica'
    code_bad_class = (
        "class HistorialPaciente(models.Model):\n"
        "    id = models.UUIDField(primary_key=True)\n"
    )
    (src_dir / "bad_models.py").write_text(code_bad_class, encoding="utf-8")

    rc, out = run_cli(project, "glossary-check", "--root", str(project), "--paths", str(src_dir / "bad_models.py"))
    assert rc == 4, out
    assert out["ok"] is False
    assert out["critical_count"] >= 1
    criticals = [v for v in out["violations"] if v["severity"] == "CRITICAL"]
    assert len(criticals) >= 1
    assert criticals[0]["canonical"] == "Historia Clínica"
    assert "class HistorialPaciente" in criticals[0]["line_text"]


def test_crit_24_strict_flag_fails_on_warnings(tmpdir):
    """CRIT-24: Con --strict, incluso violaciones WARNING devuelven exit code 4."""
    project = Path(str(tmpdir))
    write_root_project(project)
    src_dir = project / "src"
    src_dir.mkdir(parents=True)

    code_warning = "def consultar_historial(): pass\n"
    (src_dir / "warn.py").write_text(code_warning, encoding="utf-8")

    # Sin --strict -> exit 0
    rc, out = run_cli(project, "glossary-check", "--root", str(project), "--paths", str(src_dir / "warn.py"))
    assert rc == 0
    assert out["warning_count"] == 1

    # Con --strict -> exit 4
    rc, out = run_cli(project, "glossary-check", "--root", str(project), "--paths", str(src_dir / "warn.py"), "--strict")
    assert rc == 4
    assert out["ok"] is False
