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
- Python 3.10+ (Target Python 3.12)

### Running locally
From root directory:
```bash
# Using venv python
.\venv\Scripts\python -m uvicorn backend.app.main:app --reload --port 8000
```
Or via script:
```bash
python scripts/run_backend.py
```

## Development Commands

Run tests:
```bash
.\venv\Scripts\pytest backend/tests
```

Run linting:
```bash
.\venv\Scripts\ruff check backend
.\venv\Scripts\ruff format --check backend
```

Run type checking:
```bash
.\venv\Scripts\mypy backend/app
```

## API Endpoints (Stage S2)

- `GET /health` — Service health metadata (safe information only).
- `GET /ready` — Service readiness status.
