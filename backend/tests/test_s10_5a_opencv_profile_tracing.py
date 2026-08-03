"""Stage S10.5A Backend Unit & Integration Tests â€” OpenCV Profile Tracing."""

import hashlib
import os

import cv2
import numpy as np

from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schema import (
    Interface,
    Point2D,
    ProfileType,
    TracedContour,
)
from app.services.analysis_provider import GEMINI_SYSTEM_PROMPT, MockAnalysisProvider
from app.services.opencv_tracer import (
    cleanup_image_v2,
    extract_pixel_contours,
    generate_svg_trace_and_overlay,
)
from app.services.profile_validation import validate_interface_profile


def get_sample_path(rel_path: str) -> str:
    """Resolve sample file path regardless of whether pytest is run from repo root or backend/."""
    if os.path.exists(rel_path):
        return rel_path
    parent_rel = os.path.join("..", rel_path)
    if os.path.exists(parent_rel):
        return parent_rel
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_dir, rel_path)


class TestS105AOpenCVProfileTracing:
    """Comprehensive test suite covering Stage S10.5A OpenCV tracing pipeline."""

    def test_gemini_cannot_author_final_contours(self):
        """Verify Gemini prompt prohibits returning 2D polygon points."""
        assert "DO NOT output final 2D polygon contour coordinates" in GEMINI_SYSTEM_PROMPT
        assert "OpenCV pixel tracing" in GEMINI_SYSTEM_PROMPT

    def test_drawing_a_opencv_contour_extraction(self):
        """Drawing A produces non-convex outer contour and inner contours."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        assert os.path.exists(path)

        with open(path, "rb") as f:
            img_bytes = f.read()

        sha256 = hashlib.sha256(img_bytes).hexdigest()
        assert sha256 in (
            "61f94300758d62402d392bd6a02723c7f91bab92cabb1d52598bf276f3eb78bf",
            "97a28147ab6439e170526a1dd0b03608e3a28528ab09a918c724c3f147c930ac",
        )

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(
            img_bytes, crop_box=[0.02, 0.02, 0.98, 0.98]
        )
        res = extract_pixel_contours(cleaned_mask, is_complex_expected=True)

        assert res["success"] is True
        assert res["raw_outer_point_count"] > 1000
        assert res["simplified_outer_point_count"] >= 30
        assert res["inner_contour_count"] >= 5

        outer = res["traced_outer_contour"]
        assert outer is not None
        assert len(outer.points) >= 30

    def test_nested_duplicate_boundary_collapses_to_one_solid_profile(self):
        """Scanned hatch/edge pairs produce one outer profile, not inner traces."""
        mask = np.zeros((240, 240), dtype=np.uint8)
        cv2.rectangle(mask, (20, 20), (220, 220), 255, -1)
        cv2.rectangle(mask, (25, 25), (215, 215), 0, -1)

        res = extract_pixel_contours(mask, is_complex_expected=False)

        assert res["success"] is True
        assert res["inner_contour_count"] == 0
        assert res["traced_outer_contour"].is_closed is True
        assert any("one closed outer profile" in warning for warning in res["warnings"])
    def test_drawing_b_opencv_contour_extraction(self):
        """Drawing B produces non-convex outer contour and corner screw holes."""
        path = get_sample_path("samples/test_fixtures/s10_interface_b_original.jpg")
        assert os.path.exists(path)

        with open(path, "rb") as f:
            img_bytes = f.read()

        sha256 = hashlib.sha256(img_bytes).hexdigest()
        assert sha256 == "203910c8627e03ff523d7056a3fe13c96bd195c148568f878644d64821f76f33"

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(
            img_bytes, crop_box=[0.02, 0.02, 0.98, 0.98]
        )
        res = extract_pixel_contours(cleaned_mask, is_complex_expected=True)

        assert res["success"] is True
        assert res["raw_outer_point_count"] > 1000
        assert res["simplified_outer_point_count"] >= 30
        assert res["inner_contour_count"] >= 4

    def test_real_overlay_contains_source_image(self):
        """Real overlay SVG contains embedded original source image layer."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(img_bytes)
        res = extract_pixel_contours(cleaned_mask)
        trace_svg, overlay_svg, b64_orig = generate_svg_trace_and_overlay(
            res["traced_outer_contour"],
            res["traced_hole_contours"],
            img_bytes,
            cleaned_bytes,
            w,
            h,
            outer_pixel_points=res["outer_pixel_points"],
            hole_pixel_points=res["hole_pixel_points"],
        )

        expected_bounds = f'viewBox="0 0 {w} {h}"'
        assert "<svg" in trace_svg
        assert expected_bounds in trace_svg
        assert expected_bounds in overlay_svg
        assert "Analysis crop" in overlay_svg
        assert "data:image/png" in overlay_svg
        assert 'preserveAspectRatio="none"' in overlay_svg
        assert "xMidYMid" not in overlay_svg
        assert len(b64_orig) > 100

    def test_bounding_box_rejection_for_complex_profile(self):
        """Bounding-box 4-point fallback for complex profiles is flagged/rejected."""
        bounding_box_outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=-20, y=-20),
                Point2D(x=20, y=-20),
                Point2D(x=20, y=20),
                Point2D(x=-20, y=20),
            ],
            is_closed=True,
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            is_complex=True,
            traced_outer_contour=bounding_box_outer,
        )
        is_valid, errors, warnings = validate_interface_profile(interface)
        assert any("detailed non-convex perimeter" in w or "simplified" in w for w in warnings)

    def test_primitive_profile_regression(self):
        """Primitive profiles (circle, rectangle, rounded rectangle) remain fully supported."""
        provider = MockAnalysisProvider()
        circle_res = provider.analyze(b"", "circle_sample.png")
        assert circle_res.profile_type == ProfileType.CIRCLE

        rect_res = provider.analyze(b"", "rectangle_sample.png")
        assert rect_res.profile_type == ProfileType.RECTANGLE

        rounded_res = provider.analyze(b"", "rounded_rectangle_sample.png")
        assert rounded_res.profile_type == ProfileType.ROUNDED_RECTANGLE
