#!/usr/bin/env python3
"""Run React + Vite frontend development server."""

import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    print(f"Starting InterfaceForge Vite frontend using {npm_cmd}...")
    cmd = [npm_cmd, "run", "dev"]

    sys.exit(subprocess.run(cmd, cwd=REPO_ROOT / "frontend").returncode)
