import os
import sys
import pty
import time
import re
import tempfile
import configparser
import pytest

SG_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts/sg.py"))


def run_with_pty(argv, timeout=2.0):
    """Executes argv with a real pseudo-terminal.
    Returns output combined (stdout + stderr + tty output)."""
    pid, fd = pty.fork()
    if pid == 0:
        try:
            import fcntl, termios
            fcntl.ioctl(0, termios.TIOCSCTTY, 1)
        except Exception:
            pass
        os.execvp(argv[0], argv)
    else:
        time.sleep(timeout)
        try:
            data = os.read(fd, 8192)
        except OSError:
            data = b""
        os.waitpid(pid, 0)
        return data.decode(errors="replace")


def create_mock_change(tmpdir, change_name="test-plan-change"):
    change_dir = os.path.join(tmpdir, ".state-guard", "changes", change_name)
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    
    config = configparser.ConfigParser()
    config.add_section("Metadata")
    config.set("Metadata", "schema_version", "2")
    config.add_section("Transaction")
    config.set("Transaction", "txn_status", "idle")
    config.set("Transaction", "txn_phase", "None")
    config.add_section("Graph")
    config.set("Graph", "lock_phase", "plan")
    config.set("Graph", "current_phase", "none")
    config.set("Graph", "completed_phases", "")
    config.set("Graph", "pending_phases", "plan, execute, verify")
    
    with open(state_path, "w", encoding="utf-8") as f:
        config.write(f)
    return state_path


def test_sg_plan_approve_and_confirm_pty(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv("SPECGUARD_GATE_DIR", str(tmpdir / ".test-gate"))
    monkeypatch.setenv("STATEGUARD_GATE_DIR", str(tmpdir / ".test-gate"))
    create_mock_change(str(tmpdir), "test-plan-change")
    
    # 1. plan-approve
    out1 = run_with_pty([sys.executable, SG_PY, "plan-approve", "--change", "test-plan-change"])
    assert "GATE PREPARADO" in out1
    match = re.search(r"C[oó]digo de confirmaci[oó]n para 'test-plan-change': ([A-F0-9]+)", out1, re.IGNORECASE)
    assert match is not None, f"Token not found in PTY output: {out1}"
    token = match.group(1)
    
    # 2. plan-confirm with WRONG token
    out2 = run_with_pty([sys.executable, SG_PY, "plan-confirm", "--change", "test-plan-change", "--token", "00000000"])
    assert "WRONG_TOKEN" in out2 or "incorrecto" in out2
    
    # 3. plan-confirm with CORRECT token
    out3 = run_with_pty([sys.executable, SG_PY, "plan-confirm", "--change", "test-plan-change", "--token", token])
    assert "Plan aprobado" in out3 or '"ok": true' in out3
    
    # 4. plan-confirm after gate consumed
    out4 = run_with_pty([sys.executable, SG_PY, "plan-confirm", "--change", "test-plan-change", "--token", token])
    assert "NO_PENDING_GATE" in out4
