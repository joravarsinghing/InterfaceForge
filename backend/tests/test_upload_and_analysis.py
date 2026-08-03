"""Tests for image upload and deterministic analysis providers."""

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


def test_clean_profile_uses_opencv_without_gemini_by_default(
    client: TestClient, monkeypatch
) -> None:
    from app.services.analysis_provider import GeminiAnalysisProvider

    def fail_if_called(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Gemini should not run for default clean-profile analysis")

    monkeypatch.setattr(GeminiAnalysisProvider, "analyze", fail_if_called)
    res = client.post("/api/projects")
    project = res.json()["data"]
    headers = {"X-Project-Token": project["project_token"]}
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/upload",
        files={"file": ("valid_circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    analyze = client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/analyze",
        headers=headers,
    )
    assert analyze.status_code == 200, analyze.json()
    data = analyze.json()["data"]
    assert data["analysis_provider_name"] == "opencv"
    stored = client.get(f"/api/projects/{project['project_id']}", headers=headers).json()["data"]
    assert stored["interface_a"]["analysis_provider_name"] == "opencv"
    assert stored["interface_a"]["traced_outer_contour"] is not None


def test_explicit_ai_guidance_uses_gemini_guided_opencv(client: TestClient, monkeypatch) -> None:
    from app.services.analysis_provider import GeminiAnalysisProvider

    def fake_analyze(self, image_bytes: bytes, filename: str):  # type: ignore[no-untyped-def]
        from app.services.analysis_provider import OpenCVAnalysisProvider

        result = OpenCVAnalysisProvider().analyze(image_bytes, filename)
        result.analysis_provider_name = "gemini_guided_opencv"
        result.provider_used = "gemini_guided_opencv"
        return result

    monkeypatch.setattr(GeminiAnalysisProvider, "analyze", fake_analyze)
    res = client.post("/api/projects")
    project = res.json()["data"]
    headers = {"X-Project-Token": project["project_token"]}
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/upload",
        files={"file": ("valid_circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    analyze = client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/analyze?provider=gemini",
        headers=headers,
    )
    assert analyze.status_code == 200, analyze.json()
    assert analyze.json()["data"]["analysis_provider_name"] == "gemini_guided_opencv"


def test_mock_provider_override_keeps_mock_provenance(client: TestClient) -> None:
    res = client.post("/api/projects")
    project = res.json()["data"]
    headers = {"X-Project-Token": project["project_token"]}
    png_bytes = create_sample_png_bytes()
    client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/upload",
        files={"file": ("valid_circle.png", png_bytes, "image/png")},
        headers=headers,
    )
    analyze = client.post(
        f"/api/projects/{project['project_id']}/interfaces/interface_a/analyze?provider=mock",
        headers=headers,
    )
    assert analyze.status_code == 200, analyze.json()
    assert analyze.json()["data"]["analysis_provider_name"] == "mock"
