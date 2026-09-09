"""
locking.py — Control de concurrencia y exclusión mutua POSIX para SpecGuard.
"""
import os
import time
from datetime import datetime

__all__ = [
    "try_acquire_lockfile",
    "release_lockfile",
    "_is_write_lock_stale",
    "is_stale",
    "check_lock_status",
    "with_write_lock",
    "WRITE_LOCK_MAX_AGE",
]

WRITE_LOCK_MAX_AGE = 30  # seconds before a write lock is considered stale


def try_acquire_lockfile(lock_path: str) -> bool:
    """Atomic OS-level test-and-set. Returns True if acquired."""
    d = os.path.dirname(lock_path)
    if d:
        os.makedirs(d, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lockfile(lock_path: str) -> None:
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
        except OSError:
            pass


def _is_write_lock_stale(lock_path: str, max_age_seconds: float = WRITE_LOCK_MAX_AGE) -> bool:
    """Detecta si un .write-lock es huérfano (proceso muerto o demasiado viejo).

    Returns:
        True si el lock es stale y puede ser removido de forma segura.
    """
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) >= 1:
            pid = int(lines[0].strip())
            try:
                os.kill(pid, 0)
            except OSError:
                return True  # proceso muerto, lock huérfano
        if len(lines) >= 2:
            created = float(lines[1].strip())
            if time.time() - created > max_age_seconds:
                return True  # demasiado viejo
    except (ValueError, OSError):
        return True  # no se puede leer, asumir stale
    return False


def is_stale(started_at_iso: str, ttl_seconds: int) -> bool:
    if not started_at_iso or started_at_iso == "None":
        return False
    elapsed = (datetime.now() - datetime.fromisoformat(started_at_iso)).total_seconds()
    return elapsed > ttl_seconds


def check_lock_status(lock_path: str, started_at_iso: str, ttl_seconds: int) -> str:
    """FREE | ACTIVE | STALE"""
    if not os.path.exists(lock_path):
        return "FREE"
    if is_stale(started_at_iso, ttl_seconds):
        return "STALE"
    return "ACTIVE"


def with_write_lock(write_lock_path: str, fn, retries: int = 40, delay: float = 0.05):
    """Serializa cualquier escritura a state.ini (mutex de archivo, vida corta).
    Distinto del lock de negocio (.lock de fase): este protege contra
    lost-update por read-modify-write concurrente, sin importar qué campo
    lógico se está tocando."""
    for _ in range(retries):
        if try_acquire_lockfile(write_lock_path):
            try:
                return fn()
            finally:
                release_lockfile(write_lock_path)
        if _is_write_lock_stale(write_lock_path):
            try:
                os.remove(write_lock_path)
                continue
            except FileNotFoundError:
                pass
        time.sleep(delay)
    raise RuntimeError(
        "No se pudo adquirir el write-lock de state.ini tras reintentos."
    )
