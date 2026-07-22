"""Tests for Stage S4B — Profile Review and Structural Validation."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.models.schema import DimensionProvenance, ProfileType, WorkflowState


def create_sample_png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_supported_profiles_validation_and_approval(client: TestClient) -> None:
    """Test circle, rectangle, and rounded_rectangle pass structural validation and approval."""
    # Create project
    res = client.post("/api/projects")
    proj = res.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()

    # Upload & analyze Interface A (circle)
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    anal_a = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    ).json()["data"]

    assert anal_a["profile_type"] == ProfileType.CIRCLE
    assert len(anal_a["candidate_dimensions"]) == 2

    # Approve Interface A
    appr_a = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/approve",
        headers=headers,
    )
    assert appr_a.status_code == 200
    assert appr_a.json()["data"]["interface_a"]["approved"] is True
    assert appr_a.json()["data"]["state"] == WorkflowState.INTERFACE_A_APPROVED

    # Upload & analyze Interface B (rectangle)
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/upload",
        files={"file": ("valid_rectangle.png", png_bytes, "image/png")},
        headers=headers,
    )
    anal_b = client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/analyze",
        headers=headers,
    ).json()["data"]
    assert anal_b["profile_type"] == ProfileType.RECTANGLE

    # Approve Interface B
    appr_b = client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/approve",
        headers=headers,
    )
    assert appr_b.status_code == 200
    assert appr_b.json()["data"]["interface_b"]["approved"] is True
    assert appr_b.json()["data"]["state"] == WorkflowState.INTERFACES_APPROVED


def test_fewer_than_two_known_dimensions_rejection(client: TestClient) -> None:
    """Test interface with fewer than two known dimensions fails validation and approval."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    )

    # Patch Interface A to have only 1 dimension in total
    patch_payload = {
        "dimensions": [
            {
                "id": "outer_diameter",
                "label": "Outer Diameter",
                "value": 50.0,
                "unit": "mm",
                "provenance": DimensionProvenance.IMAGE_EXTRACTED,
                "confidence": 0.95,
                "critical": True,
            }
        ]
    }
    patch_res = client.patch(
        f"/api/projects/{p_id}/interfaces/interface_a",
        json=patch_payload,
        headers=headers,
    )
    assert patch_res.status_code == 200
    warnings = patch_res.json()["data"]["interface_a"]["validation"]["warnings"]
    assert any("at least two known dimensions" in w for w in warnings)

    # Approval attempt should fail with IF-APPROVAL-400
    appr_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/approve",
        headers=headers,
    )
    assert appr_res.status_code == 400
    assert appr_res.json()["error"]["id"] == "IF-APPROVAL-400"
    assert "at least two known dimensions" in appr_res.json()["error"]["message"]


def test_zero_or_negative_values_rejection(client: TestClient) -> None:
    """Test non-positive or non-finite dimension values fail validation and approval."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/analyze", headers=headers)

    # Patch with zero value
    patch_payload = {
        "dimensions": [
            {
                "id": "outer_diameter",
                "label": "Outer Diameter",
                "value": -10.0,
                "unit": "mm",
                "provenance": DimensionProvenance.USER_ENTERED,
                "confidence": 1.0,
                "critical": True,
            },
            {
                "id": "wall_thickness",
                "label": "Wall Thickness",
                "value": 5.0,
                "unit": "mm",
                "provenance": DimensionProvenance.USER_ENTERED,
                "confidence": 1.0,
                "critical": False,
            },
        ]
    }
    client.patch(
        f"/api/projects/{p_id}/interfaces/interface_a",
        json=patch_payload,
        headers=headers,
    )

    appr_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/approve",
        headers=headers,
    )
    assert appr_res.status_code == 400
    assert "positive finite value" in appr_res.json()["error"]["message"]


def test_unresolved_critical_dimension_rejection(client: TestClient) -> None:
    """Test unresolved critical dimension fails approval."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/analyze", headers=headers)

    patch_payload = {
        "dimensions": [
            {
                "id": "outer_diameter",
                "label": "Outer Diameter",
                "value": 50.0,
                "unit": "mm",
                "provenance": DimensionProvenance.UNRESOLVED,
                "confidence": 0.5,
                "critical": True,
            },
            {
                "id": "wall_thickness",
                "label": "Wall Thickness",
                "value": 5.0,
                "unit": "mm",
                "provenance": DimensionProvenance.USER_ENTERED,
                "confidence": 1.0,
                "critical": False,
            },
        ]
    }
    client.patch(
        f"/api/projects/{p_id}/interfaces/interface_a",
        json=patch_payload,
        headers=headers,
    )

    appr_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/approve",
        headers=headers,
    )
    assert appr_res.status_code == 400
    assert "unresolved" in appr_res.json()["error"]["message"]


def test_re_edit_clears_approval_increments_revision_marks_stale(client: TestClient) -> None:
    """Test re-editing approved interface clears approval and marks model stale."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()

    # Upload & approve Interface A & B
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/analyze", headers=headers)
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)

    client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/upload",
        files={"file": ("valid_rectangle.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/interfaces/interface_b/analyze", headers=headers)
    client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)

    # Configure connection and start/succeed model
    client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": "coaxial", "length_mm": 100.0},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    client.post(f"/api/projects/{p_id}/model/succeed", json={"model_revision": 1}, headers=headers)

    proj_before = client.get(f"/api/projects/{p_id}", headers=headers).json()["data"]
    rev_before = proj_before["current_schema_revision"]
    assert proj_before["interface_a"]["approved"] is True

    # Patch Interface A (re-edit)
    patch_res = client.patch(
        f"/api/projects/{p_id}/interfaces/interface_a",
        json={"profile_type": ProfileType.ROUNDED_RECTANGLE},
        headers=headers,
    )

    assert patch_res.status_code == 200
    proj_after = patch_res.json()["data"]
    assert proj_after["interface_a"]["approved"] is False
    assert proj_after["interface_a"]["approved_at"] is None
    assert proj_after["current_schema_revision"] == rev_before + 1
    assert proj_after["model_revisions"][0]["status"] == "stale"
    assert proj_after["state"] == WorkflowState.INTERFACE_A_REVIEW_REQUIRED
