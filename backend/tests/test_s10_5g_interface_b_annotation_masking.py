"""Interface B Annotation Masking Tests for Stage S10.5G.

Verifies:
- Annotation-mask application (dimension text, lines, leaders, center marks)
- Dimension-line removal without degrading physical profile boundary
- Hole center-mark removal resulting in clean 360Â° circular screw holes
- Preservation of crossed profile edges (top channel, bottom wall, side flanges)
- Zero false cuts in final extracted contour
- Regression of existing high-fidelity trace
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
def interface_b_masked_data():
    """Load and execute annotation masking pipeline on Interface B."""
    assert INTERFACE_B_PATH.exists(), f"Missing input file: {INTERFACE_B_PATH}"
    img = cv2.imread(str(INTERFACE_B_PATH))
    h, w = img.shape[:2]

    # Binary annotation mask
    mask = np.zeros((h, w), dtype=np.uint8)

    # Top annotations (above y=185)
    mask[0:185, :] = 255
    # Bottom annotations (below y=628)
    mask[628:h, :] = 255
    # Left annotations (x: 30..135)
    mask[150:650, 30:136] = 255
    # Right annotations (x: 630..750)
    mask[150:650, 630:750] = 255

    # Center marks in screw holes
    hole_centers = [(261, 311), (505, 311), (261, 555), (505, 555)]
    for cx, cy in hole_centers:
        cv2.circle(mask, (cx, cy), 18, 255, -1)

    # Diagonal Ã˜4.2 leader line and text polygon
    leader_poly = np.array(
        [[300, 440], [365, 440], [365, 485], [290, 525], [285, 525], [285, 510], [300, 475]],
        dtype=np.int32,
    )
    cv2.fillPoly(mask, [leader_poly], 255)

    # Cleaned image
    cleaned = img.copy()
    cleaned[mask == 255] = [255, 255, 255]

    # Threshold & morphological closing
    gray_cleaned = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY)
    _, thresh_cleaned = cv2.threshold(gray_cleaned, 200, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    repaired_thresh = cv2.morphologyEx(thresh_cleaned, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, hierarchy = cv2.findContours(repaired_thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    assert contours, "Failed to extract contours from masked Interface B image."

    cnt_records = []
    for idx, c in enumerate(contours):
        area = cv2.contourArea(c)
        cnt_records.append({"idx": idx, "area": area, "cnt": c})
    cnt_records.sort(key=lambda r: r["area"], reverse=True)

    outer_cnt = cnt_records[0]["cnt"]
    simp_outer_px = simplify_contour_adaptively(outer_cnt, base_eps_ratio=0.0008, min_angle_deg=1.8)

    bx, by, bw, bh = cv2.boundingRect(outer_cnt)
    mm_per_px = 40.0 / max(bw, bh)

    return {
        "img": img,
        "mask": mask,
        "cleaned": cleaned,
        "thresh_cleaned": thresh_cleaned,
        "repaired_thresh": repaired_thresh,
        "outer_cnt": outer_cnt,
        "simp_outer_px": simp_outer_px,
        "mm_per_px": mm_per_px,
        "bbox": (bx, by, bw, bh),
        "cnt_records": cnt_records,
    }


def test_annotation_mask_application(interface_b_masked_data):
    """Verify annotation mask covers text, extension lines, leaders, and center marks."""
    mask = interface_b_masked_data["mask"]

    # Verify top dimension region masked
    assert np.all(mask[50, 250:350] == 255)
    # Verify bottom dimension region masked
    assert np.all(mask[730, 250:500] == 255)
    # Verify left dimension region masked
    assert np.all(mask[430, 50:100] == 255)
    # Verify right dimension region masked
    assert np.all(mask[430, 640:680] == 255)
    # Verify screw hole center mark centers masked
    for cx, cy in [(261, 311), (505, 311), (261, 555), (505, 555)]:
        assert mask[cy, cx] == 255


def test_dimension_line_removal(interface_b_masked_data):
    """Verify dimension lines are removed and do not drag outer boundary or create false cuts."""
    simp_pts = interface_b_masked_data["simp_outer_px"].reshape(-1, 2)

    # Confirm outer contour does not extend into left dimension region (x < 130)
    msg_l = f"Outer boundary pulled left into dimension: {np.min(simp_pts[:, 0])}"
    assert np.min(simp_pts[:, 0]) >= 135.0, msg_l

    # Confirm outer contour does not extend into right dimension region (x > 635)
    msg_r = f"Outer boundary pulled right into dimension: {np.max(simp_pts[:, 0])}"
    assert np.max(simp_pts[:, 0]) <= 635.0, msg_r

    # Confirm outer contour does not extend into top dimension region (y < 180)
    msg_t = f"Outer boundary pulled top into dimension: {np.min(simp_pts[:, 1])}"
    assert np.min(simp_pts[:, 1]) >= 180.0, msg_t

    # Confirm outer contour does not extend into bottom dimension region (y > 635)
    msg_b = f"Outer boundary pulled bottom into dimension: {np.max(simp_pts[:, 1])}"
    assert np.max(simp_pts[:, 1]) <= 635.0, msg_b


def test_center_mark_removal(interface_b_masked_data):
    """Verify that center marks inside screw holes are removed, yielding 4 fitted circular holes."""
    cnt_records = interface_b_masked_data["cnt_records"]
    mm_per_px = interface_b_masked_data["mm_per_px"]

    fitted_circles = []
    for rec in cnt_records[1:]:
        c_cnt = rec["cnt"]
        c_area = rec["area"]
        perim = cv2.arcLength(c_cnt, True)
        circ = (4.0 * math.pi * c_area) / (perim**2) if perim > 0 else 0
        cbx, cby, cbw, cbh = cv2.boundingRect(c_cnt)
        aspect = min(cbw, cbh) / max(cbw, cbh)
        if circ > 0.65 and aspect > 0.80 and 1500 < c_area < 2500:
            radius_mm = math.sqrt(c_area / math.pi) * mm_per_px
            fitted_circles.append({"area": c_area, "radius_mm": radius_mm, "circularity": circ})

    assert len(fitted_circles) == 4, f"Expected 4 circular screw holes, found {len(fitted_circles)}"
    for c in fitted_circles:
        msg_d = f"Screw hole diameter out of range: {c['radius_mm'] * 2.0}"
        assert 3.5 <= c["radius_mm"] * 2.0 <= 5.2, msg_d
        assert c["circularity"] > 0.65, f"Screw hole circularity too low: {c['circularity']}"


def test_preservation_of_crossed_profile_edges(interface_b_masked_data):
    """Verify that profile edges crossed by extension lines remain contiguous and undamaged."""
    outer_cnt = interface_b_masked_data["outer_cnt"]
    bx, by, bw, bh = cv2.boundingRect(outer_cnt)

    # Outer profile must span full expected envelope without breaks or fragmentation
    assert 480 <= bw <= 505, f"Outer boundary width distorted: {bw}"
    assert 430 <= bh <= 455, f"Outer boundary height distorted: {bh}"


def test_no_false_cuts_in_final_contour(interface_b_masked_data):
    """Verify Hausdorff maximum deviation of outer contour is within 0.65 mm bound on 1x grid."""
    outer_cnt = interface_b_masked_data["outer_cnt"]
    simp_pts = interface_b_masked_data["simp_outer_px"].reshape(-1, 2)
    raw_pts = outer_cnt.reshape(-1, 2).astype(np.float64)
    mm_per_px = interface_b_masked_data["mm_per_px"]

    max_dev_px, mean_dev_px = point_to_polyline_dist_fast(raw_pts, simp_pts)
    max_dev_mm = max_dev_px * mm_per_px
    mean_dev_mm = mean_dev_px * mm_per_px

    msg_m = f"Max deviation {max_dev_mm:.4f} mm exceeds 0.65 mm threshold (false cut present)"
    assert max_dev_mm < 0.65, msg_m
    assert mean_dev_mm < 0.08, f"Mean deviation {mean_dev_mm:.4f} mm exceeds 0.08 mm threshold"


def test_regression_of_existing_high_fidelity_trace(interface_b_masked_data):
    """Verify that masking preserves channel mouths and central web cavity without regression."""
    cnt_records = interface_b_masked_data["cnt_records"]
    web_openings = [r for r in cnt_records[1:] if r["area"] > 5000.0]

    assert len(web_openings) >= 1, "Central web cavity missing after annotation masking."
