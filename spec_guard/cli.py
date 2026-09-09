#!/usr/bin/env python3
"""
sg — SpecGuard CLI
==================
Wrapper de alto nivel sobre state_manager.py. JSON puro en stdout siempre.
El LLM solo puede invocar los comandos que el servidor MCP expone
como tools — plan-approve y hotfix-init NO son tools MCP, son comandos
exclusivamente humanos.

Regla de oro: cli.py no duplica lógica de negocio. Delega todo a state_manager.py.
"""
import argparse
import configparser
import hashlib
import hmac
import json
import os
import re
import secrets
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ─── Resolución del entorno ──────────────────────────────────────────────────

def _find_repo_root():
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".spec-guard").exists() or (parent / ".state-guard").exists() or (parent / ".git").exists():
            return parent
    return cwd


REPO_ROOT = _find_repo_root()
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _find_guard_dir(repo_root: Path) -> Path:
    if (repo_root / ".spec-guard").exists():
        return repo_root / ".spec-guard"
    if (repo_root / ".state-guard").exists():
        return repo_root / ".state-guard"
    return repo_root / ".spec-guard"


def _find_gate_dir() -> Path:
    env_gate = os.environ.get("SPECGUARD_GATE_DIR") or os.environ.get("STATEGUARD_GATE_DIR")
    if env_gate:
        return Path(env_gate)
    p_spec = Path.home() / ".spec-guard-gate"
    p_state = Path.home() / ".state-guard-gate"
    if p_spec.exists():
        return p_spec
    if p_state.exists():
        return p_state
    return p_spec


SG_DIR = _find_guard_dir(REPO_ROOT)
CHANGES_DIR = SG_DIR / "changes"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _call_sm(args_list, check_json=False):
    """Llama a state_manager de spec_guard y retorna (returncode, parsed_or_raw, stderr)."""
    env = dict(os.environ)
    repo_pkg_root = str(Path(__file__).parent.parent)
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{repo_pkg_root}:{existing_pp}" if existing_pp else repo_pkg_root

    cmd = [sys.executable, "-m", "spec_guard.core.state_manager"] + args_list
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0 and "No module named spec_guard" in result.stderr:
        script_path = Path(__file__).parent / "core" / "state_manager.py"
        result = subprocess.run(
            [sys.executable, str(script_path)] + args_list,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
        )

    raw = result.stdout.strip()
    err = result.stderr.strip()

    if check_json:
        try:
            return result.returncode, json.loads(raw), err
        except json.JSONDecodeError:
            return result.returncode, {"raw": raw, "stderr": err}, err
    return result.returncode, raw, err


def _emit(obj, exit_code=0):
    """Emite JSON en stdout y sale con el código dado."""
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _active_change():
    if not CHANGES_DIR.exists():
        return None
    for entry in sorted(CHANGES_DIR.iterdir()):
        if entry.is_dir() and entry.name != "archive":
            state_file = entry / "state.ini"
            if state_file.exists():
                return entry.name
    return None


# ─── Comandos sg ──────────────────────────────────────────────────────────────

def cmd_status(args):
    rc, obj, err = _call_sm(["status", "--change", args.change, "--json"],
                             check_json=True)
    _emit({"ok": rc == 0, "change": args.change, "state": obj}, rc)


def cmd_begin(args):
    rc, raw, err = _call_sm(["begin", "--change", args.change, "--phase", args.phase])
    ok = rc == 0 and "SUCCESS" in raw
    _emit({
        "ok": ok,
        "change": args.change,
        "phase": args.phase,
        "message": raw,
        "stderr": err or None,
    }, rc)


def cmd_commit(args):
    rc, raw, err = _call_sm(["commit", "--change", args.change,
                              "--next-phase", args.next_phase])
    ok = rc == 0 and "SUCCESS" in raw
    gate_mode = "chat"
    try:
        from spec_guard.core.state_manager import get_gate_mode
        gate_mode = get_gate_mode(args.change)
    except Exception:
        pass
    _emit({
        "ok": ok,
        "change": args.change,
        "next_phase": args.next_phase,
        "gate_mode": gate_mode,
        "message": raw,
        "stderr": err or None,
    }, rc)


def cmd_rollback(args):
    rc, raw, err = _call_sm(["rollback", "--change", args.change])
    ok = rc == 0 and "SUCCESS" in raw
    _emit({
        "ok": ok,
        "change": args.change,
        "message": raw,
        "stderr": err or None,
    }, rc)


