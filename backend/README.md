# InterfaceForge Backend Service

FastAPI-based backend API for InterfaceForge (Zoo API Makeathon 2026).

## Overview

The backend provides the API service layer for InterfaceForge. In Stage S2, it implements the minimal architecture skeleton:
- FastAPI application entry point / factory
- Safe health (`/health`) and readiness (`/ready`) endpoints
- Standard JSON response envelopes for success and error payloads
- Request-ID tracking middleware (`X-Request-ID`)
- Environment-based configuration (`pydantic-settings`)
- Restricted CORS configuration

## Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── health.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── middleware.py
│   └── services/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_health.py
├── pyproject.toml
└── README.md
```

## Setup & Running

### Requirements
- Python 3.14.x. The supported backend runtime is the repository root `venv314` environment.

### Dependency policy
Runtime dependencies are declared in `pyproject.toml` and include FastAPI, Uvicorn, Pydantic, Pydantic Settings, WebSockets, Pillow, NumPy, OpenCV headless, and Python Multipart. The `dev` extra adds pytest, pytest-asyncio, httpx, Ruff, Mypy, msgpack, and google-genai for local verification and provider-mocked tests.

### Running locally
From root directory:
```bash
# Using the supported Python 3.14 runtime
.\venv314\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```
Or via script:
```bash
python scripts/run_backend.py
```

## Development Commands

Run tests:
```bash
.\venv314\Scripts\python.exe -m pytest backend\tests
```

Run linting:
```bash
.\venv314\Scripts\python.exe -m ruff check backend
.\venv314\Scripts\python.exe -m ruff format --check backend
```

Run type checking:
```bash
.\venv314\Scripts\python.exe -m mypy backend/app
```

## API Endpoints (Stage S2)

- `GET /health` — Service health metadata (safe information only).
- `GET /ready` — Service readiness status.
