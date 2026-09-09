#!/usr/bin/env python3
"""Agent Hooks daemon — observa el filesystem y dispara acciones declaradas
en .spec-guard/hooks.yaml (o .state-guard/hooks.yaml).
Solo ejecuta acciones de categoría "derivada" — nunca toca objective.md/design.md
ni el gate humano."""
import json
import subprocess
import sys
import time
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    import yaml
    HAS_HOOK_DEPS = True
except ImportError:
    HAS_HOOK_DEPS = False
    Observer = object
    FileSystemEventHandler = object
    yaml = None

__all__ = [
    "main",
    "HookHandler",
    "REPO_ROOT",
    "GUARD_DIR",
    "RULES_FILE",
    "LOG_FILE",
    "EXCLUDED_PREFIXES",
    "FORBIDDEN_PATTERNS",
    "HAS_HOOK_DEPS",
    "get_repo_root",
    "get_rules_file",
    "get_log_file",
    "_find_repo_root",
    "_find_guard_dir",
    "_log",
    "_load_rules",
]


def _find_repo_root():
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".spec-guard").exists() or (parent / ".state-guard").exists() or (parent / ".git").exists():
            return parent
    return cwd


REPO_ROOT = _find_repo_root()


def _find_guard_dir(repo_root: Path) -> Path:
    if (repo_root / ".spec-guard").exists():
        return repo_root / ".spec-guard"
    if (repo_root / ".state-guard").exists():
        return repo_root / ".state-guard"
    return repo_root / ".spec-guard"


GUARD_DIR = _find_guard_dir(REPO_ROOT)
RULES_FILE = GUARD_DIR / "hooks.yaml"
LOG_FILE = GUARD_DIR / "hooks.log.jsonl"
EXCLUDED_PREFIXES = (".spec-guard/", ".state-guard/", ".git/")  # nunca reaccionar a sus propios efectos
FORBIDDEN_PATTERNS = ("objective.md", "design.md")  # nunca disparar sobre estos, bajo ninguna circunstancia


def get_repo_root():
    shim = sys.modules.get("hook_daemon")
    if shim and hasattr(shim, "REPO_ROOT"):
        return Path(getattr(shim, "REPO_ROOT"))
    this_mod = sys.modules.get("spec_guard.daemon.hook_daemon")
    if this_mod and hasattr(this_mod, "REPO_ROOT"):
        return Path(getattr(this_mod, "REPO_ROOT"))
    return REPO_ROOT


def get_rules_file():
    shim = sys.modules.get("hook_daemon")
    if shim and hasattr(shim, "RULES_FILE"):
        return Path(getattr(shim, "RULES_FILE"))
    this_mod = sys.modules.get("spec_guard.daemon.hook_daemon")
    if this_mod and hasattr(this_mod, "RULES_FILE"):
        return Path(getattr(this_mod, "RULES_FILE"))
    return RULES_FILE


def get_log_file():
    shim = sys.modules.get("hook_daemon")
    if shim and hasattr(shim, "LOG_FILE"):
        return Path(getattr(shim, "LOG_FILE"))
    this_mod = sys.modules.get("spec_guard.daemon.hook_daemon")
    if this_mod and hasattr(this_mod, "LOG_FILE"):
        return Path(getattr(this_mod, "LOG_FILE"))
    return LOG_FILE


def _log(entry: dict):
    entry["ts"] = time.time()
    log_path = get_log_file()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_rules():
    target_rules = get_rules_file()
    if not target_rules.exists():
        alt = get_repo_root() / (".state-guard" if ".spec-guard" in str(GUARD_DIR) else ".spec-guard") / "hooks.yaml"
        if alt.exists():
            target_rules = alt

    if not target_rules.exists():
        return []
    if yaml is None:
        return []
    try:
        with open(target_rules, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("hooks", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"Advertencia: {target_rules} malformado ({e}). Ignorando reglas.", file=sys.stderr)
        return []


class HookHandler(FileSystemEventHandler):
    def __init__(self, rules):
        self.rules = rules
        self._debounce = {}  # path -> last_trigger_ts

    def _should_skip(self, path: str) -> bool:
        repo_root = get_repo_root()
        try:
            rel = str(Path(path).relative_to(repo_root))
        except ValueError:
            return True
        if any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
            return True
        if any(f in rel for f in FORBIDDEN_PATTERNS):
            return True
        now = time.time()
        last = self._debounce.get(rel, 0)
        if now - last < 2.0:  # debounce de 2s por archivo
            return True
        self._debounce[rel] = now
        return False

    def on_modified(self, event):
        if event.is_directory or self._should_skip(event.src_path):
            return
        repo_root = get_repo_root()
        try:
            rel = str(Path(event.src_path).relative_to(repo_root))
        except ValueError:
            return
        for rule in self.rules:
            if Path(rel).match(rule["pattern"]) and "on_save" in rule.get("events", []):
                self._fire(rule, rel)

    def _fire(self, rule, path):
        prompt = rule["prompt"].format(path=path)
        _log({"rule": rule["name"], "path": path, "status": "triggered"})
        repo_root = get_repo_root()
        try:
            result = subprocess.run(
                rule["agent_command"] + [prompt],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=rule.get("timeout", 120),
            )
            _log({"rule": rule["name"], "path": path, "status": "done",
                  "returncode": result.returncode})
        except Exception as e:
            _log({"rule": rule["name"], "path": path, "status": "error", "error": str(e)})


def main():
    if not HAS_HOOK_DEPS:
        print("Error: falta dependencia opcional para Agent Hooks. Instalá con: pip install -e '.[hooks]'", file=sys.stderr)
        sys.exit(1)
    rules = _load_rules()
    if not rules:
        print(f"No hay reglas en {RULES_FILE}. Nada que observar.")
        return
    observer = Observer()
    observer.schedule(HookHandler(rules), str(REPO_ROOT), recursive=True)
    observer.start()
    print(f"Agent Hooks daemon activo. {len(rules)} reglas cargadas. Log: {LOG_FILE}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