def cmd_checkpoint(args):
    rc, raw, err = _call_sm(["checkpoint", "--change", args.change,
                              "--summary", args.summary])
    ok = rc == 0 and "SUCCESS" in raw
    _emit({
        "ok": ok,
        "change": args.change,
        "message": raw,
        "stderr": err or None,
    }, rc)


def cmd_check_completion(args):
    rc, obj, _ = _call_sm(["check-completion", "--change", args.change, "--json"],
                           check_json=True)
    _emit({"ok": rc == 0, "change": args.change, **obj}, rc)


def cmd_mark_task(args):
    rc, obj, _ = _call_sm(["mark-task", "--change", args.change,
                            "--task-id", args.task_id], check_json=True)
    _emit({"ok": rc == 0, **obj}, rc)


def cmd_next_task(args):
    rc, obj, _ = _call_sm(["next-task", "--change", args.change], check_json=True)
    _emit({"ok": rc == 0, **obj}, rc)


def cmd_verify_gate(args):
    rc, obj, _ = _call_sm(["verify-gate", "--change", args.change,
                            "--phase", args.phase], check_json=True)
    _emit({"ok": rc == 0, **obj}, rc)


def cmd_validate_spec(args):
    rc, obj, _ = _call_sm(["validate-spec", "--change", args.change], check_json=True)
    _emit({"ok": rc == 0, **obj}, rc)


def _search_pattern_in_tests(repo_root: Path, pattern: str) -> list[str]:
    """Busca una etiqueta de criterio (ej. CRIT-01 o CRIT_01) en directorios de test/código."""
    patterns = {pattern.lower(), pattern.lower().replace("-", "_"), pattern.lower().replace("_", "-")}
    regex_pattern = "|".join(re.escape(p) for p in patterns)

    if (repo_root / ".git").exists():
        try:
            cmd = ["git", "grep", "--untracked", "-in", "-E", regex_pattern, "--", "tests/", "test/", "spec/", "src/"]
            res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
        except Exception:
            pass

    matches = []
    for dname in ["tests", "test", "spec", "src"]:
        target_dir = repo_root / dname
        if not target_dir.exists():
            continue
        for fpath in target_dir.rglob("*"):
            if fpath.is_file() and not fpath.name.startswith("."):
                try:
                    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for idx, line in enumerate(lines, start=1):
                        line_lower = line.lower()
                        if any(p in line_lower for p in patterns):
                            rel = fpath.relative_to(repo_root)
                            matches.append(f"{rel}:{idx}:{line.strip()}")
                except Exception:
                    pass
    return matches


def cmd_verify_crit(args):
    """
    Audita deterministamente la trazabilidad 1:1 de criterios CRIT-XX en tests.
    Extrae criterios de tasks.md, design.md y objective.md, y verifica que para cada
    criterio automatizado exista una prueba en el código que contenga su identificador.
    """
    import re
    change = args.change
    guard_dir = _find_guard_dir(REPO_ROOT)
    change_dir = guard_dir / "changes" / change
    if not change_dir.exists():
        _emit({"ok": False, "change": change, "message": f"El change '{change}' no existe."}, 1)

    crit_pattern = re.compile(r'-\s*\[([ xX])\]\s*(CRIT-[0-9]+)[:\s]*(.*)')
    criteria_map = {}

    for fname in ["tasks.md", "design.md", "objective.md"]:
        fpath = change_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            for line in content.splitlines():
                m = crit_pattern.search(line)
                if m:
                    crit_id = m.group(2)
                    desc = m.group(3).strip()
                    is_manual = "(manual)" in desc.lower()
                    if crit_id not in criteria_map:
                        criteria_map[crit_id] = {
                            "id": crit_id,
                            "checked": m.group(1).lower() == "x",
                            "description": desc,
                            "type": "manual" if is_manual else "automated",
                            "source_file": fname,
                        }

    if not criteria_map:
        _emit({
            "ok": True,
            "change": change,
            "criteria": [],
            "failures": 0,
            "message": f"No se encontraron criterios CRIT-XX en las especificaciones de '{change}'."
        }, 0)

    failures = 0
    results = []

    for crit_id in sorted(criteria_map.keys()):
        item = criteria_map[crit_id]
        if item["type"] == "manual":
            item["status"] = "Pendiente de verificación humana"
            item["location"] = None
        else:
            code_matches = [
                l for l in _search_pattern_in_tests(REPO_ROOT, crit_id)
                if not any(f"changes/{change}/" in l or "SESSION.md" in l or "PLAN-" in l for _ in [0])
            ]
            if code_matches:
                first = code_matches[0]
                loc = first.split(":", 2)[:2]
                location_str = ":".join(loc)
                item["status"] = f"Localizado en {location_str}"
                item["location"] = location_str
            else:
                item["status"] = f"FALLO: No existe test asociado con la etiqueta {crit_id}"
                item["location"] = None
                failures += 1
        results.append(item)

    ok = failures == 0
    message = (
        f"Trazabilidad completa: {len(results)} criterios auditados, {failures} fallas."
        if ok else
        f"FALLÓ la verificación de trazabilidad: {failures} criterio(s) automatizados sin test demostrable."
    )
    _emit({
        "ok": ok,
        "change": change,
        "failures": failures,
        "criteria": results,
        "message": message,
    }, 0 if ok else 2)


