"""Unit and integration test suite for canonical project schema, invariants, and API endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.models.schema import (
    ConnectionMode,
    ManufacturingProcess,
    ModelRevisionStatus,
    ProfileType,
    Project,
    WorkflowState,
)
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.services.project_service import ProjectService


def test_project_creation(client: TestClient) -> None:
    """Test project creation endpoint returns 201 with unguessable token and initial state."""
    response = client.post("/api/projects")
    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "project_id" in data
    assert data["project_token"].startswith("tok_")
    assert data["schema_version"] == "0.1"
    assert data["state"] == WorkflowState.NEW


def test_persistence_across_repository_reload(temp_db: Path) -> None:
    """Test persistence across distinct repository instances accessing the same database."""
    repo1 = SQLiteProjectRepository(db_path=str(temp_db))
    service1 = ProjectService(repository=repo1)
    project = service1.create_project()

    # Modify project in repo1
    service1.approve_interface(
        project.project_id, "interface_a", project_token=project.project_token
    )

    # Initialize separate repository instance
    repo2 = SQLiteProjectRepository(db_path=str(temp_db))
    service2 = ProjectService(repository=repo2)
    loaded_project = service2.get_project(project.project_id)

    assert loaded_project is not None
    assert loaded_project.project_id == project.project_id
    assert loaded_project.interface_a.approved is True
    assert loaded_project.state == WorkflowState.INTERFACE_A_APPROVED


def test_serialization_round_trip() -> None:
    """Test Pydantic model serialization and deserialization integrity."""
    service = ProjectService(repository=SQLiteProjectRepository(db_path=":memory:"))
    project = service.create_project()
    json_str = project.model_dump_json()
    reconstructed = Project.model_validate_json(json_str)

    assert reconstructed.project_id == project.project_id
    assert reconstructed.schema_version == project.schema_version
    assert reconstructed.interface_a.id == "interface_a"


def test_valid_workflow_transitions(client: TestClient) -> None:
    """Test full happy-path workflow sequence from creation to export."""
    # 1. Create project
    resp = client.post("/api/projects")
    proj = resp.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    # 2. Mark Interface A uploaded
    resp = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/mark-uploaded?source_image_ref=art_img_a",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.INTERFACE_A_UPLOADED

    # 3. Approve Interface A
    resp = client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.INTERFACE_A_APPROVED

    # 4. Mark Interface B uploaded
    resp = client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/mark-uploaded?source_image_ref=art_img_b",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.INTERFACE_B_UPLOADED

    # 5. Approve Interface B
    resp = client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.INTERFACES_APPROVED

    # 6. Configure Connection
    conn_payload = {
        "mode": ConnectionMode.OFFSET,
        "length_mm": 120.0,
        "offset_x_mm": 15.0,
        "offset_y_mm": 0.0,
        "angle_deg": 0.0,
    }
    resp = client.put(f"/api/projects/{p_id}/connection", json=conn_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.CONNECTION_CONFIGURED

    # 7. Start Model Generation
    resp = client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.GENERATION_IN_PROGRESS

    # 8. Succeed Model Generation
    succ_payload = {
        "model_revision": 1,
        "kcl_artifact_ref": "art_kcl_1",
        "preview_artifact_ref": "art_preview_1",
        "volume_cm3": 45.2,
        "warnings": [],
    }
    resp = client.post(f"/api/projects/{p_id}/model/succeed", json=succ_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["state"] == WorkflowState.MODEL_CURRENT
    assert data["current_model_revision"] == 1
    assert data["last_known_good_model_revision"] == 1

    # 9. Start Export
    resp = client.post(f"/api/projects/{p_id}/export/start", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.EXPORT_IN_PROGRESS

    # 10. Complete Export
    exp_payload = {"stl_artifact_ref": "art_stl_1", "step_artifact_ref": "art_step_1"}
    resp = client.post(f"/api/projects/{p_id}/export/complete", json=exp_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["state"] == WorkflowState.EXPORT_READY


def test_invalid_prerequisites(client: TestClient) -> None:
    """Test invariant enforcement and stable error responses for invalid prerequisites."""
    # Create project
    resp = client.post("/api/projects")
    proj = resp.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    # Invariant 1: Approve Interface B before Interface A -> IF-APPROVAL-400
    resp = client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["id"] == "IF-APPROVAL-400"

    # Invariant 2: Connection update before both interfaces approved -> IF-PREREQ-400
    conn_payload = {"mode": ConnectionMode.COAXIAL, "length_mm": 100.0}
    resp = client.put(f"/api/projects/{p_id}/connection", json=conn_payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["id"] == "IF-PREREQ-400"

    # Approve Interface A only
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)

    # Attempt connection with only A approved -> IF-PREREQ-400
    resp = client.put(f"/api/projects/{p_id}/connection", json=conn_payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["id"] == "IF-PREREQ-400"

    # Invariant 3: Start generation before connection configured -> IF-PREREQ-400
    client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)
    resp = client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["id"] == "IF-PREREQ-400"

    # Invariant 4: Start export before model exists -> IF-STALE-400
    resp = client.post(f"/api/projects/{p_id}/export/start", headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error"]["id"] == "IF-STALE-400"


def test_schema_revision_increments_and_stale_behavior(client: TestClient) -> None:
    """Test schema revision incrementing and downstream model staleness upon upstream edits."""
    # Setup project to model_current state
    resp = client.post("/api/projects")
    proj = resp.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)
    client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)
    client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": "coaxial", "length_mm": 100.0},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    client.post(f"/api/projects/{p_id}/model/succeed", json={"model_revision": 1}, headers=headers)

    # Initial revision check
    resp = client.get(f"/api/projects/{p_id}", headers=headers)
    proj_data = resp.json()["data"]
    initial_schema_rev = proj_data["current_schema_revision"]

    # Invariant 5: Edit approved Interface A
    patch_resp = client.patch(
        f"/api/projects/{p_id}/interfaces/interface_a",
        json={
            "profile_type": ProfileType.RECTANGLE,
            "dimensions": [
                {
                    "id": "width",
                    "label": "Width",
                    "value": 50.0,
                    "unit": "mm",
                    "provenance": "system_inferred",
                    "confidence": 1.0,
                    "critical": True,
                    "feature_ref": "outer_contour",
                },
                {
                    "id": "height",
                    "label": "Height",
                    "value": 40.0,
                    "unit": "mm",
                    "provenance": "system_inferred",
                    "confidence": 1.0,
                    "critical": True,
                    "feature_ref": "outer_contour",
                },
            ],
        },
        headers=headers,
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()["data"]
    assert data["current_schema_revision"] == initial_schema_rev + 1
    assert data["interface_a"]["approved"] is False
    assert data["model_revisions"][0]["status"] == ModelRevisionStatus.STALE

    # Re-approve A & B and update connection to bring model to current again
    reapprove_a = client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)
    assert reapprove_a.status_code == 200
    client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": ConnectionMode.COAXIAL, "length_mm": 100.0},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    client.post(f"/api/projects/{p_id}/model/succeed", json={"model_revision": 2}, headers=headers)

    # Invariant 6: Edit connection values -> marks model #2 stale
    conn_resp = client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": ConnectionMode.ANGLED, "length_mm": 150.0, "angle_deg": 15.0},
        headers=headers,
    )
    assert conn_resp.status_code == 200
    data = conn_resp.json()["data"]
    assert data["state"] == WorkflowState.MODEL_STALE
    assert data["model_revisions"][1]["status"] == ModelRevisionStatus.STALE

    # Edit manufacturing settings -> marks model stale
    mfg_resp = client.put(
        f"/api/projects/{p_id}/manufacturing",
        json={
            "process": ManufacturingProcess.SLA,
            "material": "Resin",
            "wall_thickness_mm": 3.0,
            "clearance_a_mm": 0.2,
            "clearance_b_mm": 0.2,
        },
        headers=headers,
    )
    assert mfg_resp.status_code == 200
    assert mfg_resp.json()["data"]["state"] == WorkflowState.MODEL_STALE


def test_last_known_good_preservation(client: TestClient) -> None:
    """Test Invariant 7: Failed generation preserves last-known-good model revision."""
    resp = client.post("/api/projects")
    proj = resp.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    reapprove_a = client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)
    assert reapprove_a.status_code == 200
    client.post(f"/api/projects/{p_id}/interfaces/interface_b/approve", headers=headers)
    client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": "coaxial", "length_mm": 100.0},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/model/start", headers=headers)
    client.post(f"/api/projects/{p_id}/model/succeed", json={"model_revision": 1}, headers=headers)

    # Model 1 is current & last known good
    resp = client.get(f"/api/projects/{p_id}", headers=headers)
    assert resp.json()["data"]["last_known_good_model_revision"] == 1

    # Edit connection and start generation #2
    client.put(
        f"/api/projects/{p_id}/connection",
        json={"mode": "offset", "length_mm": 120.0, "offset_x_mm": 10.0},
        headers=headers,
    )
    client.post(f"/api/projects/{p_id}/model/start", headers=headers)

    # Fail generation #2
    fail_resp = client.post(
        f"/api/projects/{p_id}/model/fail",
        json={"model_revision": 2, "error_message": "Loft self-intersection detected"},
        headers=headers,
    )
    assert fail_resp.status_code == 200
    data = fail_resp.json()["data"]
    assert data["state"] == WorkflowState.GENERATION_FAILED
    assert data["last_known_good_model_revision"] == 1  # Preserved!
    assert data["model_revisions"][1]["status"] == ModelRevisionStatus.FAILED


def test_project_not_found(client: TestClient) -> None:
    """Test 404 response with IF-PROJ-404 for missing project ID."""
    resp = client.get("/api/projects/non-existent-uuid")
    assert resp.status_code == 404
    err = resp.json()["error"]
    assert err["id"] == "IF-PROJ-404"


def test_invalid_project_token(client: TestClient) -> None:
    """Test 401 response with IF-AUTH-401 for incorrect project token."""
    resp = client.post("/api/projects")
    proj = resp.json()["data"]
    p_id = proj["project_id"]

    resp = client.get(f"/api/projects/{p_id}", headers={"X-Project-Token": "invalid-token-123"})
    assert resp.status_code == 401
    err = resp.json()["error"]
    assert err["id"] == "IF-AUTH-401"


def test_schema_version_rejection(temp_db: Path) -> None:
    """Test schema version mismatch rejection with IF-SCHEMA-400."""
    repo = SQLiteProjectRepository(db_path=str(temp_db))
    service = ProjectService(repository=repo)
    project = service.create_project()

    # Manually modify schema version in database
    project.schema_version = "99.9"
    repo.save(project)

    try:
        service.get_project(project.project_id)
        assert False, "Expected SchemaVersionMismatchError"
    except Exception as exc:
        assert getattr(exc, "error_id", None) == "IF-SCHEMA-400"
