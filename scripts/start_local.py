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
    """Return virtual environment python if available, else current sys.executable."""
    scripts_dir = REPO_ROOT / "venv" / ("Scripts" if os.name == "nt" else "bin")
    python_exe = scripts_dir / ("python.exe" if os.name == "nt" else "python")
    if python_exe.exists():
        return str(python_exe)
    return sys.executable


def main():
    python_cmd = get_python_exe()
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    backend_dir = REPO_ROOT / "backend"
    frontend_dir = REPO_ROOT / "frontend"

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
