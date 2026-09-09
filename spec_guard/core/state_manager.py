#!/usr/bin/env python3
"""
state_manager.py — Motor ACID de SpecGuard (v2: esquema de 3 fases)

DAG colapsado a 3 fases principales: plan → execute → verify
archive es el Paso 9 dentro de verify.
El lock de plan solo se emite tras aprobación humana explícita out-of-band.
"""
import argparse
import configparser
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from spec_guard.core.locking import (
    try_acquire_lockfile,
    release_lockfile,
    is_stale,
    check_lock_status,
    with_write_lock,
)

__all__ = [
    "main",
    "cmd_begin",
    "cmd_commit",
    "cmd_rollback",
    "cmd_checkpoint",
    "cmd_status",
    "cmd_check_completion",
    "cmd_mark_task",
    "cmd_migrate",
    "cmd_plan_approve",
    "cmd_verify_gate",
    "cmd_next_task",
    "cmd_validate_spec",
    "is_v1_state",
    "_migrate_v1_to_v2",
    "get_list",
    "set_list",
    "load_state",
    "save_state",
    "resolve_change_dir",
    "STATE_FILE",
    "LOCK_FILE",
    "WRITE_LOCK_FILE",
    "TASKS_FILE",
    "DEFAULT_TTL",
    "MAX_SUMMARY_CHARS",
    "SCHEMA_VERSION",
    "EXIT_OK",
    "EXIT_GENERIC",
    "EXIT_LOCK_CONFLICT",
    "EXIT_BAD_TRANSITION",
    "EXIT_VALIDATION",
    "EXIT_GATE_REQUIRED",
    "TRANSITIONS",
    "V1_TO_V2_PHASE",
]

DEFAULT_TTL = 1800
MAX_SUMMARY_CHARS = 2000  # ~500 tokens ≈ 2000 chars

SCHEMA_VERSION = "2"  # v1 = 8 fases, v2 = 3 fases

# Exit codes diferenciados para que modelos débiles (free-tier) puedan
# distinguir categorías de error por código numérico.
EXIT_OK = 0
EXIT_GENERIC = 1        # state.ini no encontrado, error inesperado
EXIT_LOCK_CONFLICT = 2  # lock activo (otra sesión), reintentable
EXIT_BAD_TRANSITION = 3 # transición inválida en el DAG, no reintentar
EXIT_VALIDATION = 4     # datos de entrada inválidos (summary muy largo, etc.)
EXIT_GATE_REQUIRED = 5  # gate humano no cumplido — el LLM no puede resolver esto

# Matchea: "- [ ] [T003] Descripción" o "- [x] Descripción" (ID opcional)
TASK_LINE_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(?:\[([^\]]+)\]\s*)?(.*)$")

# ─── DAG v2 (3 fases) ──────────────────────────────────────────────────────
TRANSITIONS = {
    "plan":    "execute",
    "execute": "verify",
    "hotfix":  "execute",   # hotfix bypass: saltea plan, entra directo a execute
}

# ─── Mapa de migración v1 → v2 ─────────────────────────────────────────────
V1_TO_V2_PHASE = {
    "explore":  "plan",
    "propose":  "plan",
    "spec":     "plan",
    "design":   "plan",
    "tasks":    "execute",
    "apply":    "execute",
    "verify":   "verify",
    "archive":  "verify",
}


def resolve_change_dir(change_name: str) -> Path:
    """Resuelve la ruta a la carpeta del cambio, soportando .spec-guard y .state-guard."""
    p_spec = Path(f".spec-guard/changes/{change_name}")
    if p_spec.exists():
        return p_spec
    p_state = Path(f".state-guard/changes/{change_name}")
    if p_state.exists():
        return p_state

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate_spec = parent / ".spec-guard" / "changes" / change_name
        if candidate_spec.exists():
            return candidate_spec
        candidate_state = parent / ".state-guard" / "changes" / change_name
        if candidate_state.exists():
            return candidate_state

    if (cwd / ".state-guard").exists():
        return cwd / ".state-guard" / "changes" / change_name
    return cwd / ".spec-guard" / "changes" / change_name


