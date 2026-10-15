"""C1 CRIT-13: root_docs parsers."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import FILLED_REQUIREMENTS  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402


def test_crit_13_parse_rfs_headings_and_criteria():
    rfs = root_docs.parse_rfs(FILLED_REQUIREMENTS)
    assert [r["id"] for r in rfs] == ["RF-101", "RF-102"]

    rf101 = rfs[0]
    assert rf101["title"] == "Registrar Evolución"
    assert rf101["checked"] is False
    assert rf101["description"].startswith("El sistema debe permitir")
    assert [(c["id"], c["type"], c["checked"]) for c in rf101["criteria"]] == [
        ("CRIT-101-1", "automated", False),
        ("CRIT-101-2", "manual", False),
    ]
    assert rfs[1]["checked"] is True
    assert all(c["checked"] for c in rfs[1]["criteria"])


def test_crit_13_parse_glossary():
    glossary = root_docs.parse_glossary(FILLED_REQUIREMENTS)
    assert [g["term"] for g in glossary] == ["Historia Clínica", "Evolución"]
    assert glossary[0]["definition"] == "Registro global único por paciente."
    assert glossary[0]["forbidden"] == ["Ficha médica", "Historial", "Legajo"]
    assert glossary[1]["forbidden"] == ["Nota", "Consulta"]


def test_crit_13_html_comments_are_ignored():
    text = (
        "## 2. Glosario\n"
        "| Término | Definición | Prohibidos |\n| :--- | :--- | :--- |\n"
        "<!--\n| **Ejemplo** | Def. | X. |\n-->\n"
        "## 4. Requerimientos Funcionales\n"
        "<!--\n### [ ] RF-101: Ejemplo\n-->\n"
    )
    stripped = root_docs.strip_html_comments(text)
    assert root_docs.parse_glossary(stripped) == []
    assert root_docs.parse_rfs(stripped) == []


def test_crit_13_find_sections_by_keyword_es_en():
    assert root_docs.section_body(FILLED_REQUIREMENTS, root_docs.REQUIREMENTS_SECTIONS["vision"]) is not None
    en = "## Functional Requirements\n### [ ] RF-1: X\n## Out of Scope\n- none\n"
    assert root_docs.section_body(en, root_docs.REQUIREMENTS_SECTIONS["functional"]) is not None
    assert root_docs.section_body(en, root_docs.REQUIREMENTS_SECTIONS["out_of_scope"]).strip() == "- none"
    assert root_docs.section_body(en, root_docs.REQUIREMENTS_SECTIONS["glossary"]) is None
