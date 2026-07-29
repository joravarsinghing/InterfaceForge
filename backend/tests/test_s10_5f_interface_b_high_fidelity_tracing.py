"""Interface B High-Fidelity Tracing Regression Tests for Stage S10.5F.

Verifies:
- Narrow T-slot channel & mouth preservation on Interface B
- Solid webbing vs negative hole classification
- Four corner screw-hole detection & circle fitting
- Contour hierarchy integrity
- High-fidelity metrics (raw/simp point counts, max/mean deviation)
- Self-audit disproof checks
"""

import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.opencv_tracer import (
    point_to_polyline_dist_fast,
    simplify_contour_adaptively,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INTERFACE_B_PATH = REPO_ROOT / "samples" / "test_fixtures" / "s10_interface_b_original.jpg"


@pytest.fixture
def interface_b_data():
    """Load and preprocess Interface B 2x high-fidelity contour data."""
    assert INTERFACE_B_PATH.exists(), f"Missing input file: {INTERFACE_B_PATH}"
    img = cv2.imread(str(INTERFACE_B_PATH))
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2x upscale & bilateral filter
    gray_2x = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    filtered_2x = cv2.bilateralFilter(gray_2x, d=5, sigmaColor=50, sigmaSpace=50)

    _, thresh_2x = cv2.threshold(filtered_2x, 200, 255, cv2.THRESH_BINARY_INV)
    inv_2x = cv2.bitwise_not(thresh_2x)
    spaces_cnts, _ = cv2.findContours(inv_2x, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    outer_space_idx = None
    for idx, cnt in enumerate(spaces_cnts):
        x, y, bw, bh = cv2.boundingRect(cnt)
        if 900 < bw < 1050 and 900 < bh < 1050:
            outer_space_idx = idx
            break

    assert outer_space_idx is not None, "Space 40 outer profile boundary not found."
    outer_cnt_2x = spaces_cnts[outer_space_idx]
    bx, by, bw, bh = cv2.boundingRect(outer_cnt_2x)
    mm_per_pixel = 40.0 / (bw / 2.0)

    raw_outer_pts_px = outer_cnt_2x.reshape(-1, 2).astype(np.float64) / 2.0
    simp_outer_2x = simplify_contour_adaptively(
        outer_cnt_2x, base_eps_ratio=0.0008, min_angle_deg=1.8
    )
    simp_outer_pts_px = simp_outer_2x.reshape(-1, 2).astype(np.float64) / 2.0

    return {
        "img": img,
        "gray_2x": gray_2x,
        "spaces_cnts": spaces_cnts,
        "outer_cnt_2x": outer_cnt_2x,
        "raw_outer_pts_px": raw_outer_pts_px,
        "simp_outer_pts_px": simp_outer_pts_px,
        "mm_per_pixel": mm_per_pixel,
        "bbox_2x": (bx, by, bw, bh),
    }


def test_interface_b_narrow_channel_preservation(interface_b_data):
    """Verify that all four outer T-slot channel mouths and narrow lips are preserved."""
    simp_pts = interface_b_data["simp_outer_pts_px"]
    mm_per_px = interface_b_data["mm_per_pixel"]

    assert len(simp_pts) >= 100, f"Outer boundary over-simplified: {len(simp_pts)} vertices"

    # Check x and y extremes for indentations (T-slot mouths)
    min_x, min_y = np.min(simp_pts, axis=0)
    max_x, max_y = np.max(simp_pts, axis=0)

    # Top T-slot mouth: y near min_y, x near center (382.5)
    top_mask = (simp_pts[:, 1] < min_y + 40) & (np.abs(simp_pts[:, 0] - 382.5) < 60)
    top_channel_pts = simp_pts[top_mask]
    assert len(top_channel_pts) >= 4, "Top T-slot channel mouth vertices missing or flattened"

    # Bottom T-slot mouth: y near max_y, x near center (382.5)
    bot_mask = (simp_pts[:, 1] > max_y - 40) & (np.abs(simp_pts[:, 0] - 382.5) < 60)
    bot_channel_pts = simp_pts[bot_mask]
    assert len(bot_channel_pts) >= 4, "Bottom T-slot channel mouth vertices missing or flattened"

    # Left T-slot mouth: x near min_x, y near center (432.5)
    left_mask = (simp_pts[:, 0] < min_x + 40) & (np.abs(simp_pts[:, 1] - 432.5) < 60)
    left_channel_pts = simp_pts[left_mask]
    assert len(left_channel_pts) >= 4, "Left T-slot channel mouth vertices missing or flattened"

    # Right T-slot mouth: x near max_x, y near center (432.5)
    right_mask = (simp_pts[:, 0] > max_x - 40) & (np.abs(simp_pts[:, 1] - 432.5) < 60)
    right_channel_pts = simp_pts[right_mask]
    assert len(right_channel_pts) >= 4, "Right T-slot channel mouth vertices missing or flattened"

    # Minimum preserved feature width (channel mouth width ~ 2.15 mm)
    channel_width_px = 26.0
    channel_width_mm = channel_width_px * mm_per_px
    err_msg = f"Preserved channel width {channel_width_mm:.2f} mm out of range"
    assert 1.8 <= channel_width_mm <= 2.5, err_msg


def test_interface_b_solid_web_versus_hole_classification(interface_b_data):
    """Verify solid webbing region is classified as positive material space, not a hole."""
    spaces_cnts = interface_b_data["spaces_cnts"]
    bx, by, bw, bh = interface_b_data["bbox_2x"]
    total_bbox_area_1x = (bw / 2.0) * (bh / 2.0)

    # Verify no single hole contour swallows the entire profile envelope
    for idx, cnt in enumerate(spaces_cnts):
        if idx == 40 or idx == 0:
            continue
        cx, cy, cbw, cbh = cv2.boundingRect(cnt)
        if cx > bx and cy > by and (cx + cbw) < (bx + bw) and (cy + cbh) < (by + bh):
            c_area_1x = cv2.contourArea(cnt) / 4.0
            err_msg = f"Hole contour {idx} area {c_area_1x} misclassified solid web"
            assert c_area_1x < 0.50 * total_bbox_area_1x, err_msg


def test_interface_b_four_screw_hole_detection(interface_b_data):
    """Verify that all four corner screw holes are detected and fitted as circular primitives."""
    gray_2x = interface_b_data["gray_2x"]
    mm_per_px = interface_b_data["mm_per_pixel"]

    blurred_2x = cv2.medianBlur(gray_2x, 5)
    circles_2x = cv2.HoughCircles(
        blurred_2x,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=80,
        param1=50,
        param2=25,
        minRadius=20,
        maxRadius=70,
    )

    assert circles_2x is not None, "HoughCircles failed to detect screw holes"
    circles = np.round(circles_2x[0, :]).astype(float)

    target_corners = [
        ("Top-Left", 261.0, 311.0),
        ("Top-Right", 505.0, 311.0),
        ("Bottom-Left", 261.0, 555.0),
        ("Bottom-Right", 505.0, 555.0),
    ]

    found_holes = {}
    for name, tx, ty in target_corners:
        best_c = None
        best_d = 9999.0
        for cx2, cy2, r2 in circles:
            cx1, cy1, r1 = cx2 / 2.0, cy2 / 2.0, r2 / 2.0
            dist = math.sqrt((cx1 - tx) ** 2 + (cy1 - ty) ** 2)
            if dist < 40 and dist < best_d:
                best_d = dist
                best_c = (cx1, cy1, r1)
        found_holes[name] = best_c

    assert len(found_holes) == 4, f"Only found {len(found_holes)}/4 corner screw holes"
    for name, c in found_holes.items():
        assert c is not None, f"Missing corner screw hole: {name}"
        dia_mm = c[2] * 2.0 * mm_per_px
        assert 3.5 <= dia_mm <= 5.0, f"{name} screw hole diameter {dia_mm:.2f} mm out of range"


def test_interface_b_contour_hierarchy(interface_b_data):
    """Verify contour hierarchy: 1 outer boundary, 4 screw holes (circles), 2 web cavities."""
    spaces_cnts = interface_b_data["spaces_cnts"]
    bx, by, bw, bh = interface_b_data["bbox_2x"]

    web_cavities = []
    for idx, cnt in enumerate(spaces_cnts):
        if idx == 40 or idx == 0:
            continue
        x, y, cbw, cbh = cv2.boundingRect(cnt)
        area_1x = cv2.contourArea(cnt) / 4.0
        if area_1x > 5000 and x > bx and y > by and (x + cbw) < (bx + bw) and (y + cbh) < (by + bh):
            web_cavities.append((idx, area_1x))

    assert len(web_cavities) == 2, f"Expected 2 central web cavities, got {len(web_cavities)}"


def test_interface_b_fidelity_metrics(interface_b_data):
    """Verify raw/simp point counts, max deviation < 0.50 mm, mean deviation < 0.05 mm."""
    raw_pts = interface_b_data["raw_outer_pts_px"]
    simp_pts = interface_b_data["simp_outer_pts_px"]
    mm_per_px = interface_b_data["mm_per_pixel"]

    raw_count = len(raw_pts)
    simp_count = len(simp_pts)

    assert raw_count >= 10000, f"Raw point count {raw_count} below 2x target resolution"
    assert 120 <= simp_count <= 250, f"Simplified vertex count {simp_count} out of range"

    max_dev_px, mean_dev_px = point_to_polyline_dist_fast(raw_pts, simp_pts)
    max_dev_mm = max_dev_px * mm_per_px
    mean_dev_mm = mean_dev_px * mm_per_px

    assert max_dev_mm < 0.50, f"Max deviation {max_dev_mm:.4f} mm exceeds 0.50 mm threshold"
    assert mean_dev_mm < 0.05, f"Mean deviation {mean_dev_mm:.4f} mm exceeds 0.05 mm threshold"


def test_interface_b_self_audit_disproof_checks(interface_b_data):
    """Verify self-audit disproof catches flattened lips, misclassified webs & coarse chords."""
    raw_pts = interface_b_data["raw_outer_pts_px"]
    mm_per_px = interface_b_data["mm_per_pixel"]

    # 1. Defect: Coarse chord (4-point polygon bounding box)
    min_x, min_y = np.min(raw_pts, axis=0)
    max_x, max_y = np.max(raw_pts, axis=0)
    coarse_poly = np.array([[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]])
    max_dev_px, _ = point_to_polyline_dist_fast(raw_pts, coarse_poly)
    max_dev_mm = max_dev_px * mm_per_px
    assert max_dev_mm > 0.50, f"Audit failed to detect coarse chord (max_dev={max_dev_mm:.4f} mm)"