class _PathFormatter:
    """Helper de compatibilidad que responde a .format(change=...) y a str()."""
    def __init__(self, filename: str):
        self.filename = filename

    def format(self, change: str, **kwargs) -> str:
        return str(resolve_change_dir(change) / self.filename)

    def __str__(self) -> str:
        return f".spec-guard/changes/{{change}}/{self.filename}"


STATE_FILE = _PathFormatter("state.ini")
LOCK_FILE = _PathFormatter(".lock")
WRITE_LOCK_FILE = _PathFormatter(".write-lock")
TASKS_FILE = _PathFormatter("tasks.md")


def load_state(change_name: str):
    change_dir = resolve_change_dir(change_name)
    path = str(change_dir / "state.ini")
    config = configparser.ConfigParser()
    if not os.path.exists(path):
        print(f"ERROR: No se encontró el state.ini para '{change_name}'")
        sys.exit(EXIT_GENERIC)
    config.read(path, encoding="utf-8")
    return config, path


def save_state(config: configparser.ConfigParser, path: str):
    if not config.has_section("Metadata"):
        config.add_section("Metadata")
    config.set("Metadata", "last_updated", datetime.now().isoformat())
    config.set("Metadata", "schema_version", SCHEMA_VERSION)
    with open(path, "w", encoding="utf-8") as f:
        config.write(f)


def get_list(config: configparser.ConfigParser, section: str, option: str):
    val = config.get(section, option, fallback="").strip()
    return [x.strip() for x in val.split(",")] if val else []


def set_list(config: configparser.ConfigParser, section: str, option: str, lst):
    config.set(section, option, ", ".join(lst))


# ─── Detección de schema v1 ────────────────────────────────────────────────

def is_v1_state(config: configparser.ConfigParser) -> bool:
    """Retorna True si el state.ini es v1 (esquema de 8 fases)."""
    version = config.get("Metadata", "schema_version", fallback="1")
    return version == "1"


def _migrate_v1_to_v2(config: configparser.ConfigParser, path: str):
    """
    Migra in-place un state.ini v1 al esquema v2.
    """
    lock_phase_v1 = config.get("Graph", "lock_phase", fallback="plan")
    completed_v1 = get_list(config, "Graph", "completed_phases")
    txn_phase_v1 = config.get("Transaction", "txn_phase", fallback="None")

    lock_phase_v2 = V1_TO_V2_PHASE.get(lock_phase_v1, "plan")

    completed_v2 = []
    if any(p in completed_v1 for p in ["explore", "propose", "spec", "design"]):
        if any(p in completed_v1 for p in ["tasks", "apply", "verify", "archive"]):
            completed_v2.append("plan")
    if any(p in completed_v1 for p in ["tasks", "apply"]):
        if any(p in completed_v1 for p in ["verify", "archive"]):
            completed_v2.append("execute")
    if "verify" in completed_v1 or "archive" in completed_v1:
        completed_v2.append("verify")

    all_phases = ["plan", "execute", "verify"]
    pending_v2 = [p for p in all_phases if p not in completed_v2]

    txn_phase_v2 = V1_TO_V2_PHASE.get(txn_phase_v1, "None") if txn_phase_v1 != "None" else "None"

    config.set("Graph", "lock_phase", lock_phase_v2)
    config.set("Graph", "current_phase", completed_v2[-1] if completed_v2 else "none")
    set_list(config, "Graph", "completed_phases", completed_v2)
    set_list(config, "Graph", "pending_phases", pending_v2)
    if txn_phase_v2 != "None":
        config.set("Transaction", "txn_phase", txn_phase_v2)

    if not config.has_section("Session"):
        config.add_section("Session")
    config.set("Session", "migrated_from_schema", "v1")
    config.set("Session", "migrated_at", datetime.now().isoformat())

    save_state(config, path)
    return config, path


# ─── Comandos ───────────────────────────────────────────────────────────────

