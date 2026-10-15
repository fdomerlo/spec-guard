#!/usr/bin/env python3
"""MCP Server for SpecGuard.

Exposes utility, verification, and inspection tools over stdio transport.
Transactional control commands (begin, commit, rollback, checkpoint) and
human approval gates (plan-approve, hotfix-init) are intentionally NOT exposed
as MCP tools — they remain CLI/terminal operations.

Exposed tools:
  - get_next_task(change: str) -> dict
  - verify_phase_gate(change: str, phase: str) -> dict
  - mark_task_completed(change: str, task_id: str) -> dict
  - validate_spec(change: str) -> dict
  - get_rf_status(change: str = "") -> dict
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("spec-guard")


def _sg(*args):
    """Invoca sg CLI vía subprocess y parsea la salida JSON."""
    # Usar sys.executable con módulo spec_guard.cli
    cmd = [sys.executable, "-m", "spec_guard.cli"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and "No module named spec_guard" in r.stderr:
        cli_script = Path(__file__).parent.parent / "cli.py"
        r = subprocess.run([sys.executable, str(cli_script)] + list(args), capture_output=True, text=True)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return {"raw": r.stdout, "stderr": r.stderr}, r.returncode


@mcp.tool()
def get_next_task(change: str) -> dict:
    """Retorna la próxima tarea pendiente de tasks.md para el change dado, o null si no hay."""
    result, _ = _sg("next-task", "--change", change)
    return result


@mcp.tool()
def verify_phase_gate(change: str, phase: str) -> dict:
    """Verifica si la fase solicitada está autorizada por el DAG antes de ejecutarla."""
    result, _ = _sg("verify-gate", "--change", change, "--phase", phase)
    return result


@mcp.tool()
def mark_task_completed(change: str, task_id: str) -> dict:
    """Marca una tarea como completada por ID. Idempotente."""
    result, _ = _sg("mark-task", "--change", change, "--task-id", task_id)
    return result


@mcp.tool()
def validate_spec(change: str) -> dict:
    """Valida estructuralmente objective.md y design.md antes del gate humano.
    Detecta secciones faltantes, placeholders sin completar y preguntas bloqueantes [!]."""
    result, _ = _sg("validate-spec", "--change", change)
    return result


@mcp.tool()
def get_rf_status(change: str = "") -> dict:
    """Estado de los RF de requirements.md (totales, pendientes y, si se indica change, su scope)."""
    args = ["rf-status"] + (["--change", change] if change else [])
    result, _ = _sg(*args)
    return result


def _read_root_doc(name: str) -> str:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        p = parent / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        if (parent / ".spec-guard").exists() or (parent / ".git").exists():
            break
    return f"ERROR: {name} no encontrado en la raíz del proyecto"


@mcp.resource("spec://requirements")
def get_requirements_resource() -> str:
    """Retorna requirements.md (PRD raíz, fuente de verdad funcional)."""
    return _read_root_doc("requirements.md")


@mcp.resource("spec://design")
def get_root_design_resource() -> str:
    """Retorna design.md (SAD raíz, fuente de verdad técnica)."""
    return _read_root_doc("design.md")


@mcp.resource("spec://{change}/objective")
def get_objective_resource(change: str) -> str:
    """Retorna el contenido de objective.md para el change especificado."""
    for base in [".spec-guard", ".state-guard"]:
        p = Path(base) / "changes" / change / "objective.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return f"ERROR: objective.md no encontrado para '{change}'"


@mcp.resource("spec://{change}/design")
def get_design_resource(change: str) -> str:
    """Retorna el contenido de design.md para el change especificado."""
    for base in [".spec-guard", ".state-guard"]:
        p = Path(base) / "changes" / change / "design.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return f"ERROR: design.md no encontrado para '{change}'"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
