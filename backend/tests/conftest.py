"""Pytest fixtures for backend test suite."""

import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Ensure backend directory is on sys.path for app package resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.sqlite_project_repository import SQLiteProjectRepository  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Configure isolated temporary SQLite database for tests."""
    db_file = tmp_path / "test_interfaceforge.db"
    settings.db_path = str(db_file)
    SQLiteProjectRepository(db_path=str(db_file))
    yield db_file
    if db_file.exists():
        try:
            os.remove(db_file)
        except OSError:
            pass
    default_db = Path("artifacts/interfaceforge.db")
    if default_db.exists():
        try:
            os.remove(default_db)
        except OSError:
            pass


@pytest.fixture
def client(temp_db: Path) -> Generator[TestClient, None, None]:
    """Synchronous test client fixture."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(temp_db: Path) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous test client fixture."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