def cmd_begin(args):
    lock_path = LOCK_FILE.format(change=args.change)

    def _do():
        config, path = load_state(args.change)

        if is_v1_state(config):
            config, path = _migrate_v1_to_v2(config, path)
            print("INFO: state.ini v1 migrado automáticamente a v2 (3 fases).")

        status = config.get("Transaction", "txn_status", fallback="idle")
        started_at = config.get("Transaction", "txn_started_at", fallback=None)

        if status == "in_progress" and not is_stale(started_at, args.ttl):
            print("ERROR: Ya hay una transacción en progreso.")
            sys.exit(EXIT_LOCK_CONFLICT)

        if status == "in_progress" and is_stale(started_at, args.ttl):
            release_lockfile(lock_path)

        if not try_acquire_lockfile(lock_path):
            print("ERROR: Ya hay una transacción en progreso (lock activo).")
            sys.exit(EXIT_LOCK_CONFLICT)

        config.set("Transaction", "txn_status", "in_progress")
        config.set("Transaction", "txn_phase", args.phase)
        config.set("Transaction", "txn_started_at", datetime.now().isoformat())
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO_ROOT))
            if res.returncode == 0 and res.stdout.strip():
                config.set("Transaction", "base_commit", res.stdout.strip())
        except Exception:
            pass
        save_state(config, path)
        print(f"SUCCESS|BEGIN transaccional iniciado para fase: {args.phase}")

    with_write_lock(WRITE_LOCK_FILE.format(change=args.change), _do)


def cmd_commit(args):
    def _do():
        config, path = load_state(args.change)

        if is_v1_state(config):
            config, path = _migrate_v1_to_v2(config, path)

        if config.get("Transaction", "txn_status", fallback="idle") != "in_progress":
            print("ERROR: No hay transacción en progreso para hacer commit.")
            sys.exit(EXIT_GENERIC)

        phase = config.get("Transaction", "txn_phase")
        expected_next = TRANSITIONS.get(phase)
        if expected_next != args.next_phase:
            print(
                f"ERROR: Transición inválida. Desde '{phase}' el DAG solo permite "
                f"'{expected_next}', no '{args.next_phase}'."
            )
            sys.exit(EXIT_BAD_TRANSITION)

        # ── GATE ENFORCEMENT ────────────────────────────────────────────────
        if phase == "plan":
            gate_token = config.get("Gate", "plan_gate_token", fallback=None)
            if not gate_token:
                print(
                    "ERROR: GATE — El commit de 'plan' requiere aprobación humana explícita.\n"
                    "       Ejecutá desde tu terminal: sg plan-approve --change "
                    f"{args.change}\n"
                    f"       y luego confirma con: sg plan-confirm --change {args.change}\n"
                    "       Este comando solo funciona en una terminal humana (fuera del workspace)."
                )
                sys.exit(EXIT_GATE_REQUIRED)
        # ── FIN GATE ENFORCEMENT ────────────────────────────────────────────

        config.set("Graph", "current_phase", phase)
        config.set("Graph", "lock_phase", args.next_phase)

        completed = get_list(config, "Graph", "completed_phases")
        if phase not in completed:
            completed.append(phase)
            set_list(config, "Graph", "completed_phases", completed)

        pending = get_list(config, "Graph", "pending_phases")
        if phase in pending:
            pending.remove(phase)
            set_list(config, "Graph", "pending_phases", pending)

        config.set("Transaction", "txn_status", "idle")
        config.set("Transaction", "txn_phase", "None")

        if config.has_section("Gate"):
            config.remove_option("Gate", "plan_gate_token")

        auto_summary = (
            f"fase_completada={phase}\n"
            f"siguiente_fase={args.next_phase}\n"
            f"completadas={', '.join(completed)}\n"
            f"pendientes={', '.join(pending)}"
        )
        if not config.has_section("Session"):
            config.add_section("Session")
        config.set("Session", "session_summary", auto_summary)

        save_state(config, path)
        release_lockfile(LOCK_FILE.format(change=args.change))
        print(f"SUCCESS|COMMIT exitoso. lock_phase={args.next_phase}")
        print(f"⚠️ FASE {phase} COMPLETADA — sus instrucciones ya no aplican.")

    with_write_lock(WRITE_LOCK_FILE.format(change=args.change), _do)


