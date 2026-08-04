# InterfaceForge Backend Service

FastAPI backend for the implemented InterfaceForge submission workflow.

## Runtime and setup

Supported runtime: Python 3.14.x. From the repository root:

```powershell
py -3.14 -m venv venv314
.\venv314\Scripts\python.exe -m pip install --upgrade pip
.\venv314\Scripts\python.exe -m pip install -e backend[dev]
```

The backend package is under `backend/`. Run commands from the repository root with the package path configured by the launcher, or from `backend/` with the appropriate environment:

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\venv314\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The repository helper is also available:

```powershell
.\venv314\Scripts\python.exe scripts\run_backend.py
```

## Verification commands

```powershell
.\venv314\Scripts\python.exe -m pytest backend\tests
.\venv314\Scripts\python.exe -m ruff check backend
.\venv314\Scripts\python.exe -m ruff format --check backend
.\venv314\Scripts\python.exe -m mypy backend\app
```

Tests using Mock providers are offline behavior checks and do not prove live Zoo availability.

## Environment variables

Settings use Pydantic Settings and read `.env` or `backend/.env`. Exact implemented names include:

- `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `DEBUG`
- `HOST`, `PORT`, `CORS_ORIGINS`
- `DB_PATH` (default `artifacts/interfaceforge.db`)
- `ENGINE_PROVIDER` (`mock` by default), `ZOO_API_TOKEN`, `ZOO_API_BASE_URL`, `GENERATION_TIMEOUT_SECONDS`
- `ANALYSIS_PROVIDER` (`opencv` by default), `ANALYSIS_TIMEOUT_SECONDS`
- `GEMINI_API_KEY`, `GEMINI_VISION_MODEL`, `GEMINI_VISION_FALLBACK_MODEL`, `GEMINI_VISION_FALLBACK_ENABLED`, `GEMINI_MODEL`
- `OPENROUTER_API_KEY`, `OPENROUTER_API_BASE_URL`, `OPENROUTER_VISION_MODEL`, `OPENROUTER_VISION_FALLBACK_MODEL`
- `EXPORT_PROVIDER` (`mock` by default)

The frontend uses `VITE_BACKEND_URL` and never receives provider credentials. Project mode may be `mock` or `live`; live project creation/update requires a configured backend Zoo token. Agent provider selection is separate: Zoo is the default live path and Mock must be explicitly requested for tests/development.

## Persistence and artifacts

`SQLiteProjectRepository` stores canonical project JSON, workflow state, schema/model revision pointers, and last-known-good lineage in SQLite. The default database is under `artifacts/`. Uploads, cleaned images, analysis images, SVG traces, KCL, previews, and STL/KCL exports are runtime artifacts under the artifact root and must remain ignored by source control. Render's local filesystem may be ephemeral; durable production artifact storage is not claimed by this submission.

## Deployment

- Frontend: Cloudflare Pages.
- Backend: Render running the FastAPI application.
- Frontend/backend connection: `VITE_BACKEND_URL`.
- Configure `CORS_ORIGINS` to include the deployed frontend origin.
- Set `ZOO_API_TOKEN` only in the Render/backend environment for live Zoo Engine/Agent/export calls.
- Do not put Zoo, Gemini, or OpenRouter keys in frontend variables or committed files.

## Active scope

Two approved profiles use two-point calibration with one known real-world distance each. Active profiles are circle, rectangle, rounded rectangle, and approved `traced_closed`; active connections are coaxial and parallel X/Y offset. The authoritative LoftPlan drives KCL 2.0, preview, and final geometry. Active exports are STL and KCL. Angle-based connections, internal cavities, STEP, and certified manufacturing readiness are not submission capabilities.
