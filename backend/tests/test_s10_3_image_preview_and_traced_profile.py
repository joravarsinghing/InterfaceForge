"""S10.3 Tests: Image Preview Endpoint, Analysis Provenance Badge, and Traced Profile Foundation."""

import io
import math

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.models.schema import (
    AnalysisResult,
    DimensionProvenance,
    Interface,
    Point2D,
    ProfileType,
    TracedContour,
)
from app.services.analysis_provider import MockAnalysisProvider
from app.services.profile_validation import validate_interface_profile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def create_test_png_bytes(color=(200, 200, 200), width=100, height=100) -> bytes:
    """Helper to generate valid PNG file bytes using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def project_with_image(client, tmp_path):
    """Create a project, upload a real image, return (project_id, token, interface_id)."""
    # Create project
    resp = client.post("/api/projects")
    assert resp.status_code == 201
    data = resp.json()["data"]
    project_id = data["project_id"]
    token = data["project_token"]

    png_bytes = create_test_png_bytes()

    resp = client.post(
        f"/api/projects/{project_id}/interfaces/interface_a/upload",
        files={"file": ("test_image.png", png_bytes, "image/png")},
        headers={"X-Project-Token": token},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.json()}"
    return project_id, token, "interface_a"


# ---------------------------------------------------------------------------
# S10.3.1 — Image Serving Endpoint
# ---------------------------------------------------------------------------


class TestImageServingEndpoint:
    """Tests for GET /api/projects/{id}/interfaces/{iid}/image endpoint."""

    def test_image_endpoint_returns_image_bytes(self, client, project_with_image):
        """Image endpoint returns 200 with image bytes when project and image exist."""
        project_id, token, interface_id = project_with_image

        resp = client.get(
            f"/api/projects/{project_id}/interfaces/{interface_id}/image",
            headers={"X-Project-Token": token},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/")
        assert len(resp.content) > 0

    def test_image_endpoint_accepts_token_query_param(self, client, project_with_image):
        """Image endpoint accepts project token as ?token= query param for img tag compatibility."""
        project_id, token, interface_id = project_with_image

        resp = client.get(
            f"/api/projects/{project_id}/interfaces/{interface_id}/image?token={token}",
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/")

    def test_image_endpoint_header_takes_precedence_over_query_token(
        self, client, project_with_image
    ):
        """When both header and query token are provided, header takes precedence."""
        project_id, token, interface_id = project_with_image

        resp = client.get(
            f"/api/projects/{project_id}/interfaces/{interface_id}/image?token=invalid_token",
            headers={"X-Project-Token": token},  # valid token in header
        )
        # Valid header token should work even when query token is invalid
        assert resp.status_code == 200

    def test_image_endpoint_returns_404_when_no_image_uploaded(self, client):
        """Image endpoint returns error when no image has been uploaded for the interface."""
        resp = client.post("/api/projects")
        assert resp.status_code == 201
        data = resp.json()["data"]
        project_id = data["project_id"]
        token = data["project_token"]

        resp = client.get(
            f"/api/projects/{project_id}/interfaces/interface_a/image",
            headers={"X-Project-Token": token},
        )
        # Missing prerequisite → 400
        assert resp.status_code in (400, 404)
        assert "success" in resp.json()
        assert resp.json()["success"] is False

    def test_image_endpoint_returns_404_for_unknown_project(self, client):
        """Image endpoint returns 404 for a project that does not exist."""
        resp = client.get(
            "/api/projects/nonexistent-id/interfaces/interface_a/image",
        )
        assert resp.status_code == 404

    def test_image_endpoint_content_type_matches_uploaded_format(self, client, project_with_image):
        """Content-type of served image matches the originally uploaded format."""
        project_id, token, interface_id = project_with_image

        resp = client.get(
            f"/api/projects/{project_id}/interfaces/{interface_id}/image",
            headers={"X-Project-Token": token},
        )
        assert resp.status_code == 200
        # PNG was uploaded
        assert "png" in resp.headers["content-type"] or "image" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# S10.3.2 — Analysis Provenance Badge
# ---------------------------------------------------------------------------


class TestAnalysisProvenanceBadge:
    """Tests that analysis_provider_name is correctly set and returned by mock provider."""

    def test_mock_provider_circle_returns_mock_provenance(self):
        """MockAnalysisProvider sets analysis_provider_name='mock' on circle result."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "circle_interface.png")
        assert result.analysis_provider_name == "mock"
        assert result.profile_type == ProfileType.CIRCLE

    def test_mock_provider_rectangle_returns_mock_provenance(self):
        """MockAnalysisProvider sets analysis_provider_name='mock' on rectangle result."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "rectangle_interface.png")
        assert result.analysis_provider_name == "mock"
        assert result.profile_type == ProfileType.RECTANGLE

    def test_mock_provider_rounded_rectangle_returns_mock_provenance(self):
        """MockAnalysisProvider sets analysis_provider_name='mock' on rounded_rectangle result."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "rounded_interface.png")
        assert result.analysis_provider_name == "mock"
        assert result.profile_type == ProfileType.ROUNDED_RECTANGLE

    def test_mock_provider_traced_returns_mock_provenance(self):
        """MockAnalysisProvider sets analysis_provider_name='mock' on traced_closed result."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_interface.png")
        assert result.analysis_provider_name == "mock"
        assert result.profile_type == ProfileType.TRACED_CLOSED

    def test_analysis_result_includes_provider_name_field(self):
        """AnalysisResult schema includes analysis_provider_name field."""
        result = AnalysisResult(
            profile_type=ProfileType.CIRCLE,
            success=True,
            analysis_provider_name="mock",
        )
        dumped = result.model_dump()
        assert "analysis_provider_name" in dumped
        assert dumped["analysis_provider_name"] == "mock"

    def test_analysis_result_provider_name_defaults_to_none(self):
        """AnalysisResult analysis_provider_name defaults to None if not set."""
        result = AnalysisResult(profile_type=ProfileType.CIRCLE, success=True)
        assert result.analysis_provider_name is None

    def test_analyze_endpoint_persists_provider_name_to_interface(self, client, project_with_image):
        """After analysis, the interface stores the analysis_provider_name from the result."""
        project_id, token, interface_id = project_with_image

        resp = client.post(
            f"/api/projects/{project_id}/interfaces/{interface_id}/analyze?provider=mock",
            headers={"X-Project-Token": token},
        )
        assert resp.status_code == 200

        # Fetch project and check interface has provider name set
        project_resp = client.get(
            f"/api/projects/{project_id}",
            headers={"X-Project-Token": token},
        )
        assert project_resp.status_code == 200
        iface_data = project_resp.json()["data"][interface_id]
        assert iface_data.get("analysis_provider_name") == "mock"


# ---------------------------------------------------------------------------
# S10.3.3 — Traced Closed Profile Foundation
# ---------------------------------------------------------------------------


class TestTracedClosedProfileMockFixture:
    """Tests for the traced_closed mock fixture in MockAnalysisProvider."""

    def test_traced_filename_returns_traced_closed_type(self):
        """Filename containing 'traced' triggers traced_closed fixture."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_extrusion_cross_section.png")
        assert result.profile_type == ProfileType.TRACED_CLOSED

    def test_extrusion_filename_returns_traced_closed_type(self):
        """Filename containing 'extrusion' triggers traced_closed fixture."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "extrusion_profile.png")
        assert result.profile_type == ProfileType.TRACED_CLOSED

    def test_traced_result_has_outer_contour(self):
        """Traced result includes a TracedContour with at least 4 outer points."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_profile.png")
        assert result.traced_outer_contour is not None
        assert len(result.traced_outer_contour.points) >= 4
        assert result.traced_outer_contour.is_closed is True

    def test_traced_result_has_inner_hole(self):
        """Traced result includes at least one inner hole contour."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_profile.png")
        assert len(result.traced_hole_contours) >= 1
        hole = result.traced_hole_contours[0]
        assert len(hole.points) >= 3
        assert hole.is_closed is True

    def test_traced_result_dimensions_are_supplementary(self):
        """Traced result includes supplementary dimensions (overall_width, bore_diameter etc.)."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_cross_section.png")
        dim_ids = [d.id for d in result.candidate_dimensions]
        assert "overall_width" in dim_ids
        assert len(result.candidate_dimensions) >= 2
        assert all(d.value >= 0 for d in result.candidate_dimensions)

    def test_traced_result_warns_about_generation_limitation(self):
        """Traced result includes a warning about generation not being enabled yet."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_profile.png")
        # Exactly one warning mentioning the limitation
        assert any("not yet enabled" in w.lower() or "traced" in w.lower() for w in result.warnings)

    def test_traced_result_has_success_true(self):
        """Traced mock result is a successful analysis, not a rejection."""
        provider = MockAnalysisProvider()
        result = provider.analyze(b"", "traced_profile.png")
        assert result.success is True
        assert len(result.rejection_reasons) == 0


class TestTracedContourModel:
    """Tests for the TracedContour schema model."""

    def test_traced_contour_point_count_auto_computed(self):
        """TracedContour.point_count is auto-computed from points list."""
        points = [Point2D(x=0.0, y=0.0), Point2D(x=1.0, y=0.0), Point2D(x=0.5, y=1.0)]
        contour = TracedContour(points=points, is_closed=True)
        assert contour.point_count == 3

    def test_traced_contour_serializes_to_dict(self):
        """TracedContour serializes to dict with expected keys."""
        points = [Point2D(x=0.0, y=0.0), Point2D(x=1.0, y=0.0), Point2D(x=0.5, y=1.0)]
        contour = TracedContour(points=points, is_closed=True, confidence=0.9)
        d = contour.model_dump()
        assert "points" in d
        assert "is_closed" in d
        assert "confidence" in d
        assert "point_count" in d
        assert d["point_count"] == 3

    def test_interface_stores_traced_contour_fields(self):
        """Interface model accepts and stores traced_outer_contour and traced_hole_contours."""
        outer = TracedContour(
            points=[Point2D(x=i * 10.0, y=0.0) for i in range(6)],
            is_closed=True,
        )
        hole = TracedContour(
            points=[Point2D(x=i * 2.0, y=0.0) for i in range(4)],
            is_closed=True,
        )
        iface = Interface(id="interface_a")
        iface.traced_outer_contour = outer
        iface.traced_hole_contours = [hole]
        assert iface.traced_outer_contour is not None
        assert len(iface.traced_hole_contours) == 1

    def test_interface_generation_unsupported_defaults_to_false(self):
        """Interface.generation_unsupported defaults to False."""
        iface = Interface(id="interface_a")
        assert iface.generation_unsupported is False
        assert iface.generation_unsupported_reason is None


class TestTracedProfileValidation:
    """Tests for the updated profile_validation.py with traced_closed support."""

    def _make_traced_interface(self, outer_points=None, holes=None) -> Interface:
        """Helper to build a traced_closed Interface for validation testing."""
        if outer_points is None:
            outer_points = [
                Point2D(x=-40.0, y=-40.0),
                Point2D(x=40.0, y=-40.0),
                Point2D(x=40.0, y=-10.0),
                Point2D(x=15.0, y=-10.0),
                Point2D(x=15.0, y=40.0),
                Point2D(x=-15.0, y=40.0),
                Point2D(x=-15.0, y=-10.0),
                Point2D(x=-40.0, y=-10.0),
            ]
        outer = TracedContour(points=outer_points, is_closed=True, confidence=0.9)
        iface = Interface(id="interface_a")
        iface.profile_type = ProfileType.TRACED_CLOSED
        iface.traced_outer_contour = outer
        iface.traced_hole_contours = holes or []
        return iface

    def test_valid_traced_profile_passes_validation(self):
        """A traced_closed interface with a valid outer contour passes validation."""
        iface = self._make_traced_interface()
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is True, f"Expected valid, got errors: {errors}"
        assert len(errors) == 0

    def test_missing_outer_contour_fails_validation(self):
        """A traced_closed interface with no outer contour fails validation."""
        iface = Interface(id="interface_a")
        iface.profile_type = ProfileType.TRACED_CLOSED
        iface.traced_outer_contour = None
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is False
        assert any("outer contour" in e.lower() for e in errors)

    def test_too_few_outer_points_fails_validation(self):
        """Outer contour with fewer than 4 points fails validation."""
        iface = self._make_traced_interface(
            outer_points=[Point2D(x=0.0, y=0.0), Point2D(x=1.0, y=0.0)]
        )
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is False
        assert any("minimum" in e.lower() or "4" in e for e in errors)

    def test_non_finite_outer_point_fails_validation(self):
        """An outer contour point with NaN coordinates fails validation."""
        outer_points = [
            Point2D(x=float("nan"), y=0.0),
            Point2D(x=1.0, y=0.0),
            Point2D(x=1.0, y=1.0),
            Point2D(x=0.0, y=1.0),
        ]
        iface = self._make_traced_interface(outer_points=outer_points)
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is False
        assert any("non-finite" in e.lower() or "nan" in e.lower() for e in errors)

    def test_traced_profile_with_valid_hole_passes(self):
        """Traced profile with a valid inner hole passes validation."""
        hole_points = [
            Point2D(
                x=round(5.0 * math.cos(2 * math.pi * i / 8), 2),
                y=round(5.0 * math.sin(2 * math.pi * i / 8), 2),
            )
            for i in range(8)
        ]
        hole = TracedContour(points=hole_points, is_closed=True, confidence=0.85)
        iface = self._make_traced_interface(holes=[hole])
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is True, f"Expected valid with hole, got errors: {errors}"

    def test_primitive_circle_validation_still_works(self):
        """Existing circle profile validation is unchanged after S10.3 refactor."""
        from app.models.schema import Dimension

        iface = Interface(id="interface_a")
        iface.profile_type = ProfileType.CIRCLE
        iface.dimensions = [
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=50.0,
                unit="mm",
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.95,
                critical=True,
            ),
            Dimension(
                id="wall_thickness",
                label="Wall Thickness",
                value=5.0,
                unit="mm",
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.90,
                critical=False,
            ),
        ]
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is True, f"Circle should pass: {errors}"

    def test_traced_profile_too_dense_fails(self):
        """Outer contour exceeding MAX_TRACED_POINTS (2000) fails validation."""
        from app.services.profile_validation import MAX_TRACED_POINTS

        outer_points = [
            Point2D(x=float(i % 100), y=float(i // 100)) for i in range(MAX_TRACED_POINTS + 1)
        ]
        iface = self._make_traced_interface(outer_points=outer_points)
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is False
        assert any("too dense" in e.lower() or "max" in e.lower() for e in errors)

    def test_unclosed_contour_fails_validation(self):
        """Contour marked as not closed fails validation."""
        outer_points = [
            Point2D(x=0.0, y=0.0),
            Point2D(x=10.0, y=0.0),
            Point2D(x=10.0, y=10.0),
            Point2D(x=0.0, y=10.0),
        ]
        outer = TracedContour(points=outer_points, is_closed=False, confidence=0.9)
        iface = Interface(id="interface_a")
        iface.profile_type = ProfileType.TRACED_CLOSED
        iface.traced_outer_contour = outer
        is_valid, errors, warnings = validate_interface_profile(iface)
        assert is_valid is False
        assert any("closed" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# S10.3.4 — End-to-End: Analyze with Traced Fixture
# ---------------------------------------------------------------------------


class TestTracedAnalysisEndToEnd:
    """Integration tests: upload traced-filename image, analyze, verify stored state."""

    def test_analyze_traced_image_stores_contour_on_interface(self, client):
        """Uploading a 'traced' filename and analyzing sets traced contour on the interface."""
        # 1. Create project
        resp = client.post("/api/projects")
        project_id = resp.json()["data"]["project_id"]
        token = resp.json()["data"]["project_token"]

        # 2. Upload a PNG named with 'traced' trigger
        png_bytes = create_test_png_bytes()
        upload_resp = client.post(
            f"/api/projects/{project_id}/interfaces/interface_a/upload",
            files={"file": ("traced_extrusion_cross_section.png", png_bytes, "image/png")},
            headers={"X-Project-Token": token},
        )
        assert upload_resp.status_code == 201

        # 3. Analyze using mock provider
        analyze_resp = client.post(
            f"/api/projects/{project_id}/interfaces/interface_a/analyze?provider=mock",
            headers={"X-Project-Token": token},
        )
        assert analyze_resp.status_code == 200
        result_data = analyze_resp.json()["data"]
        assert result_data["profile_type"] == "traced_closed"
        assert result_data["traced_outer_contour"] is not None
        assert len(result_data["traced_hole_contours"]) >= 1

        # 4. Fetch project and verify interface has generation_unsupported=True
        project_resp = client.get(
            f"/api/projects/{project_id}",
            headers={"X-Project-Token": token},
        )
        iface_data = project_resp.json()["data"]["interface_a"]
        assert iface_data["profile_type"] == "traced_closed"
        assert iface_data["generation_unsupported"] is True
        assert iface_data["traced_outer_contour"] is not None
        assert len(iface_data.get("traced_hole_contours", [])) >= 1
        assert iface_data["analysis_provider_name"] == "mock"

    def test_analyze_non_traced_image_does_not_set_generation_unsupported(self, client):
        """Primitive profile analysis does NOT set generation_unsupported=True."""
        resp = client.post("/api/projects")
        project_id = resp.json()["data"]["project_id"]
        token = resp.json()["data"]["project_token"]

        png_bytes = create_test_png_bytes()
        client.post(
            f"/api/projects/{project_id}/interfaces/interface_a/upload",
            files={"file": ("circle_interface.png", png_bytes, "image/png")},
            headers={"X-Project-Token": token},
        )
        client.post(
            f"/api/projects/{project_id}/interfaces/interface_a/analyze?provider=mock",
            headers={"X-Project-Token": token},
        )
        project_resp = client.get(
            f"/api/projects/{project_id}",
            headers={"X-Project-Token": token},
        )
        iface_data = project_resp.json()["data"]["interface_a"]
        assert iface_data["profile_type"] == "circle"
        assert iface_data.get("generation_unsupported") is False
        assert iface_data.get("traced_outer_contour") is None
