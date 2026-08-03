"""Unit and Contract Tests for File Format API Export Suite per S8."""

import pytest
from httpx import AsyncClient

from app.services.export_provider import (
    redact_secrets,
    validate_step_signature,
    validate_stl_signature,
)
from app.services.project_service import ProjectService


@pytest.fixture
def service(temp_db):
    """ProjectService fixture with isolated DB."""
    return ProjectService()


async def _create_project_with_current_model(async_client: AsyncClient, token_header: bool = True):
    """Helper to set up a project in model_current state ready for export."""
    # 1. Create project
    res = await async_client.post("/api/projects")
    data = res.json()["data"]
    project_id = data["project_id"]
    token = data["project_token"]
    headers = {"X-Project-Token": token} if token_header else {}

    # 2. Upload Interface A & B
    dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"  # noqa: E501
    await async_client.post(
        f"/api/projects/{project_id}/interfaces/interface_a/upload",
        files={"file": ("test.png", dummy_img, "image/png")},
        headers=headers,
    )
    await async_client.post(
        f"/api/projects/{project_id}/interfaces/interface_a/approve", headers=headers
    )

    await async_client.post(
        f"/api/projects/{project_id}/interfaces/interface_b/upload",
        files={"file": ("test.png", dummy_img, "image/png")},
        headers=headers,
    )
    await async_client.post(
        f"/api/projects/{project_id}/interfaces/interface_b/approve", headers=headers
    )

    # 3. Configure Connection
    conn_data = {
        "connection": {
            "mode": "coaxial",
            "length_mm": 50.0,
            "offset_x_mm": 0.0,
            "offset_y_mm": 0.0,
            "angle_deg": 0.0,
        },
        "manufacturing": {
            "process": "fdm",
            "material": "PETG",
            "wall_thickness_mm": 3.0,
            "clearance_a_mm": 0.3,
            "clearance_b_mm": 0.2,
        },
    }
    await async_client.put(
        f"/api/projects/{project_id}/connection-config", json=conn_data, headers=headers
    )

    # 4. Start 3D Generation & Succeed Model
    gen_res = await async_client.post(
        f"/api/projects/{project_id}/generation/start",
        json={"mock_scenario": "success"},
        headers=headers,
    )
    job_data = gen_res.json()["data"]

    # Register success
    await async_client.post(
        f"/api/projects/{project_id}/model/succeed",
        json={
            "model_revision": job_data["model_revision"],
            "volume_cm3": 38.5,
        },
        headers=headers,
    )

    return project_id, token, headers


@pytest.mark.asyncio
async def test_missing_model_rejection(async_client: AsyncClient):
    """Test 5: Export is blocked when no model generation has occurred."""
    # Create project without generating model
    res = await async_client.post("/api/projects")
    data = res.json()["data"]
    project_id = data["project_id"]
    headers = {"X-Project-Token": data["project_token"]}

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )
    assert gen_res.status_code == 400
    assert gen_res.json()["error"]["id"] == "IF-STALE-400"


def test_secret_redaction():
    """Test 12: Secret redaction sanitizes tokens and API keys in exception logging."""
    token = "api-12345-abcdef-secret-token"
    raw_error = f"Error connecting to api.zoo.dev with Bearer {token}"
    redacted = redact_secrets(raw_error, token)

    assert token not in redacted
    assert "Bearer [REDACTED]" in redacted or "[REDACTED_TOKEN]" in redacted
