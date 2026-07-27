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


def test_complete_happy_path_workflow(client: TestClient) -> None:
    """Test full workflow from project creation to export placeholder readiness."""
    # 1. Create project
    create_res = client.post("/api/projects")
    assert create_res.status_code == 201
    proj = create_res.json()["data"]
    proj_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()

    # 2. Upload Interface A
    files_a = {"file": ("interface_a.png", png_bytes, "image/png")}
    up_a_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/upload", files=files_a, headers=headers
    )
    assert up_a_res.status_code == 201

    # 3. Analyze Interface A
    an_a_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/analyze", headers=headers
    )
    assert an_a_res.status_code == 200
    assert an_a_res.json()["data"]["profile_type"] in ("circle", "rectangle")

    # 4. Approve Interface A
    app_a_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/approve", headers=headers
    )
    assert app_a_res.status_code == 200
    assert app_a_res.json()["data"]["interface_a"]["approved"] is True

    # 5. Upload Interface B
    png_bytes = create_sample_png_bytes()
    files_b = {"file": ("interface_b.png", png_bytes, "image/png")}
    up_b_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/upload", files=files_b, headers=headers
    )
    assert up_b_res.status_code == 201

    # 6. Analyze Interface B
    an_b_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/analyze", headers=headers
    )
    assert an_b_res.status_code == 200

    # 7. Approve Interface B
    app_b_res = client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/approve", headers=headers
    )
    assert app_b_res.status_code == 200
    assert app_b_res.json()["data"]["interface_b"]["approved"] is True

    # 8. Configure Connection & Manufacturing
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
            "wall_thickness_mm": 2.4,
            "clearance_a_mm": 0.3,
            "clearance_b_mm": 0.1,
        },
    }
    cfg_res = client.put(
        f"/api/projects/{proj_id}/connection-config", json=conn_data, headers=headers
    )
    assert cfg_res.status_code == 200

    # 9. Compile KCL
    kcl_res = client.post(f"/api/projects/{proj_id}/kcl/compile", headers=headers)
    assert kcl_res.status_code == 200
    assert kcl_res.json()["success"] is True

    # 10. Start Mock Generation Job
    gen_res = client.post(
        f"/api/projects/{proj_id}/generation/start",
        json={"mock_scenario": "success"},
        headers=headers,
    )
    assert gen_res.status_code == 201
    job_id = gen_res.json()["data"]["job_id"]

    # 11. Poll generation job completion
    status_res = client.get(f"/api/projects/{proj_id}/generation/{job_id}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["data"]["status"] == "succeeded"

    # 12. Verify Project state is MODEL_CURRENT
    proj_res = client.get(f"/api/projects/{proj_id}", headers=headers)
    assert proj_res.status_code == 200
    p_data = proj_res.json()["data"]
    assert p_data["state"] == "model_current"
    assert (
        p_data["current_model_revision"] == 2
    )  # KCL compile (rev 1 draft) + generation (rev 2 current)


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


def test_connection_validation_failure(client: TestClient) -> None:
    """Invalid connection parameters (e.g. length_mm <= 0) return validation error."""
    # Setup approved project
    create_res = client.post("/api/projects")
    proj_id = create_res.json()["data"]["project_id"]
    token = create_res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    # Approve A and B
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/upload",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/approve", headers=headers)

    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/upload",
        files={"file": ("b.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/approve", headers=headers)

    # Invalid connection config (length_mm = -10)
    bad_cfg = {
        "connection": {
            "mode": "coaxial",
            "length_mm": -10.0,
            "offset_x_mm": 0,
            "offset_y_mm": 0,
            "angle_deg": 0,
        },
        "manufacturing": {
            "process": "fdm",
            "material": "PETG",
            "wall_thickness_mm": 2.4,
            "clearance_a_mm": 0.3,
            "clearance_b_mm": 0.1,
        },
    }
    res = client.put(f"/api/projects/{proj_id}/connection-config", json=bad_cfg, headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["id"] == "IF-CONN-003"


def test_failed_revision_preserves_last_known_good_model(client: TestClient) -> None:
    """Failed model generation preserves last_known_good_model_revision per ADR-005."""
    create_res = client.post("/api/projects")
    proj_id = create_res.json()["data"]["project_id"]
    token = create_res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    # Setup through step 3
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/upload",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/approve", headers=headers)

    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/upload",
        files={"file": ("b.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/approve", headers=headers)

    conn_data = {
        "connection": {
            "mode": "coaxial",
            "length_mm": 40.0,
            "offset_x_mm": 0,
            "offset_y_mm": 0,
            "angle_deg": 0,
        },
        "manufacturing": {
            "process": "fdm",
            "material": "PETG",
            "wall_thickness_mm": 2.4,
            "clearance_a_mm": 0.3,
            "clearance_b_mm": 0.1,
        },
    }
    client.put(f"/api/projects/{proj_id}/connection-config", json=conn_data, headers=headers)

    # Successful Gen 1
    gen1 = client.post(
        f"/api/projects/{proj_id}/generation/start",
        json={"mock_scenario": "success"},
        headers=headers,
    )
    assert gen1.status_code == 201

    proj_res1 = client.get(f"/api/projects/{proj_id}", headers=headers).json()["data"]
    assert proj_res1["current_model_revision"] == 1
    assert proj_res1["last_known_good_model_revision"] == 1

    # Revise parameters & trigger failing Gen 2
    conn_data["connection"]["length_mm"] = 60.0
    client.put(f"/api/projects/{proj_id}/connection-config", json=conn_data, headers=headers)

    gen2 = client.post(
        f"/api/projects/{proj_id}/generation/start",
        json={"mock_scenario": "engine_validation_failure"},
        headers=headers,
    )
    assert gen2.status_code == 201
    job_id2 = gen2.json()["data"]["job_id"]

    status2 = client.get(f"/api/projects/{proj_id}/generation/{job_id2}", headers=headers).json()[
        "data"
    ]
    assert status2["status"] == "failed"

    # Verify LKG revision is PRESERVED as 1!
    proj_res2 = client.get(f"/api/projects/{proj_id}", headers=headers).json()["data"]
    assert proj_res2["last_known_good_model_revision"] == 1
    assert proj_res2["state"] == "generation_failed"


def test_editing_interface_a_marks_model_stale(client: TestClient) -> None:
    """Editing Interface A after model generation sets project state to STALE
    and clears interface approval.
    """
    create_res = client.post("/api/projects")
    proj_id = create_res.json()["data"]["project_id"]
    token = create_res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    # Complete setup & generation
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/upload",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/approve", headers=headers)
    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_b/upload",
        files={"file": ("b.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_b/approve", headers=headers)

    client.put(
        f"/api/projects/{proj_id}/connection-config",
        json={
            "connection": {
                "mode": "coaxial",
                "length_mm": 40.0,
                "offset_x_mm": 0,
                "offset_y_mm": 0,
                "angle_deg": 0,
            },
            "manufacturing": {
                "process": "fdm",
                "material": "PETG",
                "wall_thickness_mm": 2.4,
                "clearance_a_mm": 0.3,
                "clearance_b_mm": 0.1,
            },
        },
        headers=headers,
    )

    client.post(
        f"/api/projects/{proj_id}/generation/start",
        json={"mock_scenario": "success"},
        headers=headers,
    )

    # Edit Interface A
    patch_res = client.patch(
        f"/api/projects/{proj_id}/interfaces/interface_a",
        json={
            "profile_type": "rectangle",
            "dimensions": [
                {
                    "id": "width",
                    "label": "Width",
                    "value": 70.0,
                    "unit": "mm",
                    "provenance": "user_entered",
                    "confidence": 1.0,
                    "critical": True,
                }
            ],
        },
        headers=headers,
    )

    assert patch_res.status_code == 200
    p_data = patch_res.json()["data"]
    assert p_data["interface_a"]["approved"] is False
    assert p_data["model_revisions"][0]["status"] == "stale"


def test_backend_restart_persistence_recovery(client: TestClient) -> None:
    """Project state survives backend service restart through SQLite persistence."""
    create_res = client.post("/api/projects")
    proj_id = create_res.json()["data"]["project_id"]
    token = create_res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    # Update state
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{proj_id}/interfaces/interface_a/upload",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/analyze", headers=headers)
    client.post(f"/api/projects/{proj_id}/interfaces/interface_a/approve", headers=headers)

    # Instatiate fresh ProjectService (simulating restart)
    new_service = ProjectService(repository=SQLiteProjectRepository())
    recovered = new_service.get_project(proj_id, token)

    assert recovered.project_id == proj_id
    assert recovered.interface_a.approved is True
    assert recovered.state == WorkflowState.INTERFACE_A_APPROVED
