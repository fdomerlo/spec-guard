"""C1 CRIT-16 / CRIT-17: verify-crit over RF criteria, rf-status and mark-rf."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from root_fixtures import run_cli, write_root_project  # noqa: E402
from spec_guard.core import root_docs  # noqa: E402


def _write_tests(project, body):
    tests_dir = Path(project) / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_feature.py").write_text(body, encoding="utf-8")


def test_crit_16_crit_matches_respects_boundaries():
    m = root_docs.crit_matches
    assert m("CRIT-01", "def test_crit_01_autenticacion(): pass")
    assert m("CRIT-01", "def test_CRIT_01_x(): pass")
    assert m("CRIT-101-1", "test('CRIT-101-1: valida')")
    assert m("CRIT-101-1", "def test_crit_101_1_valida(): pass")
    assert not m("CRIT-1", "def test_crit_10_algo(): pass")
    assert not m("CRIT-101-1", "def test_crit_101_10_algo(): pass")
    assert not m("CRIT-101", "def test_crit_101_1_algo(): pass")
    assert not m("CRIT-01", "def test_xcrit_01(): pass")


def test_crit_16_verify_crit_includes_scoped_rf_criteria(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, rf_ids="RF-101")
    _write_tests(project, "def test_crit_101_1_valida_htmx(): pass\n")
    rc, out = run_cli(project, "verify-crit", "--change", "demo")
    assert rc == 0, out
    by_id = {c["id"]: c for c in out["criteria"]}
    assert set(by_id) == {"CRIT-101-1", "CRIT-101-2"}
    assert by_id["CRIT-101-1"]["source_file"] == "requirements.md"
    assert by_id["CRIT-101-2"]["type"] == "manual"


def test_crit_16_verify_crit_rejects_prefix_false_positive(tmpdir):
    project = Path(str(tmpdir))
    change_dir = project / ".spec-guard" / "changes" / "legacy"
    change_dir.mkdir(parents=True)
    (change_dir / "tasks.md").write_text("- [ ] CRIT-1: Algo\n", encoding="utf-8")
    _write_tests(project, "def test_crit_10_otra_cosa(): pass\n")
    rc, out = run_cli(project, "verify-crit", "--change", "legacy")
    assert rc == 2
    assert out["failures"] == 1


def test_crit_17_rf_status_reports_totals(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, rf_ids="RF-101")
    rc, out = run_cli(project, "rf-status", "--change", "demo")
    assert rc == 0, out
    assert out["totals"] == {"total": 2, "done": 1, "pending": 1}
    assert out["pending_ids"] == ["RF-101"]
    assert out["scope"] == ["RF-101"]
    assert [r["id"] for r in out["in_scope"]] == ["RF-101"]


def test_crit_17_mark_rf_rejects_wrong_phase(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, lock_phase="execute")
    _write_tests(project, "def test_crit_101_1_ok(): pass\n")
    rc, out = run_cli(project, "mark-rf", "--change", "demo", "--rf", "RF-101")
    assert rc == 3
    assert out["ok"] is False


def test_crit_17_mark_rf_rejects_out_of_scope(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, lock_phase="verify", rf_ids="RF-101")
    rc, out = run_cli(project, "mark-rf", "--change", "demo", "--rf", "RF-102")
    assert rc == 4
    assert out["ok"] is False


def test_crit_17_mark_rf_rejects_when_crit_uncovered(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, lock_phase="verify")
    rc, out = run_cli(project, "mark-rf", "--change", "demo", "--rf", "RF-101")
    assert rc == 2
    assert "[ ] RF-101" in (project / "requirements.md").read_text(encoding="utf-8")


def test_crit_17_mark_rf_success_and_idempotent(tmpdir):
    project = Path(str(tmpdir))
    write_root_project(project, lock_phase="verify")
    _write_tests(project, "def test_crit_101_1_ok(): pass\n")
    rc, out = run_cli(project, "mark-rf", "--change", "demo", "--rf", "RF-101")
    assert rc == 0, out
    assert out["status"] == "SUCCESS"
    rf = [r for r in root_docs.parse_rfs((project / "requirements.md").read_text(encoding="utf-8"))
          if r["id"] == "RF-101"][0]
    assert rf["checked"] is True
    assert all(c["checked"] for c in rf["criteria"])

    rc, out = run_cli(project, "mark-rf", "--change", "demo", "--rf", "RF-101")
    assert rc == 0
    assert out["status"] == "ALREADY_DONE"
