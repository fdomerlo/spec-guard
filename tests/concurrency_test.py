import json
import subprocess
import sys
import os
import time
import pty
import configparser
from concurrent.futures import ThreadPoolExecutor

CHANGE = "test-change"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["SPECGUARD_GATE_DIR"] = os.path.join(REPO_ROOT, ".test-gate")
os.environ["STATEGUARD_GATE_DIR"] = os.path.join(REPO_ROOT, ".test-gate")
SCRIPT = os.path.join(REPO_ROOT, "scripts", "state_manager.py")
SG_SCRIPT = os.path.join(REPO_ROOT, "scripts", "sg.py")
STATE_PATH = os.path.join(REPO_ROOT, f".state-guard/changes/{CHANGE}/state.ini")


import pty


def run(args):
    result = subprocess.run(
        [sys.executable, SCRIPT] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def run_with_pty(argv, timeout=2.0):
    """Ejecuta argv con una terminal de control real (pty.fork)."""
    pid, fd = pty.fork()
    if pid == 0:
        try:
            import fcntl
            import termios
            fcntl.ioctl(0, termios.TIOCSCTTY, 1)
        except Exception:
            pass
        os.execvp(argv[0], argv)
    else:
        output = b""
        start = time.time()
        while time.time() - start < timeout:
            try:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                output += chunk
            except OSError:
                break
        _, status = os.waitpid(pid, 0)
        rc = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else (status >> 8)
        return subprocess.CompletedProcess(argv, rc, stdout=output.decode(errors="replace"), stderr="")


def inject_gate_token():
    """Inyecta el token de aprobacion directamente via state_manager.py
    (sin pasar por sg.py, que tiene el challenge-response).
    En tests esto es correcto: state_manager.py es el motor ACID,
    sg.py es el guardian del canal humano."""
    run(["plan-approve", "--change", CHANGE, "--approved-by", "test-suite"])


def reset_state():
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    gate_dir = os.environ.get("SPECGUARD_GATE_DIR")
    if gate_dir and os.path.exists(gate_dir):
        import shutil
        shutil.rmtree(gate_dir, ignore_errors=True)
    with open(STATE_PATH, "w") as f:
        f.write(
            "[Metadata]\nlast_updated = 2026-07-02T10:00:00\nschema_version = 2\n\n"
            "[Transaction]\ntxn_status = idle\ntxn_phase = None\ntxn_started_at = None\n\n"
            "[Graph]\ncurrent_phase = none\nlock_phase = plan\n"
            "completed_phases = \n"
            "pending_phases = plan, execute, verify\n"
        )
    for f_name in [".lock", ".write-lock"]:
        p = os.path.join(REPO_ROOT, f".state-guard/changes/{CHANGE}/{f_name}")
        if os.path.exists(p):
            os.remove(p)


def extract_last_json(raw):
    """Extrae el ultimo JSON object del output (puede haber texto previo)."""
    idx = raw.rfind("{")
    if idx == -1:
        return None
    try:
        return json.loads(raw[idx:])
    except json.JSONDecodeError:
        return None


# ============================================================================
# TEST 1: ACID — dos BEGIN simultaneos, mismo --change
# ============================================================================
print("=" * 60)
print("TEST 1: dos BEGIN simultaneos, mismo --change")
print("=" * 60)
reset_state()
with ThreadPoolExecutor(max_workers=2) as ex:
    futures = [
        ex.submit(run, ["begin", "--change", CHANGE, "--phase", "plan"]),
        ex.submit(run, ["begin", "--change", CHANGE, "--phase", "plan"]),
    ]
    results = [f.result() for f in futures]

for i, (rc, out, err) in enumerate(results):
    print(f"  proceso {i}: rc={rc} stdout={out!r} stderr={err!r}")

successes = [r for r in results if "SUCCESS" in r[1]]
errors = [r for r in results if "ERROR" in r[1]]
print(f"  -> {len(successes)} exito(s), {len(errors)} rechazo(s)")
assert len(successes) == 1, "FALLO: deberia ganar exactamente uno de los dos BEGIN"
assert len(errors) == 1, "FALLO: el otro deberia ser rechazado con ERROR"
print("  PASS: exactamente un BEGIN gano, el otro fue rechazado correctamente.\n")


# ============================================================================
# TEST 1b: GATE — commit de plan sin gate token
# ============================================================================
print("=" * 60)
print("TEST 1b: COMMIT de plan sin gate token -> EXIT_GATE_REQUIRED (5)")
print("=" * 60)
rc_no_gate, out_no_gate, _ = run(["commit", "--change", CHANGE, "--next-phase", "execute"])
print(f"  rc={rc_no_gate} stdout={out_no_gate!r}")
assert rc_no_gate == 5, "FALLO: commit sin gate token deberia retornar exit code 5"
assert "GATE" in out_no_gate, "FALLO: el mensaje de error debe mencionar GATE"
print("  PASS: commit sin gate token fue rechazado con EXIT_GATE_REQUIRED (5).\n")


# ============================================================================
# TEST 2: ACID — COMMIT + CHECKPOINT simultaneos (gate token inyectado)
# ============================================================================
print("=" * 60)
print("TEST 2: COMMIT + CHECKPOINT simultaneos (gate token inyectado)")
print("=" * 60)
inject_gate_token()
with ThreadPoolExecutor(max_workers=2) as ex:
    futures = [
        ex.submit(run, ["commit", "--change", CHANGE, "--next-phase", "execute"]),
        ex.submit(run, ["checkpoint", "--change", CHANGE, "--summary", "checkpoint concurrente de prueba"]),
    ]
    results = [f.result() for f in futures]

for i, (rc, out, err) in enumerate(results):
    label = "commit" if i == 0 else "checkpoint"
    print(f"  {label}: rc={rc} stdout={out!r} stderr={err!r}")

config = configparser.ConfigParser()
config.read(STATE_PATH)
print("\n  Estado final del state.ini:")
for section in config.sections():
    for k, v in config.items(section):
        print(f"    [{section}] {k} = {v}")

lock_phase = config.get("Graph", "lock_phase", fallback=None)
has_summary = config.has_option("Session", "session_summary")
gate_token_cleared = not config.has_option("Gate", "plan_gate_token")
print(f"\n  lock_phase == 'execute': {lock_phase == 'execute'}")
print(f"  session_summary presente: {has_summary}")
print(f"  gate token borrado post-commit: {gate_token_cleared}")
assert lock_phase == "execute", "FALLO: el commit se perdio (lost update)"
assert has_summary, "FALLO: el checkpoint se perdio (lost update)"
assert gate_token_cleared, "FALLO: el gate token debe borrarse post-commit (no reutilizable)"
print("  PASS: ambas escrituras sobrevivieron, no hubo lost-update. Gate token borrado.\n")


# ============================================================================
# TEST 3: DAG — commit con transicion invalida
# ============================================================================
print("=" * 60)
print("TEST 3: COMMIT con transicion invalida (fuera del DAG)")
print("=" * 60)
run(["begin", "--change", CHANGE, "--phase", "execute"])
rc, out, err = run(["commit", "--change", CHANGE, "--next-phase", "plan"])
print(f"  rc={rc} stdout={out!r}")
assert "inválida" in out or "invalida" in out.lower(), "FALLO: deberia rechazar plan despues de execute"
print("  PASS: transicion fuera del DAG fue rechazada.\n")


# ============================================================================
# TEST 4: GATE OUT-OF-BAND — sg plan-approve (paso 1) + sg plan-confirm (paso 2)
# ============================================================================
print("=" * 60)
print("TEST 4: sg plan-approve + sg plan-confirm (hash verification)")
print("=" * 60)
reset_state()

# Paso 1: plan-approve (prepara token fuera del workspace, muestra en /dev/tty)
res_approve = run_with_pty(
    [sys.executable, SG_SCRIPT, "plan-approve", "--change", CHANGE],
)
print(f"  plan-approve rc={res_approve.returncode}")
assert res_approve.returncode == 0, f"FALLO: esperado exit 0, got {res_approve.returncode}: stdout={res_approve.stdout!r} stderr={res_approve.stderr!r}"

payload = extract_last_json(res_approve.stdout)
assert payload is not None, f"FALLO: no se encontro JSON en la salida: {res_approve.stdout!r}"
assert payload.get("ok") is True, f"FALLO: ok no es True: {payload}"
assert "token" not in payload and "token_hash" not in payload, f"FALLO: el payload JSON expone el token o su hash: {payload}"

token_file = payload.get("token_file")
assert token_file is not None and os.path.exists(token_file), f"FALLO: archivo token no existe: {token_file}"

# Verificar que en el archivo JSON guardado en disco NO ESTE el token crudo, solo token_hash
with open(token_file, "r", encoding="utf-8") as tf:
    saved_gate_data = json.load(tf)
assert "token" not in saved_gate_data, f"FALLO: el archivo de token almacena el token crudo: {saved_gate_data}"
assert "token_hash" in saved_gate_data, f"FALLO: el archivo no almacena token_hash: {saved_gate_data}"

# Verificar rechazo explícito en CI si se intenta plan-confirm SIN --token
res_confirm_notoken = subprocess.run(
    [sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  plan-confirm sin --token rc={res_confirm_notoken.returncode}")
assert res_confirm_notoken.returncode != 0, f"FALLO: plan-confirm sin --token deberia fallar (exit != 0), got {res_confirm_notoken.returncode}"

# Verificar rechazo con WRONG_TOKEN si se pasa un token incorrecto, y que el archivo NO se borra
res_confirm_wrong = subprocess.run(
    [sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE, "--token", "INVALID1"],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  plan-confirm con token incorrecto rc={res_confirm_wrong.returncode}")
assert res_confirm_wrong.returncode == 5, f"FALLO: esperado exit 5 para WRONG_TOKEN, got {res_confirm_wrong.returncode}"
payload_w = extract_last_json(res_confirm_wrong.stdout)
assert payload_w is not None and payload_w.get("error") == "WRONG_TOKEN", f"FALLO: error esperado WRONG_TOKEN, got {payload_w}"
assert os.path.exists(token_file), f"FALLO: el archivo token {token_file} fue borrado tras un token incorrecto"

# Para simular el paso 2 exitoso en CI de forma no interactiva (sin leer /dev/tty),
# inyectamos un token conocido en el archivo de hash para verificar la aprobación end-to-end
import hashlib
known_token = "CITEST99"
saved_gate_data["token_hash"] = hashlib.sha256(known_token.encode("utf-8")).hexdigest()
with open(token_file, "w", encoding="utf-8") as tf:
    json.dump(saved_gate_data, tf, indent=2)

res_confirm = subprocess.run(
    [sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE, "--token", known_token],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  plan-confirm con token correcto rc={res_confirm.returncode}")
assert res_confirm.returncode == 0, f"FALLO: esperado exit 0, got {res_confirm.returncode}: {res_confirm.stderr}"

payload_c = extract_last_json(res_confirm.stdout)
assert payload_c is not None and payload_c.get("ok") is True, f"FALLO: confirm no exitoso: {payload_c}"
assert not os.path.exists(token_file), f"FALLO: token_file {token_file} no fue consumido (borrado)"
print("  PASS: plan-approve y plan-confirm (hash verification) funcionaron correctamente.\n")


# ============================================================================
# TEST 5: GATE OUT-OF-BAND — sg hotfix-init (paso 1) + sg hotfix-confirm (paso 2)
# ============================================================================
print("=" * 60)
print("TEST 5: sg hotfix-init + sg hotfix-confirm (hash verification)")
print("=" * 60)
hotfix_change = "mi-hotfix"
hotfix_dir = os.path.join(REPO_ROOT, ".state-guard", "changes", hotfix_change)
import shutil
if os.path.exists(hotfix_dir):
    shutil.rmtree(hotfix_dir)

# Paso 1: hotfix-init (prepara token fuera del workspace)
res_hinit = run_with_pty(
    [sys.executable, SG_SCRIPT, "hotfix-init", "--change", hotfix_change, "--reason", "test bypass"],
)
print(f"  hotfix-init rc={res_hinit.returncode}")
assert res_hinit.returncode == 0, f"FALLO: esperado exit 0, got {res_hinit.returncode}: {res_hinit.stderr}"

payload_hi = extract_last_json(res_hinit.stdout)
assert payload_hi is not None and payload_hi.get("ok") is True, f"FALLO: hotfix-init fallo: {payload_hi}"
assert "token" not in payload_hi and "token_hash" not in payload_hi, f"FALLO: payload JSON expone token/hash: {payload_hi}"
token_file_h = payload_hi.get("token_file")
assert token_file_h is not None and os.path.exists(token_file_h), f"FALLO: archivo token no existe: {token_file_h}"

with open(token_file_h, "r", encoding="utf-8") as tf:
    saved_hf_data = json.load(tf)
assert "token" not in saved_hf_data, f"FALLO: archivo almacena token crudo: {saved_hf_data}"
assert "token_hash" in saved_hf_data, f"FALLO: archivo no almacena token_hash: {saved_hf_data}"

# Verificar rechazo si se intenta hotfix-confirm SIN --token
res_hconf_notoken = subprocess.run(
    [sys.executable, SG_SCRIPT, "hotfix-confirm", "--change", hotfix_change],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  hotfix-confirm sin --token rc={res_hconf_notoken.returncode}")
assert res_hconf_notoken.returncode != 0, f"FALLO: hotfix-confirm sin --token deberia fallar (exit != 0)"

# Verificar rechazo con WRONG_TOKEN
res_hconf_wrong = subprocess.run(
    [sys.executable, SG_SCRIPT, "hotfix-confirm", "--change", hotfix_change, "--token", "INVALID2"],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  hotfix-confirm con token incorrecto rc={res_hconf_wrong.returncode}")
assert res_hconf_wrong.returncode == 5, f"FALLO: esperado exit 5 para WRONG_TOKEN, got {res_hconf_wrong.returncode}"
assert os.path.exists(token_file_h), f"FALLO: el archivo token fue borrado tras WRONG_TOKEN en hotfix-confirm"

# Simulación en CI para verificar aprobación end-to-end
known_hf_token = "CIHF8877"
saved_hf_data["token_hash"] = hashlib.sha256(known_hf_token.encode("utf-8")).hexdigest()
with open(token_file_h, "w", encoding="utf-8") as tf:
    json.dump(saved_hf_data, tf, indent=2)

res_hconf = subprocess.run(
    [sys.executable, SG_SCRIPT, "hotfix-confirm", "--change", hotfix_change, "--token", known_hf_token],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
)
print(f"  hotfix-confirm con token correcto rc={res_hconf.returncode}")
assert res_hconf.returncode == 0, f"FALLO: esperado exit 0, got {res_hconf.returncode}: {res_hconf.stderr}"

payload_hc = extract_last_json(res_hconf.stdout)
assert payload_hc is not None and payload_hc.get("ok") is True, f"FALLO: hotfix-confirm fallo: {payload_hc}"
assert payload_hc.get("lock_phase") == "execute", f"FALLO: lock_phase no es execute: {payload_hc}"
assert not os.path.exists(token_file_h), f"FALLO: token_file {token_file_h} no fue consumido"

# ============================================================================
# TEST 6: HARDENING — Lockout tras 3 intentos fallidos de token
# ============================================================================
print("=" * 60)
print("TEST 6: Lockout de intentos en confirm (max 3 intentos)")
print("=" * 60)
reset_state()
res_l_app = run_with_pty([sys.executable, SG_SCRIPT, "plan-approve", "--change", CHANGE])
assert res_l_app.returncode == 0, f"plan-approve fallo: {res_l_app.stderr}"
p_l = extract_last_json(res_l_app.stdout)
assert p_l is not None
tf_l = p_l.get("token_file")
assert tf_l is not None and os.path.exists(tf_l)

# Intento 1 fallido
r1 = subprocess.run([sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE, "--token", "BAD1"], capture_output=True, text=True)
assert r1.returncode == 5
assert os.path.exists(tf_l)

# Intento 2 fallido
r2 = subprocess.run([sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE, "--token", "BAD2"], capture_output=True, text=True)
assert r2.returncode == 5
assert os.path.exists(tf_l)

# Intento 3 fallido -> TOKEN_LOCKED_OUT y token borrado
r3 = subprocess.run([sys.executable, SG_SCRIPT, "plan-confirm", "--change", CHANGE, "--token", "BAD3"], capture_output=True, text=True)
assert r3.returncode == 5
p3 = extract_last_json(r3.stdout)
assert p3 is not None and p3.get("error") == "TOKEN_LOCKED_OUT", f"Esperado TOKEN_LOCKED_OUT, got {p3}"
assert not os.path.exists(tf_l), f"El archivo token {tf_l} debio ser eliminado tras 3 fallos"
print("  PASS: Token revocado exitosamente tras 3 intentos fallidos.\n")


print("=" * 60)
print("TODOS LOS TESTS PASARON")
print("=" * 60)
