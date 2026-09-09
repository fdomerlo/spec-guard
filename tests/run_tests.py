#!/usr/bin/env python3
"""
Test runner para SpecGuard.
Ejecuta con pytest si está disponible, o ejecuta las suites de tests unitarios
con un arnés ligero si pytest no está instalado en el entorno.
"""
import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

# Si pytest existe, ejecutarlo directamente
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


def _create_mini_pytest():
    import types

    class RaisesContext:
        def __init__(self, expected_exc):
            self.expected_exc = expected_exc
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.expected_exc} but no exception was raised.")
            if issubclass(exc_type, self.expected_exc):
                self.value = exc_val
                return True
            return False

    class MonkeyPatch:
        def __init__(self):
            self._orig_cwd = os.getcwd()
            self._actions = []

        def chdir(self, path):
            os.chdir(path)

        def setattr(self, target, name, value):
            orig = getattr(target, name)
            self._actions.append((setattr, (target, name, orig)))
            setattr(target, name, value)

        def setenv(self, name, value):
            orig = os.environ.get(name)
            self._actions.append((self._restore_env, (name, orig)))
            os.environ[name] = str(value)

        def _restore_env(self, name, orig):
            if orig is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = orig

        def undo(self):
            os.chdir(self._orig_cwd)
            for fn, args in reversed(self._actions):
                fn(*args)

    class CapSys:
        def __init__(self):
            import io
            self._old_stdout = sys.stdout
            self._old_stderr = sys.stderr
            self._out = io.StringIO()
            self._err = io.StringIO()
            sys.stdout = self._out
            sys.stderr = self._err

        def readouterr(self):
            val_out = self._out.getvalue()
            val_err = self._err.getvalue()
            return types.SimpleNamespace(out=val_out, err=val_err)

        def close(self):
            sys.stdout = self._old_stdout
            sys.stderr = self._old_stderr

    def _fail(msg=""):
        raise AssertionError(msg)

    mod = types.ModuleType("pytest")
    mod.raises = RaisesContext
    mod.MonkeyPatch = MonkeyPatch
    mod.fail = _fail
    return mod, MonkeyPatch, CapSys


def run_unit_tests():
    if HAS_PYTEST:
        import pytest
        return pytest.main([str(REPO_ROOT / "tests" / "unit"), "-q"])

    # Fallback runner
    print("→ pytest no detectado en el entorno; ejecutando tests unitarios con arnés autónomo...")
    mini_pytest, MonkeyPatchCls, CapSysCls = _create_mini_pytest()
    sys.modules["pytest"] = mini_pytest

    unit_dir = REPO_ROOT / "tests" / "unit"
    test_files = sorted(unit_dir.glob("test_*.py"))

    passed = 0
    failed = 0
    errors = []

    for test_file in test_files:
        module_name = f"tests.unit.{test_file.stem}"
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, test_file)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
        except Exception as e:
            # Si requiere dependencias opcionales como watchdog o fastmcp que no están instaladas
            if "watchdog" in str(e) or "mcp" in str(e):
                print(f"  [SKIP] {test_file.name}: falta dependencia opcional ({e})")
                continue
            errors.append((test_file.name, str(e)))
            print(f"  [ERROR] {test_file.name}: {e}")
            continue

        test_funcs = [
            (name, fn) for name, fn in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]

        for name, fn in test_funcs:
            sig = inspect.signature(fn)
            params = sig.parameters

            mp = MonkeyPatchCls()
            tmp_d = tempfile.mkdtemp(prefix="sg_test_")
            kwargs = {}

            if "monkeypatch" in params:
                kwargs["monkeypatch"] = mp
            if "tmpdir" in params:
                kwargs["tmpdir"] = Path(tmp_d)
            cs = None
            if "capsys" in params:
                cs = CapSysCls()
                kwargs["capsys"] = cs

            try:
                fn(**kwargs)
                passed += 1
                sys.stdout.write(".")
                sys.stdout.flush()
            except SystemExit as se:
                if se.code == 0 or se.code is None:
                    passed += 1
                    sys.stdout.write(".")
                    sys.stdout.flush()
                else:
                    failed += 1
                    errors.append((f"{test_file.name}::{name}", f"Unexpected SystemExit({se.code})"))
                    sys.stdout.write("F")
                    sys.stdout.flush()
            except Exception as ex:
                import traceback
                failed += 1
                tb = traceback.format_exc().splitlines()[-2:]
                errors.append((f"{test_file.name}::{name}", " -> ".join(tb)))
                sys.stdout.write("F")
                sys.stdout.flush()
            finally:
                if cs is not None:
                    cs.close()
                mp.undo()
                shutil.rmtree(tmp_d, ignore_errors=True)

    print(f"\n\nResultados: {passed} PASSED, {failed} FAILED")
    if errors:
        print("\nDetalle de fallos:")
        for target, err in errors:
            print(f"  - {target}: {err}")
        return 1
    return 0


def main():
    print("============================================================")
    print("SpecGuard Test Suite")
    print("============================================================")
    
    # 1. Tests de Concurrencia y Hardening
    print("\n--- Ejecutando tests de concurrencia y gates ---")
    import subprocess
    r_conc = subprocess.run([sys.executable, str(REPO_ROOT / "tests" / "concurrency_test.py")])
    if r_conc.returncode != 0:
        print(f"FALLO en concurrency_test.py (exit {r_conc.returncode})")
        sys.exit(r_conc.returncode)

    # 2. Tests Unitarios
    print("\n--- Ejecutando tests unitarios ---")
    rc_unit = run_unit_tests()
    if rc_unit != 0:
        sys.exit(rc_unit)

    print("\n✓ Todas las suites de pruebas completadas con éxito.")


if __name__ == "__main__":
    main()