def cmd_session_checkpoint(args):
    """
    Actualiza o genera el cursor de sesión liviano (~250 tokens) SESSION.md.
    """
    change = args.change
    guard_dir = _find_guard_dir(REPO_ROOT)
    change_dir = guard_dir / "changes" / change
    if not change_dir.exists():
        _emit({"ok": False, "change": change, "message": f"El change '{change}' no existe."}, 1)

    state_file = change_dir / "state.ini"
    phase = "execute"
    base_commit = "HEAD"
    if state_file.exists():
        cfg = configparser.ConfigParser()
        cfg.read(state_file, encoding="utf-8")
        phase = cfg.get("Graph", "lock_phase", fallback="execute")
        base_commit = cfg.get("Transaction", "base_commit", fallback="")

    if not base_commit:
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True)
            if res.returncode == 0:
                base_commit = res.stdout.strip()
        except Exception:
            base_commit = "unknown"

    diverged = False
    if base_commit and base_commit != "unknown":
        try:
            res = subprocess.run(
                ["git", "merge-base", "--is-ancestor", base_commit, "HEAD"],
                cwd=str(REPO_ROOT), capture_output=True, text=True
            )
            if res.returncode != 0:
                diverged = True
        except Exception:
            pass

    now_iso = datetime.now().isoformat()
    action = args.action or "Continuar implementación de tareas pendientes"
    completed = args.completed or "- Hito inicial registrado"
    working_state = args.working_state or "- Ejecutando fase actual"
    decisions = args.decisions or "- Ninguna pendiente"

    content = (
        f"# Session Checkpoint\n\n"
        f"- **Plan:** {change}\n"
        f"- **Phase:** {phase}\n"
        f"- **Status:** in_progress\n"
        f"- **Updated:** {now_iso}\n"
        f"- **Base commit:** {base_commit}\n\n"
        f"## Completed in this session\n"
        f"{completed}\n\n"
        f"## Current working state\n"
        f"{working_state}\n\n"
        f"## Next action\n"
        f"{action}\n\n"
        f"## Open decisions\n"
        f"{decisions}\n\n"
        f"## Verification\n"
        f"- Tests: {'pending' if not args.tests else args.tests}\n"
        f"- Divergence check: {'ALERTA: Git divergió del commit base' if diverged else 'OK (ancestro válido)'}\n"
        f"- Human review: pending\n"
    )

    session_root = REPO_ROOT / "SESSION.md"
    tmp_root = REPO_ROOT / "SESSION.md.tmp"
    session_change = change_dir / "SESSION.md"

    try:
        tmp_root.write_text(content, encoding="utf-8")
        tmp_root.replace(session_root)
        session_change.write_text(content, encoding="utf-8")
    except Exception as e:
        _emit({"ok": False, "error": str(e), "message": "No se pudo escribir SESSION.md"}, 1)

    _emit({
        "ok": True,
        "change": change,
        "phase": phase,
        "base_commit": base_commit,
        "diverged": diverged,
        "session_file": str(session_root),
        "message": "SESSION.md actualizado exitosamente.",
    })


def cmd_migrate(args):
    rc, obj, _ = _call_sm(["migrate", "--change", args.change], check_json=True)
    _emit({"ok": rc == 0, **obj}, rc)


