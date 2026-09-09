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


def test_sg_hotfix_init_and_confirm_pty(monkeypatch, tmpdir):
    monkeypatch.chdir(tmpdir)
    monkeypatch.setenv("SPECGUARD_GATE_DIR", str(tmpdir / ".test-gate"))
    monkeypatch.setenv("STATEGUARD_GATE_DIR", str(tmpdir / ".test-gate"))
    change_name = "test-hotfix-change"
    reason = "Critical security patch"
    
    # 1. hotfix-init
    out1 = run_with_pty([sys.executable, SG_PY, "hotfix-init", "--change", change_name, "--reason", reason])
    assert "HOTFIX PREPARADO" in out1
    match = re.search(rf"C[oó]digo de confirmaci[oó]n para '{change_name}': ([A-F0-9]+)", out1, re.IGNORECASE)
    assert match is not None, f"Token not found in PTY output: {out1}"
    token = match.group(1)
    
    # 2. hotfix-confirm with WRONG token
    out2 = run_with_pty([sys.executable, SG_PY, "hotfix-confirm", "--change", change_name, "--token", "BADTOKEN"])
    assert "WRONG_TOKEN" in out2 or "incorrecto" in out2
    
    # 3. hotfix-confirm with CORRECT token
    out3 = run_with_pty([sys.executable, SG_PY, "hotfix-confirm", "--change", change_name, "--token", token])
    assert "inicializado" in out3 or "confirmado" in out3 or '"ok": true' in out3
    
    # Check that state.ini was created with lock_phase = execute
    state_path = os.path.join(tmpdir, ".spec-guard", "changes", change_name, "state.ini")
    if not os.path.exists(state_path):
        state_path = os.path.join(tmpdir, ".spec-guard", "changes", change_name, "state.ini")
    assert os.path.exists(state_path)
    config = configparser.ConfigParser()
    config.read(state_path)
    assert config.get("Graph", "lock_phase") == "execute"
    assert config.get("Gate", "hotfix_bypass") == "true"
    assert config.get("Gate", "hotfix_bypass_reason") == reason
