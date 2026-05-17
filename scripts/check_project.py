"""
Lightweight project checks that do not require GPU, camera, mic, or model files.

Run:
  python scripts/check_project.py
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def check_pyproject() -> bool:
    path = ROOT / "pyproject.toml"
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"pyproject.toml: {exc}")
        return False
    ok("pyproject.toml parses")
    return True


def check_compile() -> bool:
    targets = [
        ROOT / "main.py",
        ROOT / "src",
        ROOT / "scripts",
        ROOT / "tests",
    ]
    files: list[Path] = []
    for target in targets:
        if target.is_file():
            files.append(target)
        else:
            files.extend(target.rglob("*.py"))

    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            fail(f"syntax error in {path.relative_to(ROOT)}: {exc}")
            return False

    ok("Python files parse")
    return True


def check_unittest() -> bool:
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    if proc.returncode == 0:
        ok("unit tests pass")
        return True
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    fail("unit tests failed")
    return False


def main() -> int:
    checks = [
        check_pyproject(),
        check_compile(),
        check_unittest(),
    ]
    if all(checks):
        print("\nProject check passed.")
        return 0
    print("\nProject check failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
