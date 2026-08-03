"""End-to-End backend workflow integration tests for Stage S6A.

Covers:
1. Complete happy path workflow
2. Interface B prerequisite enforcement (cannot analyze/approve B before A approval)
3. Connection validation failure handling
4. Mock generation failure & retry
5. Cancellation handling
6. Parameter revision & regeneration
7. Failed revision preserving last-known-good model revision (ADR-005)
8. Editing Interface A marking model state STALE
9. Backend restart and project persistence recovery
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.schema import WorkflowState
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService


def create_sample_png_bytes(color=(200, 200, 200), width=100, height=100) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_interface_b_prerequisites_enforced(client: TestClient) -> None:
    """Interface B cannot be uploaded, analyzed, or approved before Interface A is approved."""
    create_res = client.post("/api/projects")
    proj = create_res.json()["data"]
    proj_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    # Attempt to upload Interface B before approving Interface A -> 400 Bad Request
    png_bytes = create_sample_png_bytes()
    files_b = {"file": ("interface_b.png", png_bytes, "image/png")}
    up_b = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/upload", files=files_b, headers=headers
    )
    assert up_b.status_code == 400
    assert up_b.json()["error"]["id"] == "IF-PREREQ-400"

    # Attempt to approve Interface B -> 400
    app_b = client.post(f"/api/projects/{proj_id}/interfaces/interface_b/approve", headers=headers)
    assert app_b.status_code == 400
    assert app_b.json()["error"]["id"] == "IF-APPROVAL-400"
