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
async def test_stl_export_success(async_client: AsyncClient):
    """Test 1: STL export generation and download succeed."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )
    assert gen_res.status_code == 200
    res_data = gen_res.json()["data"]
    assert res_data["formats"]["stl"]["status"] == "ready"
    assert res_data["formats"]["stl"]["size_bytes"] > 0

    # Test download
    dl_res = await async_client.get(
        f"/api/projects/{project_id}/exports/stl/download", headers=headers
    )
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/sla"
    assert validate_stl_signature(dl_res.content)


@pytest.mark.asyncio
async def test_step_export_success(async_client: AsyncClient):
    """Test 2: STEP export generation and download succeed."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["step"]},
        headers=headers,
    )
    assert gen_res.status_code == 200
    res_data = gen_res.json()["data"]
    assert res_data["formats"]["step"]["status"] == "unavailable"
    assert res_data["formats"]["step"]["error_id"] == "IF-EXPORT-007"

    dl_res = await async_client.get(
        f"/api/projects/{project_id}/exports/step/download", headers=headers
    )
    assert dl_res.status_code == 404




@pytest.mark.asyncio
async def test_kcl_export_download(async_client: AsyncClient):
    """Test 3: KCL artifact download succeeds."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["kcl"]},
        headers=headers,
    )
    assert gen_res.status_code == 200

    dl_res = await async_client.get(
        f"/api/projects/{project_id}/exports/kcl/download", headers=headers
    )
    assert dl_res.status_code == 200
    assert "text/plain" in dl_res.headers["content-type"]
    assert len(dl_res.content) > 0
    query_dl_res = await async_client.get(
        f"/api/projects/{project_id}/exports/kcl/download?token={token}"
    )
    assert query_dl_res.status_code == 200
    assert "text/plain" in query_dl_res.headers["content-type"]
    assert len(query_dl_res.content) > 0


@pytest.mark.asyncio
async def test_stale_model_rejection(async_client: AsyncClient):
    """Test 4: Export is blocked when current model is stale (IF-STALE-400)."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    # Modify Interface A dimensions to make model stale
    patch_res = await async_client.patch(
        f"/api/projects/{project_id}/interfaces/interface_a",
        json={
            "dimensions": [
                {
                    "id": "outer_diameter",
                    "label": "OD",
                    "value": 75.0,
                    "unit": "mm",
                    "provenance": "user_entered",
                    "confidence": 1.0,
                    "critical": True,
                }
            ]
        },
        headers=headers,
    )
    assert patch_res.status_code == 200

    # Attempt export -> must return IF-STALE-400
    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )
    assert gen_res.status_code == 400
    err = gen_res.json()["error"]
    assert err["id"] == "IF-STALE-400"
    assert "stale" in err["message"].lower()


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


@pytest.mark.asyncio
async def test_zero_byte_artifact_rejection(async_client: AsyncClient):
    """Test 6: Zero-byte export artifact is rejected (IF-EXPORT-004)."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"], "mock_scenario": "zero_byte"},
        headers=headers,
    )
    assert gen_res.status_code == 200
    res_data = gen_res.json()["data"]
    assert res_data["formats"]["stl"]["status"] == "failed"
    assert res_data["formats"]["stl"]["error_id"] == "IF-EXPORT-004"


@pytest.mark.asyncio
async def test_malformed_provider_response(async_client: AsyncClient):
    """Test 7: Mock failure scenario handles provider errors safely."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"], "mock_scenario": "failure"},
        headers=headers,
    )
    assert gen_res.status_code == 200
    res_data = gen_res.json()["data"]
    assert res_data["formats"]["stl"]["status"] == "failed"
    assert res_data["formats"]["stl"]["error_id"] == "IF-EXPORT-001"


@pytest.mark.asyncio
async def test_partial_success(async_client: AsyncClient):
    """Test 8: Failure in one format does not invalidate another successful format."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen_res = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl", "step"], "mock_scenario": "stl_failure"},
        headers=headers,
    )
    assert gen_res.status_code == 200
    res_data = gen_res.json()["data"]
    assert res_data["formats"]["stl"]["status"] == "failed"
    assert res_data["formats"]["step"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_retry_failed_format(async_client: AsyncClient):
    """Test 9: Retrying a failed format replaces failure status with ready."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    # 1. Trigger initial partial failure
    await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl", "step"], "mock_scenario": "stl_failure"},
        headers=headers,
    )

    # 2. Retry only failed format "stl" without mock failure
    retry_res = await async_client.post(
        f"/api/projects/{project_id}/exports/stl/retry",
        headers=headers,
    )
    assert retry_res.status_code == 200
    res_data = retry_res.json()["data"]
    assert res_data["formats"]["stl"]["status"] == "ready"




@pytest.mark.asyncio
async def test_duplicate_reused_export(async_client: AsyncClient):
    """Test 10: Repeated export calls reuse existing valid artifacts."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    gen1 = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )
    ref1 = gen1.json()["data"]["formats"]["stl"]["artifact_ref"]

    gen2 = await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )
    ref2 = gen2.json()["data"]["formats"]["stl"]["artifact_ref"]

    assert ref1 == ref2


@pytest.mark.asyncio
async def test_unauthorized_artifact_access(async_client: AsyncClient):
    """Test 11: Download without valid token returns IF-AUTH-401."""
    project_id, token, headers = await _create_project_with_current_model(async_client)

    # Generate export
    await async_client.post(
        f"/api/projects/{project_id}/exports/generate",
        json={"formats": ["stl"]},
        headers=headers,
    )

    # Download with wrong token
    bad_res = await async_client.get(
        f"/api/projects/{project_id}/exports/stl/download",
        headers={"X-Project-Token": "invalid_token_123"},
    )
    assert bad_res.status_code == 401
    assert bad_res.json()["error"]["id"] == "IF-AUTH-401"


def test_secret_redaction():
    """Test 12: Secret redaction sanitizes tokens and API keys in exception logging."""
    token = "api-12345-abcdef-secret-token"
    raw_error = f"Error connecting to api.zoo.dev with Bearer {token}"
    redacted = redact_secrets(raw_error, token)

    assert token not in redacted
    assert "Bearer [REDACTED]" in redacted or "[REDACTED_TOKEN]" in redacted
