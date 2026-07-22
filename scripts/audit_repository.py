#!/usr/bin/env python3
"""
Repository Audit Script for InterfaceForge
Checks required files, directory structure, documentation placeholders, governance documents,
and security rules (no committed secrets, no generated artifacts).

Uses standard library only.
Returns exit code 0 on success, non-zero on failure.
"""

import sys
import os
import subprocess
from pathlib import Path

REQUIRED_ROOT_FILES = [
    "README.md",
    "LICENSE",
    "AGENTS.md",
    ".gitignore",
    ".gitattributes",
    "InterfaceForge_PRD_v0.1.md",
    "technical_design.md",
    "user_flow.md",
    "ascii_wireframes.md",
]

REQUIRED_DIRECTORIES = [
    "frontend",
    "backend",
    "tests",
    "scripts",
    "samples",
    "artifacts",
    "production_docs",
    "docs",
]

REQUIRED_DOC_PLACEHOLDERS = [
    "docs/ARCHITECTURE.md",
    "docs/API_USAGE.md",
    "docs/DESIGN_SCHEMA.md",
    "docs/GEOMETRY_RULES.md",
    "docs/TEST_PLAN.md",
    "docs/TEST_RESULTS.md",
    "docs/ZOO_API_NOTES.md",
    "docs/BUGS_AND_LIMITATIONS.md",
    "docs/DESIGN_DECISIONS.md",
    "docs/DEMO_SCRIPT.md",
    "docs/SUBMISSION_CHECKLIST.md",
]

FORBIDDEN_PATTERNS = [
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "service_account.json",
]


def audit_repository(repo_root: Path) -> int:
    failures = []
    warnings = []

    print("=== InterfaceForge Repository Audit ===")
    print(f"Repository Root: {repo_root.resolve()}\n")

    # 1. Check Root Files
    print("[Check 1/7] Checking required root files...")
    for filename in REQUIRED_ROOT_FILES:
        filepath = repo_root / filename
        if not filepath.is_file():
            failures.append(f"Missing required root file: {filename}")
        else:
            print(f"  [OK] {filename}")

    # 2. Check Directories
    print("\n[Check 2/7] Checking required directories...")
    for dirname in REQUIRED_DIRECTORIES:
        dirpath = repo_root / dirname
        if not dirpath.is_dir():
            failures.append(f"Missing required directory: {dirname}")
        else:
            print(f"  [OK] {dirname}/")

    # 3. Check Documentation Placeholders
    print("\n[Check 3/7] Checking documentation placeholders...")
    for docname in REQUIRED_DOC_PLACEHOLDERS:
        docpath = repo_root / docname
        if not docpath.is_file():
            failures.append(f"Missing documentation placeholder: {docname}")
        else:
            print(f"  [OK] {docname}")

    # 4. Check MIT License
    print("\n[Check 4/7] Checking MIT license presence...")
    license_path = repo_root / "LICENSE"
    if license_path.is_file():
        content = license_path.read_text(encoding="utf-8", errors="ignore")
        if "MIT License" in content:
            print("  [OK] MIT License text verified.")
        else:
            warnings.append("LICENSE file exists but does not explicitly mention 'MIT License'.")
    else:
        failures.append("LICENSE file missing.")

    # 5. Check for Forbidden Secret Files
    print("\n[Check 5/7] Checking for forbidden secret-like files...")
    for pattern in FORBIDDEN_PATTERNS:
        found_files = list(repo_root.rglob(pattern))
        for f in found_files:
            # exclude .env.example
            if f.name == ".env.example":
                continue
            failures.append(f"Forbidden secret file present: {f.relative_to(repo_root)}")
    if not any("Forbidden secret file" in f for f in failures):
        print("  [OK] No forbidden secret files found.")

    # 6. Check Git Tracked Files (No .env tracked)
    print("\n[Check 6/7] Checking git tracked files for untracked secrets...")
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        tracked_files = res.stdout.splitlines()
        for tf in tracked_files:
            if tf == ".env" or tf.startswith(".env.") and not tf.endswith(".example"):
                failures.append(f"Tracked environment secret file in git: {tf}")
            if tf.endswith(".pem") or tf.endswith(".key") or tf.endswith(".secret"):
                failures.append(f"Tracked key/secret file in git: {tf}")
        print("  [OK] Git tracked files check complete.")
    except Exception as e:
        warnings.append(f"Could not run `git ls-files`: {e}")

    # 7. Check Artifact Directory Contents
    print("\n[Check 7/7] Checking artifacts directory for forbidden committed output...")
    artifacts_dir = repo_root / "artifacts"
    if artifacts_dir.is_dir():
        artifact_files = [
            f for f in artifacts_dir.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        ]
        if artifact_files:
            for af in artifact_files:
                failures.append(f"Forbidden committed file in artifacts/: {af.name}")
        else:
            print("  [OK] artifacts/ directory contains no committed generated files.")

    # Summary Output
    print("\n=== Audit Summary ===")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - WARNING: {w}")

    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  - FAIL: {f}")
        print("\nAudit status: FAILED")
        return 1

    print("Audit status: PASSED (All checks successful)")
    return 0


if __name__ == "__main__":
    repo_root_dir = Path(__file__).resolve().parent.parent
    sys.exit(audit_repository(repo_root_dir))