def cmd_rollback(args):
    def _do():
        config, path = load_state(args.change)
        if config.get("Transaction", "txn_status", fallback="idle") != "in_progress":
            print("ERROR: No hay transacción en progreso para revertir.")
            sys.exit(EXIT_GENERIC)
        config.set("Transaction", "txn_status", "idle")
        config.set("Transaction", "txn_phase", "None")
        save_state(config, path)
        release_lockfile(LOCK_FILE.format(change=args.change))
        print("SUCCESS|ROLLBACK ejecutado. txn_status restaurado a idle.")

    with_write_lock(WRITE_LOCK_FILE.format(change=args.change), _do)


def cmd_checkpoint(args):
    def _do():
        if len(args.summary) > MAX_SUMMARY_CHARS:
            print(
                f"ERROR: session_summary excede el límite "
                f"({len(args.summary)}/{MAX_SUMMARY_CHARS} chars). "
                f"Resumí el contenido y reintentá."
            )
            sys.exit(EXIT_VALIDATION)
        config, path = load_state(args.change)
        if not config.has_section("Session"):
            config.add_section("Session")
        config.set("Session", "session_summary", args.summary)
        save_state(config, path)
        print("SUCCESS|CHECKPOINT guardado en session_summary.")

    with_write_lock(WRITE_LOCK_FILE.format(change=args.change), _do)


def cmd_check_completion(args):
    path = TASKS_FILE.format(change=args.change)
    if not os.path.exists(path):
        payload = {
            "estado_tareas": "N/A", "total": 0, "completed": 0,
            "all_complete": False, "last_completed_id": None,
            "last_completed_desc": None
        }
        if args.json:
            print(json.dumps(payload))
        else:
            for k, v in payload.items():
                print(f"{k}={v}")
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = 0
    completed = 0
    last_completed_id = None
    last_completed_desc = None

    for line in lines:
        m = TASK_LINE_RE.match(line)
        if not m:
            continue
        total += 1
        checked = m.group(1).lower() == "x"
        task_id = m.group(2) or ""
        desc = m.group(3).strip()
        if checked:
            completed += 1
            last_completed_id = task_id if task_id else last_completed_id
            last_completed_desc = desc[:100] if desc else last_completed_desc

    all_complete = total > 0 and completed == total
    estado = f"{completed}/{total}"
    if last_completed_id:
        estado += f" — última: [{last_completed_id}] {last_completed_desc}"
    elif last_completed_desc:
        estado += f" — última: {last_completed_desc}"

    if args.json:
        print(json.dumps({
            "estado_tareas": estado,
            "total": total,
            "completed": completed,
            "all_complete": all_complete,
            "last_completed_id": last_completed_id,
            "last_completed_desc": last_completed_desc,
        }))
    else:
        print(f"estado_tareas={estado}")
        print(f"total={total}")
        print(f"completed={completed}")
        print(f"all_complete={'true' if all_complete else 'false'}")
        print(f"last_completed_id={last_completed_id or 'None'}")
        print(f"last_completed_desc={last_completed_desc or 'None'}")


def cmd_mark_task(args):
    path = TASKS_FILE.format(change=args.change)
    if not os.path.exists(path):
        result = {"status": "ERROR", "message": f"tasks.md no encontrado para '{args.change}'"}
        print(json.dumps(result))
        sys.exit(EXIT_GENERIC)

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    already_done = False
    new_lines = []

    for line in lines:
        m = TASK_LINE_RE.match(line)
        if m and m.group(2) == args.task_id:
            found = True
            if m.group(1).lower() == "x":
                already_done = True
                new_lines.append(line)
            else:
                new_lines.append(line.replace("[ ]", "[x]", 1))
        else:
            new_lines.append(line)

    if not found:
        result = {"status": "ERROR", "message": f"Tarea '{args.task_id}' no encontrada en tasks.md"}
        print(json.dumps(result))
        sys.exit(EXIT_VALIDATION)

    if already_done:
        result = {"status": "ALREADY_DONE", "task_id": args.task_id,
                  "message": f"Tarea '{args.task_id}' ya estaba completada"}
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        result = {"status": "SUCCESS", "task_id": args.task_id,
                  "message": f"Tarea '{args.task_id}' marcada como completada"}

    print(json.dumps(result))


