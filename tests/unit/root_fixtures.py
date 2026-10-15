"""Shared fixtures for 2-File Root Protocol tests (not a test module)."""
import os
import subprocess
import sys
from pathlib import Path

REPO_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

FILLED_REQUIREMENTS = """# Demo - PRD
## 1. Visión General del Producto
- **Problema central:** Registrar tratamientos odontológicos.
- **Objetivo principal:** Historias clínicas auditables.

## 2. Glosario Estricto de Dominio (Token Anchoring)
| Término Permitido | Definición Precisa | Sinónimos Prohibidos (Rechazar) |
| :--- | :--- | :--- |
| **Historia Clínica** | Registro global único por paciente. | Ficha médica, Historial, Legajo. |
| **Evolución** | Entrada fechada dentro de una Historia Clínica. | Nota, Consulta. |

## 3. Roles de Usuario y Permisos
- **Odontólogo:** Puede crear Evoluciones. No puede eliminar registros.

## 4. Requerimientos Funcionales
### [ ] RF-101: Registrar Evolución
- **Módulo:** RF-100 Historias Clínicas
- **Descripción:** El sistema debe permitir registrar una Evolución.
- **Criterios de Aceptación:**
  - [ ] CRIT-101-1 [automated]: El formulario valida campos vía HTMX.
  - [ ] CRIT-101-2 [manual]: El odontólogo confirma la usabilidad.
- **Flujo de Excepción:** Si falta la descripción, responder 422.

### [x] RF-102: Listar Evoluciones
- **Descripción:** El sistema debe listar las Evoluciones.
- **Criterios de Aceptación:**
  - [x] CRIT-102-1 [automated]: Devuelve un fragmento HTML.
  - [x] CRIT-102-2 [automated]: Ordena por fecha descendente.

## 5. Fuera del Alcance (Out of Scope)
- NO implementar pasarelas de pago.

## 6. Preguntas Abiertas
- Ninguna.
"""

FILLED_DESIGN = """# Demo - SAD
## 1. Stack Tecnológico Obligatorio
- **Backend:** Python (Django 5.x).
## 2. Modelo de Datos y Esquema de Persistencia
### Entidad: `HistoriaClinica`
- `id`: UUID (Primary Key)
## 3. Contratos de Interfaz y Endpoints (API / HTMX)
- **GET `/historias/<uuid:id>/evoluciones/`**: fragmento HTML.
## 4. Patrones de Diseño y Reglas de Código
- Lógica de negocio en `services.py`.
## 5. Infraestructura y Seguridad
- Secretos solo desde `.env`.
"""


def write_root_project(root, requirements=FILLED_REQUIREMENTS, design=FILLED_DESIGN,
                       change="demo", rf_ids="RF-101", lock_phase="plan"):
    root = Path(root)
    if requirements is not None:
        (root / "requirements.md").write_text(requirements, encoding="utf-8")
    if design is not None:
        (root / "design.md").write_text(design, encoding="utf-8")
    change_dir = root / ".spec-guard" / "changes" / change
    change_dir.mkdir(parents=True, exist_ok=True)
    scope = f"\n[Scope]\nrf_ids = {rf_ids}\n" if rf_ids is not None else ""
    (change_dir / "state.ini").write_text(
        "[Metadata]\nschema_version = 2\n\n"
        "[Transaction]\ntxn_status = idle\ntxn_phase = None\n\n"
        f"[Graph]\nlock_phase = {lock_phase}\ncurrent_phase = none\n"
        "completed_phases = \npending_phases = plan, execute, verify\n" + scope,
        encoding="utf-8",
    )
    return change_dir


def run_cli(cwd, *args):
    import json
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_PKG_ROOT
    res = subprocess.run(
        [sys.executable, "-m", "spec_guard.cli", *args],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )
    try:
        payload = json.loads(res.stdout)
    except ValueError:
        payload = {"raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload
