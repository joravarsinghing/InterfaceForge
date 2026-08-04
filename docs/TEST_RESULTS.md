# InterfaceForge Test Results

**Status:** PROVISIONAL - current working-tree evidence; not a clean final-commit report.
**Date:** 2026-08-04
**Commit:** Working tree; no commit created by this task.

## Commands executed

```powershell
.\venv314\Scripts\python.exe -m pytest backend/tests/test_connection_validation.py backend/tests/test_kcl_compiler.py backend/tests/test_agent_bounded_revisions.py backend/tests/test_profile_extensions.py -q
```

Result: **29 passed, 0 failed, 1 warning** in 9.02 seconds. Warning: Starlette/httpx deprecation warning from the installed test environment.

```powershell
git diff --check
```

Result: PASS, with normal LF/CRLF conversion warnings.

## Evidence classification

- **Offline PASS:** connection validation, KCL compiler, bounded Agent revisions, and profile extensions.
- **Not run in this update:** full backend suite, full frontend suite/build, deployment smoke checks, and fresh live-provider matrix.
- **Prior evidence:** KCL 2.0 compilation and STL export were previously verified; treat these as prior project evidence, not fresh live evidence from this update.
- **Live Agent:** a prior credentialed integration flow succeeded. During the focused 2026-08-04 adversarial audit, 17 of 18 Agent calls timed out or closed.
- **Live Engine:** the direct 2026-08-04 audit timed out before a fresh STL conversion result.
- **Not proven:** current live Engine loft/subtraction matrix, fresh deterministic STL conversion, live timeout semantics, and broad live Agent reliability.

## Scope exclusions

No active test claim is made for STEP export, angle-based generation, internal cavities, or certified manufacturing readiness. Offline tests are not live Zoo proof. No confirmed Zoo bug was established.

## Required before final submission

Run the full backend/frontend suites and build in the intended environment, perform deployment smoke checks, and update this document with the exact command, commit, environment, and totals. Do not reuse historical totals without rerunning them.
