#!/usr/bin/env python3
"""Run all verification checks: backend lint/type/tests, frontend lint/tsc/test/build, and repo audit."""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_venv_python() -> str:
    scripts_dir = REPO_ROOT / "venv314" / ("Scripts" if os.name == "nt" else "bin")
    return str(scripts_dir / ("python.exe" if os.name == "nt" else "python"))


def run_step(name: str, cmd: list[str], cwd: Path, env: dict = None) -> None:
    print("\n==========================================")
    print(f"Executing: {name}")
    print("==========================================")
    res = subprocess.run(cmd, cwd=cwd, env=env)
    if res.returncode != 0:
        print(f"[FAIL] FAILED step: {name}")
        sys.exit(res.returncode)
    print(f"[OK] PASSED step: {name}")


if __name__ == "__main__":
    python_cmd = get_venv_python()
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"

    backend_dir = REPO_ROOT / "backend"
    frontend_dir = REPO_ROOT / "frontend"

    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(backend_dir)

    # 1. Repository Audit
    run_step(
        "Repository Governance Audit",
        [python_cmd, "scripts/audit_repository.py"],
        REPO_ROOT,
    )

    # 2. Backend Checks
    run_step(
        "Backend Ruff Lint Check",
        [python_cmd, "-m", "ruff", "check", "app", "tests"],
        backend_dir,
    )
    run_step(
        "Backend Ruff Format Check",
        [python_cmd, "-m", "ruff", "format", "--check", "app", "tests"],
        backend_dir,
    )
    run_step(
        "Backend Mypy Type Check",
        [python_cmd, "-m", "mypy", "--explicit-package-bases", "app"],
        backend_dir,
        env=backend_env,
    )
    run_step(
        "Backend Pytest Suite",
        [python_cmd, "-m", "pytest", "tests"],
        backend_dir,
        env=backend_env,
    )

    # 3. Frontend Checks
    run_step("Frontend Vitest Suite", [npm_cmd, "test"], frontend_dir)
    run_step("Frontend ESLint Check", [npm_cmd, "run", "lint"], frontend_dir)
    run_step("Frontend TypeScript Check", [npx_cmd, "tsc", "--noEmit"], frontend_dir)
    run_step("Frontend Production Build", [npm_cmd, "run", "build"], frontend_dir)

    print("\nALL CHECKS PASSED SUCCESSFULLY!")
    sys.exit(0)
