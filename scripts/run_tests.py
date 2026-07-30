#!/usr/bin/env python3
"""Run test suites for backend and frontend."""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_venv_python() -> str:
    scripts_dir = REPO_ROOT / "venv314" / ("Scripts" if os.name == "nt" else "bin")
    return str(scripts_dir / ("python.exe" if os.name == "nt" else "python"))


if __name__ == "__main__":
    python_cmd = get_venv_python()
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    print("=== 1. Running Backend Pytest Suite ===")
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(REPO_ROOT / "backend")
    pytest_res = subprocess.run(
        [python_cmd, "-m", "pytest", "tests"],
        cwd=REPO_ROOT / "backend",
        env=backend_env,
    )
    if pytest_res.returncode != 0:
        print("[FAIL] Backend tests failed.")
        sys.exit(pytest_res.returncode)

    print("\n=== 2. Running Frontend Vitest Suite ===")
    vitest_res = subprocess.run([npm_cmd, "test"], cwd=REPO_ROOT / "frontend")
    if vitest_res.returncode != 0:
        print("[FAIL] Frontend tests failed.")
        sys.exit(vitest_res.returncode)

    print("\n[OK] ALL TEST SUITES PASSED!")
    sys.exit(0)