def cmd_init(args):
    """Inicializa la estructura .spec-guard/ y los contratos AGENTS.md y CLAUDE.md."""
    target_dir = REPO_ROOT
    spec_dir = target_dir / ".spec-guard"
    (spec_dir / "changes").mkdir(parents=True, exist_ok=True)
    (spec_dir / "specs").mkdir(parents=True, exist_ok=True)

    config_file = spec_dir / "config.yaml"
    if not config_file.exists():
        config_file.write_text(
            "schema: spec-driven\n\n"
            "gate:\n"
            "  mode: chat  # 'chat' (default, cero fricción) | 'strict' (out-of-band /dev/tty)\n\n"
            "rules:\n"
            "  change_naming: kebab-case\n"
            "  execute:\n"
            "    - Seguir patrones y convenciones existentes\n"
            "  verify:\n"
            "    - Criterios CRIT-XX automatizables deben contar con tests\n",
            encoding="utf-8"
        )

    # AGENTS.md
    agents_template = TEMPLATES_DIR / "AGENTS.md.template"
    if not agents_template.exists():
        user_tpl = Path.home() / ".agents" / "skills" / "spec-guard" / "templates" / "AGENTS.md.template"
        if user_tpl.exists():
            agents_template = user_tpl

    if agents_template.exists():
        content = agents_template.read_text(encoding="utf-8")
    else:
        content = (
            "<!-- BEGIN SPECGUARD -->\n"
            "# Contributor & Executor Contract (SpecGuard SDD)\n\n"
            "## SDD Lifecycle\n"
            "Every change follows a strict phase DAG: PLAN -> EXECUTE -> VERIFY.\n"
            "<!-- END SPECGUARD -->\n"
        )

    agents_file = target_dir / "AGENTS.md"
    start_marker = "<!-- BEGIN SPECGUARD -->"
    end_marker = "<!-- END SPECGUARD -->"

    if not agents_file.exists():
        agents_file.write_text(content, encoding="utf-8")
    elif getattr(args, "force", False):
        agents_file.write_text(content, encoding="utf-8")
    else:
        existing = agents_file.read_text(encoding="utf-8")
        if start_marker in existing and end_marker in existing:
            pre = existing.split(start_marker)[0]
            post = existing.split(end_marker, 1)[1]
            new_text = pre.rstrip() + "\n\n" + content.strip() + "\n" + post.lstrip("\n")
            agents_file.write_text(new_text, encoding="utf-8")
        else:
            agents_file.write_text(existing.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")

    claude_file = target_dir / "CLAUDE.md"
    if not claude_file.exists():
        claude_file.write_text("@AGENTS.md\n", encoding="utf-8")
    elif "@AGENTS.md" not in claude_file.read_text(encoding="utf-8"):
        claude_file.write_text(claude_file.read_text(encoding="utf-8").rstrip() + "\n@AGENTS.md\n", encoding="utf-8")

    # verify-crit.sh
    scripts_dir = target_dir / "scripts"
    verify_script = scripts_dir / "verify-crit.sh"
    installed_verify = False
    source_verify = REPO_ROOT / "scripts" / "verify-crit.sh"
    if not source_verify.exists():
        source_verify = Path.home() / ".agents" / "skills" / "spec-guard" / "bin" / "verify-crit.sh"

    if source_verify.exists() and source_verify.resolve() != verify_script.resolve():
        scripts_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(str(source_verify), str(verify_script))
        os.chmod(str(verify_script), 0o755)
        installed_verify = True
    elif verify_script.exists():
        os.chmod(str(verify_script), 0o755)

    _emit({
        "ok": True,
        "repo_dir": str(target_dir),
        "spec_dir": str(spec_dir),
        "agents_md": str(agents_file),
        "claude_md": str(claude_file),
        "verify_script": str(verify_script) if (installed_verify or verify_script.exists()) else None,
        "message": "Repositorio inicializado exitosamente para SpecGuard SDD.",
    })


def cmd_init_change(args):
    change_dir = CHANGES_DIR / args.change
    state_file = change_dir / "state.ini"

    if state_file.exists():
        _emit({
            "ok": False,
            "message": f"El change '{args.change}' ya existe.",
        }, 1)

    change_dir.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        f.write(
            "[Metadata]\n"
            "last_updated = \n"
            "schema_version = 2\n\n"
            "[Transaction]\n"
            "txn_status = idle\n"
            "txn_phase = None\n"
            "txn_started_at = None\n\n"
            "[Graph]\n"
            "current_phase = none\n"
            "lock_phase = plan\n"
            "completed_phases = \n"
            "pending_phases = plan, execute, verify\n"
        )
    _emit({
        "ok": True,
        "change": args.change,
        "state_file": str(state_file),
        "message": f"Change '{args.change}' inicializado. lock_phase=plan",
    })


def cmd_list_changes(args):
    if not CHANGES_DIR.exists():
        _emit({"ok": True, "changes": []})

    changes = []
    for entry in sorted(CHANGES_DIR.iterdir()):
        if entry.is_dir() and entry.name != "archive":
            state_file = entry / "state.ini"
            if state_file.exists():
                cfg = configparser.ConfigParser()
                cfg.read(state_file, encoding="utf-8")
                changes.append({
                    "name": entry.name,
                    "lock_phase": cfg.get("Graph", "lock_phase", fallback="?"),
                    "txn_status": cfg.get("Transaction", "txn_status", fallback="?"),
                    "schema_version": cfg.get("Metadata", "schema_version", fallback="1"),
                })

    _emit({"ok": True, "changes": changes})


# ─── Agent Hooks ─────────────────────────────────────────────────────────────

def cmd_hooks_start(args):
    daemon = Path(__file__).parent / "daemon" / "hook_daemon.py"
    if not daemon.exists():
        daemon = REPO_ROOT / "scripts" / "hook_daemon.py"

    SG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = SG_DIR / "hooks.daemon.log"
    log_fh = open(log_path, "a", buffering=1)
    proc = subprocess.Popen(
        [sys.executable, str(daemon)],
        cwd=str(REPO_ROOT),
        stdout=log_fh,
        stderr=log_fh,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    (SG_DIR / "hooks.pid").write_text(str(proc.pid))
    _emit({
        "ok": True,
        "pid": proc.pid,
        "log_file": str(log_path),
        "message": "Agent Hooks daemon iniciado en background (detached). Logs en el archivo indicado.",
    })


def cmd_hooks_stop(args):
    pid_file = SG_DIR / "hooks.pid"
    if not pid_file.exists():
        _emit({"ok": False, "message": "No hay daemon corriendo (no se encontró hooks.pid)."}, 1)
        return
    pid = int(pid_file.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    if pid_file.exists():
        pid_file.unlink()
    _emit({"ok": True, "message": f"Daemon (pid {pid}) detenido."})


def cmd_hooks_status(args):
    pid_file = SG_DIR / "hooks.pid"
    if not pid_file.exists():
        _emit({"ok": True, "running": False})
        return
    pid = int(pid_file.read_text())
    try:
        os.kill(pid, 0)
        _emit({"ok": True, "running": True, "pid": pid})
    except ProcessLookupError:
        if pid_file.exists():
            pid_file.unlink()
        _emit({"ok": True, "running": False, "stale_pid_removed": True})


# ─── Instalación de git hooks ─────────────────────────────────────────────────

HOOK_TEMPLATE = """\
#!/bin/sh
# SpecGuard git hook: {hook_name}
# Instalado por: sg install-hooks

SG_BIN="$(dirname "$0")/../../scripts/sg.py"
if [ ! -f "$SG_BIN" ]; then
    SG_BIN="sg"
fi

CHANGE=$(python3 "$SG_BIN" list-changes 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
changes = data.get('changes', [])
if changes:
    print(changes[0]['name'])
" 2>/dev/null)

if [ -z "$CHANGE" ]; then
    exit 0
fi

python3 "$SG_BIN" {hook_action} --change "$CHANGE"
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "SpecGuard: hook {hook_name} falló (exit $EXIT_CODE)."
    exit $EXIT_CODE
fi
exit 0
"""


def cmd_install_hooks(args):
    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists():
        _emit({"ok": False, "message": "No se encontró .git/ en la raíz del repo."}, 1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    installed = []
    hook_defs = [("post-commit", "status")]

    for hook_name, hook_action in hook_defs:
        hook_path = hooks_dir / hook_name
        content = HOOK_TEMPLATE.format(hook_name=hook_name, hook_action=hook_action)
        if hook_path.exists() and not args.force:
            _emit({
                "ok": False,
                "message": f"El hook '{hook_name}' ya existe. Usá --force para sobreescribir.",
            }, 1)
        with open(hook_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(hook_path, 0o755)
        installed.append(str(hook_path))

    _emit({
        "ok": True,
        "installed_hooks": installed,
        "message": "Hooks instalados.",
    })


# ─── Gate de aprobación humana out-of-band (2 pasos + hardening) ───────────────

def _prepare_gate_token(change, gate_type, **extra_data):
    gate_dir = _find_gate_dir()
    gate_dir.mkdir(parents=True, exist_ok=True)
    token_file = gate_dir / f"{change}.token"

    token = secrets.token_hex(4).upper()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    try:
        with open("/dev/tty", "w", encoding="utf-8") as tty:
            tty.write(f"\n[SPECGUARD GATE] Código de confirmación para '{change}': {token}\n\n")
            tty.flush()
    except OSError:
        if token_file.exists():
            try:
                token_file.unlink()
            except Exception:
                pass
        _emit({
            "ok": False,
            "error": "NO_TTY",
            "message": "No se pudo mostrar el token: no hay terminal de control disponible. Este gate requiere ejecutarse desde una sesión con TTY real."
        }, 1)

    gate_data = {
        "token_hash": token_hash,
        "type": gate_type,
        "change": change,
        "created_at": datetime.now().isoformat(),
        "failed_attempts": 0,
        **extra_data
    }
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(gate_data, f, indent=2)

    try:
        os.chmod(token_file, 0o600)
    except Exception:
        pass

    return token_file


def _verify_and_consume_token(token_file, expected_type, received_token):
    if not token_file.exists():
        _emit({
            "ok": False,
            "error": "NO_PENDING_GATE",
            "message": f"No hay un gate pendiente de confirmación ({token_file.name} no encontrado)."
        }, 1)

    try:
        with open(token_file, "r", encoding="utf-8") as f:
            gate_data = json.load(f)
    except Exception:
        _emit({"ok": False, "error": "CORRUPT_TOKEN_FILE", "message": "El archivo de token está corrupto."}, 1)

    if gate_data.get("type") != expected_type:
        _emit({
            "ok": False,
            "error": "GATE_TYPE_MISMATCH",
            "message": f"El token es de tipo '{gate_data.get('type')}', no '{expected_type}'."
        }, 1)

    stored_hash = gate_data.get("token_hash", "")
    received_hash = hashlib.sha256(received_token.strip().upper().encode("utf-8")).hexdigest()

    if not hmac.compare_digest(stored_hash, received_hash):
        failed_attempts = gate_data.get("failed_attempts", 0) + 1
        if failed_attempts >= 3:
            try:
                token_file.unlink()
            except Exception:
                pass
            _emit({
                "ok": False,
                "error": "TOKEN_LOCKED_OUT",
                "message": "Demasiados intentos fallidos (3). El token ha sido revocado e invalidado. Generá uno nuevo."
            }, 5)

        gate_data["failed_attempts"] = failed_attempts
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(gate_data, f, indent=2)
        _emit({
            "ok": False,
            "error": "WRONG_TOKEN",
            "attempts_remaining": 3 - failed_attempts,
            "message": f"El código de confirmación es incorrecto ({failed_attempts}/3 intentos fallidos). Intenta nuevamente."
        }, 5)

    # Token verificado correctamente: consumirlo
    token_file.unlink()
    return gate_data


def cmd_plan_approve(args):
    change = args.change
    token_file = _prepare_gate_token(change, "plan")

    print("")
    print(f"  [GATE PREPARADO] Token de aprobación generado para el change '{change}'.")
    print(f"  El código de confirmación fue mostrado en tu terminal (/dev/tty).")
    print(f"  Archivo out-of-band (contiene solo el hash): {token_file}")
    print(f"  Para confirmar la aprobación, abrí una terminal separada y ejecutá:")
    print(f"    sg plan-confirm --change {change} --token <CODIGO>")
    print("")

    _emit({
        "ok": True,
        "change": change,
        "gate_prepared": True,
        "token_file": str(token_file),
        "message": f"Gate preparado en {token_file}. Ejecutá 'sg plan-confirm --change {change} --token <CODIGO>' en terminal humana para confirmar."
    })


def cmd_plan_confirm(args):
    change = args.change
    gate_dir = _find_gate_dir()
    token_file = gate_dir / f"{change}.token"

    _verify_and_consume_token(token_file, "plan", args.token)

    rc, obj, err = _call_sm(
        ["plan-approve", "--change", change, "--approved-by", "human"],
        check_json=True,
    )
    if rc == 0:
        print("")
        print(f"  Plan aprobado para '{change}'. Próximo paso:")
        print(f"    sg begin --change {change} --phase execute")
        print("")
    _emit({"ok": rc == 0, **obj}, rc)


def cmd_hotfix_init(args):
    change = args.change
    reason = args.reason

    change_dir = CHANGES_DIR / change
    if (change_dir / "state.ini").exists():
        _emit({
            "ok": False,
            "message": f"El change '{change}' ya existe.",
        }, 1)

    token_file = _prepare_gate_token(change, "hotfix", reason=reason)

    print("")
    print(f"  [HOTFIX PREPARADO] Token de bypass generado para el change '{change}'.")
    print(f"  Razón registrada: {reason}")
    print(f"  El código de confirmación fue mostrado en tu terminal (/dev/tty).")
    print(f"  Archivo out-of-band (contiene solo el hash): {token_file}")
    print(f"  Para confirmar e inicializar el hotfix, abrí una terminal separada y ejecutá:")
    print(f"    sg hotfix-confirm --change {change} --token <CODIGO>")
    print("")

    _emit({
        "ok": True,
        "change": change,
        "hotfix_prepared": True,
        "reason": reason,
        "token_file": str(token_file),
        "message": f"Hotfix preparado en {token_file}. Ejecutá 'sg hotfix-confirm --change {change} --token <CODIGO>' en terminal humana para confirmar."
    })


def cmd_hotfix_confirm(args):
    change = args.change
    gate_dir = _find_gate_dir()
    token_file = gate_dir / f"{change}.token"

    gate_data = _verify_and_consume_token(token_file, "hotfix", args.token)
    reason = gate_data.get("reason", "sin razon")

    change_dir = CHANGES_DIR / change
    state_file = change_dir / "state.ini"
    if state_file.exists():
        _emit({"ok": False, "message": f"El change '{change}' ya existe."}, 1)

    change_dir.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        f.write(
            "[Metadata]\n"
            "last_updated = \n"
            "schema_version = 2\n\n"
            "[Transaction]\n"
            "txn_status = idle\n"
            "txn_phase = None\n"
            "txn_started_at = None\n\n"
            "[Graph]\n"
            "current_phase = none\n"
            "lock_phase = plan\n"
            "completed_phases = \n"
            "pending_phases = plan, execute, verify\n"
        )

    rc, obj, _ = _call_sm(
        ["plan-approve", "--change", change,
         "--approved-by", "hotfix-init",
         "--bypass-reason", reason],
        check_json=True,
    )
    if rc != 0:
        _emit({"ok": False, "error": "PLAN_APPROVE_FAILED", **obj}, rc)

    rc2, raw2, _ = _call_sm(["begin", "--change", change, "--phase", "plan"])
    if rc2 != 0:
        _emit({"ok": False, "error": "BEGIN_FAILED", "message": raw2}, rc2)

    rc3, raw3, _ = _call_sm(["commit", "--change", change, "--next-phase", "execute"])
    if rc3 != 0:
        _emit({"ok": False, "error": "COMMIT_FAILED", "message": raw3}, rc3)

    print(f"  Hotfix '{change}' confirmado e inicializado. lock_phase=execute")
    print(f"  Próximo paso: sg begin --change {change} --phase execute")
    print()
    _emit({
        "ok": True,
        "change": change,
        "lock_phase": "execute",
        "hotfix_bypass": True,
        "bypass_reason": reason,
        "message": f"Hotfix '{change}' confirmado e inicializado con bypass registrado.",
    })


# ─── CLI entry point ──────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="sg",
        description=(
            "SpecGuard CLI -- Todos los comandos emiten JSON puro.\n"
            "Único mecanismo válido para mutar el manifiesto de estado y gobernar fases SDD."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init (repositorio)
    p = sub.add_parser("init", help="Inicializa la estructura .spec-guard/ y los contratos en el repositorio")
    p.add_argument("--force", action="store_true", help="Sobreescribe AGENTS.md en lugar de actualizar por bloques")

    # status
    p = sub.add_parser("status", help="Estado actual del change")
    p.add_argument("--change", required=True)

    # begin
    p = sub.add_parser("begin", help="Inicia una transacción para una fase")
    p.add_argument("--change", required=True)
    p.add_argument("--phase", required=True, choices=["plan", "execute", "verify", "hotfix"])

    # commit
    p = sub.add_parser("commit", help="Hace commit de la fase y avanza el DAG")
    p.add_argument("--change", required=True)
    p.add_argument("--next-phase", required=True,
                   choices=["execute", "verify"],
                   dest="next_phase")

    # rollback
    p = sub.add_parser("rollback", help="Revierte la transacción en curso")
    p.add_argument("--change", required=True)

    # checkpoint
    p = sub.add_parser("checkpoint", help="Guarda un checkpoint de sesión")
    p.add_argument("--change", required=True)
    p.add_argument("--summary", required=True)

    # check-completion
    p = sub.add_parser("check-completion", help="Conteo de tareas completadas (JSON)")
    p.add_argument("--change", required=True)

    # mark-task
    p = sub.add_parser("mark-task", help="Marca una tarea como completada por ID (JSON)")
    p.add_argument("--change", required=True)
      # validate-spec
    p = sub.add_parser("validate-spec", help="Valida la estructura de objective.md y design.md")
    p.add_argument("--change", required=True)

    # verify-crit
    p = sub.add_parser("verify-crit", help="Audita deterministamente la trazabilidad 1:1 de criterios CRIT-XX en tests")
    p.add_argument("--change", required=True)

    # session-checkpoint
    p = sub.add_parser("session-checkpoint", help="Actualiza o inicializa el cursor de sesión liviano SESSION.md")
    p.add_argument("--change", required=True)
    p.add_argument("--action", default=None, help="Próxima acción inmediata atómica")
    p.add_argument("--completed", default=None, help="Bullets de hitos completados")
    p.add_argument("--working-state", default=None, help="Estado actual de trabajo")
    p.add_argument("--decisions", default=None, help="Decisiones abiertas")
    p.add_argument("--tests", default=None, help="Estado de la suite de tests")

    # install-hooks
    p = sub.add_parser("install-hooks", help="Instala git hooks de SpecGuard")
    p.add_argument("--force", action="store_true",
                   help="Sobreescribir hooks existentes")

    # hooks-start, hooks-stop, hooks-status
    sub.add_parser("hooks-start", help="Inicia el daemon de Agent Hooks en background")
    sub.add_parser("hooks-stop", help="Detiene el daemon de Agent Hooks")
    sub.add_parser("hooks-status", help="Muestra el estado del daemon de Agent Hooks")

    # plan-approve (paso 1: prepara token out-of-band)
    p = sub.add_parser(
        "plan-approve",
        help="Gate de aprobación humana del plan (paso 1: prepara token out-of-band)"
    )
    p.add_argument("--change", required=True)

    # plan-confirm (paso 2: consume token y aprueba)
    p = sub.add_parser(
        "plan-confirm",
        help="Gate de aprobación humana del plan (paso 2: consume token y aprueba)"
    )
    p.add_argument("--change", required=True)
    p.add_argument("--token", required=True, help="Código de confirmación mostrado por plan-approve en /dev/tty")

    # hotfix-init (paso 1: prepara token out-of-band con razón)
    p = sub.add_parser(
        "hotfix-init",
        help="Inicializa un hotfix con bypass de gate (paso 1: prepara token con razón)"
    )
    p.add_argument("--change", required=True)
    p.add_argument("--reason", required=True,
                    help="Razón del bypass (ej: 'regresión crítica en prod')")

    # hotfix-confirm (paso 2: consume token e inicializa)
    p = sub.add_parser(
        "hotfix-confirm",
        help="Inicializa un hotfix con bypass de gate (paso 2: consume token e inicializa)"
    )
    p.add_argument("--change", required=True)
    p.add_argument("--token", required=True, help="Código de confirmación mostrado por hotfix-init en /dev/tty")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
        "begin": cmd_begin,
        "commit": cmd_commit,
        "rollback": cmd_rollback,
        "checkpoint": cmd_checkpoint,
        "check-completion": cmd_check_completion,
        "mark-task": cmd_mark_task,
        "next-task": cmd_next_task,
        "verify-gate": cmd_verify_gate,
        "migrate": cmd_migrate,
        "validate-spec": cmd_validate_spec,
        "verify-crit": cmd_verify_crit,
        "session-checkpoint": cmd_session_checkpoint,
        "init-change": cmd_init_change,
        "list-changes": cmd_list_changes,
        "install-hooks": cmd_install_hooks,
        "hooks-start": cmd_hooks_start,
        "hooks-stop": cmd_hooks_stop,
        "hooks-status": cmd_hooks_status,
        "plan-approve": cmd_plan_approve,
        "plan-confirm": cmd_plan_confirm,
        "hotfix-init": cmd_hotfix_init,
        "hotfix-confirm": cmd_hotfix_confirm,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
