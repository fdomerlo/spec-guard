"""C0 fix-cli-parser-gaps: CLI parser completeness and base_commit recording."""
import configparser
import json
import os
import subprocess
import sys
from argparse import Namespace

import pytest

REPO_PKG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, REPO_PKG_ROOT)
sys.path.insert(0, os.path.join(REPO_PKG_ROOT, "scripts"))

import state_manager  # noqa: E402  (scripts shim -> spec_guard.core.state_manager)
from spec_guard import cli  # noqa: E402


def _subparser_choices(parser):
    for action in parser._actions:
        if action.__class__.__name__ == "_SubParsersAction":
            return set(action.choices.keys())
    return set()


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, capture_output=True, text=True, check=True,
    )


def _run_cli(cwd, *args):
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_PKG_ROOT
    res = subprocess.run(
        [sys.executable, "-m", "spec_guard.cli", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )
    return res.returncode, res.stdout, res.stderr


def test_crit_01_every_dispatch_command_has_a_parser():
    parser_cmds = _subparser_choices(cli.build_parser())
    dispatch_cmds = set(cli.DISPATCH.keys())
    missing = dispatch_cmds - parser_cmds
    orphan = parser_cmds - dispatch_cmds
    assert not missing, f"Commands dispatched without parser: {sorted(missing)}"
    assert not orphan, f"Parsers without dispatch: {sorted(orphan)}"


def test_crit_01_parser_accepts_restored_arguments():
    parser = cli.build_parser()
    args = parser.parse_args(["mark-task", "--change", "c", "--task-id", "T001"])
    assert args.task_id == "T001"
    assert parser.parse_args(["next-task", "--change", "c"]).change == "c"
    assert parser.parse_args(["verify-gate", "--change", "c", "--phase", "execute"]).phase == "execute"
    assert parser.parse_args(["migrate", "--change", "c"]).change == "c"
    assert parser.parse_args(["init-change", "--change", "c"]).change == "c"
    assert parser.parse_args(["list-changes"]).command == "list-changes"


def test_crit_01_init_change_and_next_task_end_to_end(tmpdir):
    cwd = str(tmpdir)
    rc, out, err = _run_cli(cwd, "init-change", "--change", "demo")
    assert rc == 0, err
    assert json.loads(out)["ok"] is True

    tasks = os.path.join(cwd, ".spec-guard", "changes", "demo", "tasks.md")
    with open(tasks, "w", encoding="utf-8") as f:
        f.write("- [ ] [T001] First\n- [ ] [T002] Second\n")

    rc, out, err = _run_cli(cwd, "next-task", "--change", "demo")
    assert rc == 0, err
    assert json.loads(out)["task"]["id"] == "T001"

    rc, out, err = _run_cli(cwd, "mark-task", "--change", "demo", "--task-id", "T001")
    assert rc == 0, err
    assert json.loads(out)["status"] == "SUCCESS"

    rc, out, err = _run_cli(cwd, "list-changes")
    assert rc == 0, err
    assert [c["name"] for c in json.loads(out)["changes"]] == ["demo"]


def test_crit_02_begin_records_base_commit(monkeypatch, tmpdir):
    cwd = str(tmpdir)
    _git(cwd, "init", "-q")
    _git(cwd, "commit", "-q", "--allow-empty", "-m", "init")
    head = _git(cwd, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(cwd)
    change_dir = os.path.join(cwd, ".spec-guard", "changes", "test-change")
    os.makedirs(change_dir, exist_ok=True)
    state_path = os.path.join(change_dir, "state.ini")
    with open(state_path, "w", encoding="utf-8") as f:
        f.write(
            "[Metadata]\nschema_version = 2\n\n"
            "[Transaction]\ntxn_status = idle\ntxn_phase = None\n\n"
            "[Graph]\nlock_phase = plan\ncurrent_phase = none\n"
            "completed_phases = \npending_phases = plan, execute, verify\n"
        )

    state_manager.cmd_begin(Namespace(change="test-change", phase="plan", ttl=1800))

    cfg = configparser.ConfigParser()
    cfg.read(state_path, encoding="utf-8")
    assert cfg.get("Transaction", "base_commit", fallback="") == head
