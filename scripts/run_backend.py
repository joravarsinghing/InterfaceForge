#!/usr/bin/env python3
"""Run FastAPI backend development server."""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def get_venv_python() -> str:
    scripts_dir = REPO_ROOT / "venv" / ("Scripts" if os.name == "nt" else "bin")
    python_exe = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    if python_exe.exists():
        return str(python_exe)
    python_alt = scripts_dir / "python"
    if python_alt.exists():
        return str(python_alt)
    return sys.executable

if __name__ == "__main__":
    python_cmd = get_venv_python()

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
