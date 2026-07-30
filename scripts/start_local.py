#!/usr/bin/env python3
"""Local QA Aid: Launches backend FastAPI server and frontend Vite dev server together.

Usage (Windows PowerShell / CMD):
    python scripts/start_local.py

Press Ctrl+C to terminate both servers.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_python_exe() -> str:
    """Return the single supported Python 3.14 backend interpreter."""
    scripts_dir = REPO_ROOT / "venv314" / ("Scripts" if os.name == "nt" else "bin")
    python_exe = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    return str(python_exe)


def main():
    python_cmd = get_python_exe()
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    backend_dir = REPO_ROOT / "backend"
    frontend_dir = REPO_ROOT / "frontend"

    check = subprocess.run(
        [python_cmd, "-c", "import kcl; assert hasattr(kcl, 'execute_code_and_export')"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        detail = (check.stderr or check.stdout).strip()
        raise RuntimeError(
            f"Backend setup error: KCL runtime is unavailable in {python_cmd}. "
            f"Install zoo-kcl into this exact Python 3.14 environment. "
            f"Import check failed: {detail or 'missing execute_code_and_export'}"
        )

    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(backend_dir)
    backend_env["ENGINE_PROVIDER"] = "mock"

    print("==================================================")
    print("  InterfaceForge Local QA Development Runner")
    print("==================================================")
    print(f"Root Directory: {REPO_ROOT}")
    print(f"Python Executable: {python_cmd}")
    print("Backend Server: http://localhost:8000")
    print("Frontend App: http://localhost:5173")
    print("--------------------------------------------------")

    processes = []

    try:
        # Start Backend Server
        print("-> Starting FastAPI Backend (Uvicorn)...")
        backend_proc = subprocess.Popen(
            [
                python_cmd,
                "-m",
                "uvicorn",
                "app.main:app",
                "--reload",
                "--port",
                "8000",
                "--host",
                "127.0.0.1",
            ],
            cwd=backend_dir,
            env=backend_env,
        )
        processes.append(backend_proc)

        time.sleep(1.5)

        # Start Frontend Dev Server
        print("-> Starting Vite Frontend Dev Server...")
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
        )
        processes.append(frontend_proc)

        print("\n==================================================")
        print("  Both services are running!")
        print("  Open browser to: http://localhost:5173")
        print("  Press Ctrl+C to terminate.")
        print("==================================================\n")

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[Shutting down services...]")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        print("[Shutdown complete. Goodbye!]")
        sys.exit(0)


if __name__ == "__main__":
    main()
