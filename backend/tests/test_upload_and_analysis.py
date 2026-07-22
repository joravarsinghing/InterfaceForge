"""Tests for Image Upload and Mock Analysis Provider (Stage S4A)."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.models.schema import ProfileType, WorkflowState


def create_sample_png_bytes(color=(200, 200, 200), width=100, height=100) -> bytes:
    """Helper to create valid PNG file bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_valid_image_upload(client: TestClient) -> None:
    """Test valid image upload updates state and saves file artifact."""
    res = client.post("/api/projects")
    proj = res.json()["data"]
    p_id = proj["project_id"]
    token = proj["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("test_circle.png", png_bytes, "image/png")},
        headers=headers,
    )

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "artifacts/uploads/" in data["artifact_ref"]
    assert data["original_filename"] == "test_circle.png"

    # Verify project state advanced to interface_a_uploaded
    proj_res = client.get(f"/api/projects/{p_id}", headers=headers)
    assert proj_res.json()["data"]["state"] == WorkflowState.INTERFACE_A_UPLOADED


def test_unsupported_file_type(client: TestClient) -> None:
    """Test uploading unsupported file type returns IF-FILE-400 error."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]

    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("document.pdf", b"%PDF-1.4...", "application/pdf")},
    )

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-FILE-400"
    assert "Unsupported image format" in json_data["error"]["message"]


def test_oversized_file_upload(client: TestClient) -> None:
    """Test uploading file exceeding 10MB limit returns IF-FILE-400 error."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]

    # 10.5 MB dummy byte array
    huge_bytes = b"0" * (10 * 1024 * 1024 + 500 * 1024)

    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("huge_image.png", huge_bytes, "image/png")},
    )

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-FILE-400"
    assert "exceeds the 10MB limit" in json_data["error"]["message"]


def test_corrupt_file_upload(client: TestClient) -> None:
    """Test uploading corrupt image file returns IF-FILE-400 error."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]

    corrupt_bytes = b"THIS_IS_NOT_A_VALID_IMAGE_FILE"

    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("corrupt.png", corrupt_bytes, "image/png")},
    )

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-FILE-400"
    assert "Corrupt or unreadable image file" in json_data["error"]["message"]


def test_path_traversal_sanitization(client: TestClient) -> None:
    """Test malicious filename with path traversal is safely sanitized."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]

    png_bytes = create_sample_png_bytes()
    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("../../../../etc/passwd.png", png_bytes, "image/png")},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert ".." not in data["stored_filename"]
    assert data["original_filename"] == "passwd.png"


def test_interface_b_upload_prerequisite(client: TestClient) -> None:
    """Test uploading Interface B image before Interface A is approved returns IF-PREREQ-400."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]

    png_bytes = create_sample_png_bytes()
    response = client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/upload",
        files={"file": ("interface_b.png", png_bytes, "image/png")},
    )

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-PREREQ-400"
    msg = json_data["error"]["message"]
    assert "Interface A must be approved" in msg


def test_mock_analysis_success_and_state_updates(client: TestClient) -> None:
    """Test full workflow: upload circle -> analyze -> state is interface_a_review_required."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    # Upload valid circle image
    png_bytes = create_sample_png_bytes()
    upload_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("valid_circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert upload_res.status_code == 201

    # Analyze image
    analyze_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    )
    assert analyze_res.status_code == 200
    anal_data = analyze_res.json()["data"]
    assert anal_data["profile_type"] == ProfileType.CIRCLE
    assert anal_data["confidence"] > 0.8
    assert len(anal_data["candidate_dimensions"]) > 0

    # Check project state updated to interface_a_review_required
    proj_res = client.get(f"/api/projects/{p_id}", headers=headers)
    assert proj_res.json()["data"]["state"] == WorkflowState.INTERFACE_A_REVIEW_REQUIRED


def test_mock_analysis_rectangle_and_rounded(client: TestClient) -> None:
    """Test mock analysis detects rectangle and rounded rectangle profiles from filename."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("valid_rectangle.png", png_bytes, "image/png")},
        headers=headers,
    )
    rect_anal = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    ).json()["data"]
    assert rect_anal["profile_type"] == ProfileType.RECTANGLE
    assert len(rect_anal["candidate_dimensions"]) == 2

    # Interface A approve
    client.post(f"/api/projects/{p_id}/interfaces/interface_a/approve", headers=headers)

    # Interface B upload rounded rectangle
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/upload",
        files={"file": ("valid_rounded_rectangle.png", png_bytes, "image/png")},
        headers=headers,
    )
    rounded_anal = client.post(
        f"/api/projects/{p_id}/interfaces/interface_b/analyze",
        headers=headers,
    ).json()["data"]
    assert rounded_anal["profile_type"] == ProfileType.ROUNDED_RECTANGLE
    assert len(rounded_anal["candidate_dimensions"]) == 3
    proj_state = client.get(f"/api/projects/{p_id}", headers=headers).json()["data"]["state"]
    assert proj_state == WorkflowState.INTERFACE_B_REVIEW_REQUIRED


def test_mock_analysis_rejection(client: TestClient) -> None:
    """Test poor image quality triggers analysis rejection with IF-ANALYSIS-400."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("poor_image.png", png_bytes, "image/png")},
        headers=headers,
    )

    anal_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    )
    assert anal_res.status_code == 400
    json_data = anal_res.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-ANALYSIS-400"
    assert "too low to reliably detect interface profile" in json_data["error"]["message"]


def test_malformed_provider_response(client: TestClient) -> None:
    """Test malformed provider response raises IF-ANALYSIS-400."""
    res = client.post("/api/projects")
    p_id = res.json()["data"]["project_id"]
    token = res.json()["data"]["project_token"]
    headers = {"X-Project-Token": token}

    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/upload",
        files={"file": ("malformed_analysis.png", png_bytes, "image/png")},
        headers=headers,
    )

    anal_res = client.post(
        f"/api/projects/{p_id}/interfaces/interface_a/analyze",
        headers=headers,
    )
    assert anal_res.status_code == 400
    json_data = anal_res.json()
    assert json_data["success"] is False
    assert json_data["error"]["id"] == "IF-ANALYSIS-400"
    assert "malformed response" in json_data["error"]["message"]