def cmd_migrate(args):
    config, path = load_state(args.change)
    if not is_v1_state(config):
        print(json.dumps({
            "status": "ALREADY_V2",
            "schema_version": config.get("Metadata", "schema_version", fallback="2")
        }))
        return
    config, path = _migrate_v1_to_v2(config, path)
    lock_phase = config.get("Graph", "lock_phase", fallback="unknown")
    completed = get_list(config, "Graph", "completed_phases")
    print(json.dumps({
        "status": "SUCCESS",
        "message": "state.ini migrado de v1 (8 fases) a v2 (3 fases)",
        "lock_phase_v2": lock_phase,
        "completed_phases_v2": completed,
    }))


def cmd_status(args):
    config, _ = load_state(args.change)
    txn_status = config.get("Transaction", "txn_status", fallback="idle")
    txn_phase = config.get("Transaction", "txn_phase", fallback="None")
    started_at = config.get("Transaction", "txn_started_at", fallback=None)
    lock_phase = config.get("Graph", "lock_phase", fallback="None")
    schema_version = config.get("Metadata", "schema_version", fallback="1")

    lock_path = LOCK_FILE.format(change=args.change)
    lock_state = check_lock_status(lock_path, started_at, args.ttl)

    if args.json:
        print(json.dumps({
            "txn_status": txn_status,
            "txn_phase": txn_phase,
            "lock_phase": lock_phase,
            "lock_state": lock_state,
            "schema_version": schema_version,
        }))
    else:
        print(f"txn_status={txn_status}")
        print(f"txn_phase={txn_phase}")
        print(f"lock_phase={lock_phase}")
        print(f"lock_state={lock_state}")
        print(f"schema_version={schema_version}")


def cmd_plan_approve(args):
    def _do():
        config, path = load_state(args.change)
        if not config.has_section("Gate"):
            config.add_section("Gate")
        token = datetime.now().isoformat()
        config.set("Gate", "plan_gate_token", token)
        config.set("Gate", "plan_approved_at", token)
        config.set("Gate", "plan_approved_by", args.approved_by or "human")
        if args.bypass_reason:
            config.set("Gate", "hotfix_bypass_reason", args.bypass_reason)
            config.set("Gate", "hotfix_bypass", "true")
        save_state(config, path)
        print(json.dumps({
            "status": "APPROVED",
            "plan_gate_token": token,
            "change": args.change,
            "approved_at": token,
        }))

    with_write_lock(WRITE_LOCK_FILE.format(change=args.change), _do)


def cmd_verify_gate(args):
    config, _ = load_state(args.change)
    lock_phase = config.get("Graph", "lock_phase", fallback="None")
    txn_status = config.get("Transaction", "txn_status", fallback="idle")
    schema_version = config.get("Metadata", "schema_version", fallback="1")

    ok = (lock_phase == args.phase)
    result = {
        "gate_ok": ok,
        "requested_phase": args.phase,
        "lock_phase": lock_phase,
        "txn_status": txn_status,
        "schema_version": schema_version,
    }
    if not ok:
        result["error"] = (
            f"Fase '{args.phase}' no está autorizada. "
            f"El DAG requiere '{lock_phase}'."
        )
    print(json.dumps(result))
    if not ok:
        sys.exit(EXIT_BAD_TRANSITION)


def cmd_next_task(args):
    path = TASKS_FILE.format(change=args.change)
    if not os.path.exists(path):
        print(json.dumps({"status": "NO_TASKS_FILE", "task": None}))
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        m = TASK_LINE_RE.match(line)
        if m and m.group(1) != "x" and m.group(1) != "X":
            task_id = m.group(2) or None
            desc = m.group(3).strip()
            print(json.dumps({
                "status": "OK",
                "task": {
                    "id": task_id,
                    "description": desc,
                    "raw_line": line.rstrip(),
                }
            }))
            return

    print(json.dumps({"status": "ALL_COMPLETE", "task": None}))


