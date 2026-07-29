"""Stage S10.5E Backend Unit & Integration Tests â€” High-Fidelity Profile Tracing & Arc Fitting."""

import os

import cv2
import numpy as np

from app.services.opencv_tracer import (
    cleanup_image_v2,
    extract_pixel_contours,
    fit_circle_if_valid,
)


def get_sample_path(rel_path: str) -> str:
    if os.path.exists(rel_path):
        return rel_path
    parent_rel = os.path.join("..", rel_path)
    if os.path.exists(parent_rel):
        return parent_rel
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_dir, rel_path)


class TestS105EHighFidelityTracing:
    """Test suite covering Stage S10.5E contour refinement and arc fitting."""

    def test_adaptive_simplification_path(self):
        """Verify adaptive simplification preserves high detail at corners."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(img_bytes, detail_mode="high_fidelity")
        res_high = extract_pixel_contours(cleaned_mask, detail_mode="high_fidelity")
        res_fast = extract_pixel_contours(cleaned_mask, detail_mode="fast")

        assert res_high["success"] is True
        assert res_fast["success"] is True

        assert res_high["simplified_outer_point_count"] > res_fast["simplified_outer_point_count"]
        assert res_high["simplified_outer_point_count"] >= 60

    def test_circle_fitting_on_circular_holes(self):
        """Verify circular holes are accurately detected and fitted with exact circle primitives."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(img_bytes, detail_mode="high_fidelity")
        res = extract_pixel_contours(cleaned_mask, detail_mode="high_fidelity")

        assert res["success"] is True
        fidelity = res["fidelity_metrics"]
        assert fidelity["fitted_circles_count"] == 4

        circle_contours = [h for h in res["traced_hole_contours"] if h.classification == "circle"]
        assert len(circle_contours) == 4
        for c in circle_contours:
            assert c.is_closed is True
            assert len(c.points) == 36

    def test_preservation_of_narrow_slot_openings(self):
        """Verify small slots and flange lips are preserved without over-simplification."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(img_bytes, detail_mode="high_fidelity")
        res = extract_pixel_contours(cleaned_mask, detail_mode="high_fidelity")

        outer_pts = res["traced_outer_contour"].points
        assert len(outer_pts) >= 80

        fidelity = res["fidelity_metrics"]
        assert fidelity["small_features_preserved"] is True
        assert fidelity["max_deviation_mm"] < 0.35
        assert fidelity["mean_deviation_mm"] < 0.05

    def test_fidelity_metrics_computation(self):
        """Verify calculation of Hausdorff max deviation and mean deviation metrics."""
        path = get_sample_path("samples/test_fixtures/s10_interface_a_original.jpg")
        with open(path, "rb") as f:
            img_bytes = f.read()

        cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(img_bytes, detail_mode="high_fidelity")
        res = extract_pixel_contours(cleaned_mask, detail_mode="high_fidelity")

        metrics = res["fidelity_metrics"]
        assert "raw_outer_point_count" in metrics
        assert "simplified_outer_point_count" in metrics
        assert "max_deviation_mm" in metrics
        assert "mean_deviation_mm" in metrics
        assert metrics["raw_outer_point_count"] > 5000
        assert metrics["max_deviation_mm"] >= 0.0
        assert metrics["mean_deviation_mm"] >= 0.0
        assert metrics["mean_deviation_mm"] <= metrics["max_deviation_mm"]

    def test_fit_circle_helper_validation(self):
        """Test fit_circle_if_valid logic on synthetic clean circle vs rectangle."""
        canvas_circle = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(canvas_circle, (100, 100), 40, (255,), -1)
        cnts_c, _ = cv2.findContours(canvas_circle, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        circle_fit = fit_circle_if_valid(cnts_c[0], mm_per_pixel=0.2, center_x=100, center_y=100)

        assert circle_fit is not None
        assert circle_fit["is_circle"] is True
        assert abs(circle_fit["radius_mm"] - 8.0) < 0.2
        assert circle_fit["circularity"] > 0.85

        canvas_sq = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(canvas_sq, (60, 60), (140, 140), (255,), -1)
        cnts_s, _ = cv2.findContours(canvas_sq, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        sq_fit = fit_circle_if_valid(cnts_s[0], mm_per_pixel=0.2, center_x=100, center_y=100)

        assert sq_fit is None

    def test_regression_safety_for_simple_primitive_inputs(self):
        """Verify tracing handles simple clean synthetic inputs (circle, square) cleanly."""
        img_circle = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(img_circle, (150, 150), 80, (255,), -1)
        res_c = extract_pixel_contours(
            img_circle, is_complex_expected=False, detail_mode="high_fidelity"
        )

        assert res_c["success"] is True
        assert res_c["simplified_outer_point_count"] >= 4

        img_sq = np.zeros((300, 300), dtype=np.uint8)
        cv2.rectangle(img_sq, (80, 80), (220, 220), (255,), -1)
        res_sq = extract_pixel_contours(
            img_sq, is_complex_expected=False, detail_mode="high_fidelity"
        )

        assert res_sq["success"] is True
        assert res_sq["simplified_outer_point_count"] == 4
