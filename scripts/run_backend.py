#!/usr/bin/env python3
"""Run FastAPI backend development server."""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_backend_python() -> Path:
    """Return the single supported Python 3.14 backend interpreter."""
    scripts_dir = REPO_ROOT / "venv314" / ("Scripts" if os.name == "nt" else "bin")
    return scripts_dir / ("python.exe" if os.name == "nt" else "python")


def validate_kcl_runtime(python_exe: Path) -> None:
    """Fail before Uvicorn starts if the selected runtime cannot execute KCL."""
    if not python_exe.exists():
        raise RuntimeError(
            f"Backend setup error: required Python 3.14 interpreter was not found at "
            f"{python_exe}. Create venv314 and install backend dependencies including zoo-kcl."
        )

    check = subprocess.run(
        [str(python_exe), "-c", "import kcl; assert hasattr(kcl, 'execute_code_and_export')"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        detail = (check.stderr or check.stdout).strip()
        raise RuntimeError(
            f"Backend setup error: KCL runtime is unavailable in {python_exe}. "
            f"Install zoo-kcl into this exact Python 3.14 environment. "
            f"Import check failed: {detail or 'missing execute_code_and_export'}"
        )


if __name__ == "__main__":
    python_exe = get_backend_python()
    try:
        validate_kcl_runtime(python_exe)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    python_cmd = str(python_exe)

    print(f"Starting InterfaceForge FastAPI backend using {python_cmd}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "backend")

    cmd = [
        python_cmd,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]

    sys.exit(subprocess.run(cmd, cwd=REPO_ROOT / "backend", env=env).returncode)