def cmd_validate_spec(args):
    change_dir = resolve_change_dir(args.change)
    objective_path = change_dir / "objective.md"
    design_path = change_dir / "design.md"

    issues = []

    for label, path, required_sections in [
        ("objective.md", objective_path, ["## Intención", "## Alcance", "## Criterios de Éxito"]),
        ("design.md", design_path, ["## Decisiones de Arquitectura", "## Flujo de Datos", "## Archivos Afectados"]),
    ]:
        if not path.exists():
            issues.append({"file": label, "issue": "MISSING_FILE"})
            continue
        content = path.read_text(encoding="utf-8")
        if "[!]" in content:
            issues.append({"file": label, "issue": "BLOCKING_OPEN_QUESTION",
                            "detail": "Hay preguntas abiertas marcadas [!] sin resolver."})
        for section in required_sections:
            if section not in content:
                issues.append({"file": label, "issue": "MISSING_SECTION", "detail": section})
        unresolved = re.findall(r"\{[A-ZÁÉÍÓÚa-záéíóú][^}]{3,80}\}", content)
        if unresolved:
            issues.append({"file": label, "issue": "UNRESOLVED_PLACEHOLDER",
                            "detail": unresolved[:5]})
        if label == "objective.md":
            has_oos = any(k in content.lower() for k in ["fuera de alcance", "fuera del alcance", "out of scope"])
            if not has_oos:
                issues.append({
                    "file": label,
                    "issue": "MISSING_OUT_OF_SCOPE",
                    "detail": "Falta definir explícitamente qué queda fuera de alcance (Out of scope)."
                })

    result = {"ok": len(issues) == 0, "change": args.change, "issues": issues}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(EXIT_OK if not issues else EXIT_VALIDATION)


def main():
    parser = argparse.ArgumentParser(
        description="State Manager — Motor ACID de SpecGuard (v2: 3 fases)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # begin
    p_begin = subparsers.add_parser("begin")
    p_begin.add_argument("--change", required=True)
    p_begin.add_argument("--phase", required=True)
    p_begin.add_argument("--ttl", type=int, default=DEFAULT_TTL)

    # commit
    p_commit = subparsers.add_parser("commit")
    p_commit.add_argument("--change", required=True)
    p_commit.add_argument("--next-phase", required=True)

    # rollback
    p_rollback = subparsers.add_parser("rollback")
    p_rollback.add_argument("--change", required=True)

    # checkpoint
    p_checkpoint = subparsers.add_parser("checkpoint")
    p_checkpoint.add_argument("--change", required=True)
    p_checkpoint.add_argument("--summary", required=True)

    # status
    p_status = subparsers.add_parser("status")
    p_status.add_argument("--change", required=True)
    p_status.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    p_status.add_argument("--json", action="store_true",
                          help="Salida en JSON")

    # check-completion
    p_check = subparsers.add_parser("check-completion")
    p_check.add_argument("--change", required=True)
    p_check.add_argument("--json", action="store_true",
                         help="Salida en JSON")

    # mark-task
    p_mark = subparsers.add_parser("mark-task")
    p_mark.add_argument("--change", required=True)
    p_mark.add_argument("--task-id", required=True)

    # migrate
    p_migrate = subparsers.add_parser("migrate")
    p_migrate.add_argument("--change", required=True)

    # plan-approve
    p_plan = subparsers.add_parser("plan-approve")
    p_plan.add_argument("--change", required=True)
    p_plan.add_argument("--approved-by", default="human")
    p_plan.add_argument("--bypass-reason", default=None)

    # verify-gate
    p_vgate = subparsers.add_parser("verify-gate")
    p_vgate.add_argument("--change", required=True)
    p_vgate.add_argument("--phase", required=True)

    # next-task
    p_ntask = subparsers.add_parser("next-task")
    p_ntask.add_argument("--change", required=True)

    # validate-spec
    p_val = subparsers.add_parser("validate-spec")
    p_val.add_argument("--change", required=True)

    args = parser.parse_args()

    commands = {
        "begin": cmd_begin,
        "commit": cmd_commit,
        "rollback": cmd_rollback,
        "checkpoint": cmd_checkpoint,
        "status": cmd_status,
        "check-completion": cmd_check_completion,
        "mark-task": cmd_mark_task,
        "migrate": cmd_migrate,
        "plan-approve": cmd_plan_approve,
        "verify-gate": cmd_verify_gate,
        "next-task": cmd_next_task,
        "validate-spec": cmd_validate_spec,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
