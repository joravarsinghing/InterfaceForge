"""OpenCV Profile Tracer module for Stage S10.5E.

Deterministic high-fidelity profile tracing pipeline:
Original drawing image -> Gemini guidance (crop, annotation masks) ->
Edge-preserving preprocessing (upscaling + bilateral filter) ->
Sub-pixel contour extraction -> Adaptive curvature-aware simplification ->
Circle/arc fitting where justified -> High-fidelity SVG trace & overlay.
"""

import base64
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.models.schema import Point2D, ScaleCalibration, TracedContour
from app.services.coordinate_normalizer import fix_exif_orientation, safer_annotation_masking


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash string for bytes."""
    return hashlib.sha256(data).hexdigest()


def _ccw(p1: Point2D, p2: Point2D, p3: Point2D) -> bool:
    return (p3.y - p1.y) * (p2.x - p1.x) > (p2.y - p1.y) * (p3.x - p1.x)


def _segments_intersect(p1: Point2D, p2: Point2D, p3: Point2D, p4: Point2D) -> bool:
    return _ccw(p1, p3, p4) != _ccw(p2, p3, p4) and _ccw(p1, p2, p3) != _ccw(p1, p2, p4)


def check_self_intersection(pts: List[Point2D]) -> bool:
    """Check if closed 2D polygon intersects itself."""
    n = len(pts)
    if n < 4:
        return False
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            p3 = pts[j]
            p4 = pts[(j + 1) % n]
            if _segments_intersect(p1, p2, p3, p4):
                return True
    return False


def compute_deflection_angles(pts: np.ndarray) -> np.ndarray:
    """Compute deflection angles in degrees for closed polygon points (N, 2)."""
    n = len(pts)
    if n < 3:
        return np.zeros(n)
    prev_pts = np.roll(pts, 1, axis=0)
    next_pts = np.roll(pts, -1, axis=0)

    v1 = pts - prev_pts
    v2 = next_pts - pts

    norm1 = np.linalg.norm(v1, axis=1)
    norm2 = np.linalg.norm(v2, axis=1)

    mask = (norm1 > 1e-6) & (norm2 > 1e-6)
    dot_vals = np.zeros(n, dtype=np.float64)
    dot_vals[mask] = np.sum(v1[mask] * v2[mask], axis=1) / (norm1[mask] * norm2[mask])
    dot_clipped = np.clip(dot_vals, -1.0, 1.0)

    angles_rad = np.arccos(dot_clipped)
    result: np.ndarray = np.asarray(np.degrees(angles_rad))
    return result


def simplify_contour_adaptively(
    cnt: np.ndarray, base_eps_ratio: float = 0.0008, min_angle_deg: float = 1.8
) -> np.ndarray:
    """Adaptive contour simplification:
    1. Tight RDP simplification (tight base_eps_ratio) to preserve radii & slot lips.
    2. Collinear filtering on straight edges (deflection angle < min_angle_deg).
    """
    pts = cnt.reshape(-1, 2).astype(np.float64)
    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0:
        return pts

    eps = base_eps_ratio * perimeter
    approx_tight = cv2.approxPolyDP(cnt, eps, True).reshape(-1, 2).astype(np.float64)
    n = len(approx_tight)
    if n < 4:
        return approx_tight

    angles = compute_deflection_angles(approx_tight)
    kept_mask = angles >= min_angle_deg

    if np.sum(kept_mask) < 4:
        return approx_tight

    return approx_tight[kept_mask]


def fit_circle_if_valid(
    cnt: np.ndarray, mm_per_pixel: float, center_x: float, center_y: float
) -> Optional[Dict[str, Any]]:
    """Fit a circle to a contour if circularity and radial deviation justify circle fitting."""
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0 or area == 0:
        return None

    circularity = (4.0 * math.pi * area) / (perimeter**2)
    if circularity < 0.75:
        return None

    m_dict = cv2.moments(cnt)
    if m_dict["m00"] == 0:
        return None
    cx_px = m_dict["m10"] / m_dict["m00"]
    cy_px = m_dict["m01"] / m_dict["m00"]

    pts = cnt.reshape(-1, 2).astype(np.float64)
    dist_px = np.sqrt((pts[:, 0] - cx_px) ** 2 + (pts[:, 1] - cy_px) ** 2)
    radius_px = float(np.mean(dist_px))

    radial_dev_px = np.abs(dist_px - radius_px)
    max_dev_px = float(np.max(radial_dev_px))
    rms_dev_px = float(np.sqrt(np.mean(radial_dev_px**2)))

    max_dev_mm = max_dev_px * mm_per_pixel
    radius_mm = radius_px * mm_per_pixel

    # Check if circle fit is justified (max dev < 8% radius and < 0.5 mm)
    if (max_dev_px / max(radius_px, 1.0) > 0.08) or (max_dev_mm > 0.5):
        return None

    cx_mm = round((cx_px - center_x) * mm_per_pixel, 2)
    cy_mm = round(-(cy_px - center_y) * mm_per_pixel, 2)

    # Generate smooth 36-point circular polygon in mm
    circle_pts_mm: List[Point2D] = []
    num_pts = 36
    for i in range(num_pts):
        angle = 2.0 * math.pi * i / num_pts
        x_mm = round(cx_mm + radius_mm * math.cos(angle), 2)
        y_mm = round(cy_mm + radius_mm * math.sin(angle), 2)
        circle_pts_mm.append(Point2D(x=x_mm, y=y_mm))

    return {
        "is_circle": True,
        "cx_mm": cx_mm,
        "cy_mm": cy_mm,
        "radius_mm": round(radius_mm, 2),
        "circularity": round(circularity, 4),
        "max_dev_mm": round(max_dev_mm, 4),
        "rms_dev_mm": round(rms_dev_px * mm_per_pixel, 4),
        "points": circle_pts_mm,
    }


def point_to_polyline_dist_fast(pts: np.ndarray, poly: np.ndarray) -> Tuple[float, float]:
    """Fast vectorized point to closed polyline distance computation."""
    n_pts = len(pts)
    n_poly = len(poly)
    if n_pts == 0 or n_poly == 0:
        return 0.0, 0.0
    poly_next = np.roll(poly, -1, axis=0)

    seg_vec = poly_next - poly
    seg_len_sq = np.sum(seg_vec**2, axis=1)
    seg_len_sq[seg_len_sq == 0] = 1e-9

    min_dists = np.full(n_pts, np.inf)

    chunk_size = 50
    for i in range(0, n_poly, chunk_size):
        a = poly[i : i + chunk_size]
        v = seg_vec[i : i + chunk_size]
        l2 = seg_len_sq[i : i + chunk_size]

        diff = pts[:, np.newaxis, :] - a[np.newaxis, :, :]
        t = np.sum(diff * v[np.newaxis, :, :], axis=2) / l2[np.newaxis, :]
        t = np.clip(t, 0.0, 1.0)

        proj = a[np.newaxis, :, :] + t[:, :, np.newaxis] * v[np.newaxis, :, :]
        dists = np.linalg.norm(pts[:, np.newaxis, :] - proj, axis=2)

        chunk_min = np.min(dists, axis=1)
        min_dists = np.minimum(min_dists, chunk_min)

    return float(np.max(min_dists)), float(np.mean(min_dists))


def cleanup_image_v2(
    image_bytes: bytes,
    crop_box: Optional[List[float]] = None,
    annotation_regions: Optional[List[Any]] = None,
    guidance: Optional[Dict[str, Any]] = None,
    detail_mode: str = "high_fidelity",
) -> Tuple[bytes, np.ndarray, int, int]:
    """Generate deterministic cleanup image V2 / V3 from input drawing bytes.

    Uses coordinate_normalizer for safe bounding box parsing, protected profile geometry
    masking, crop validation, and non-destructive annotation pixel removal.

    Returns:
        (cleaned_png_bytes, cleaned_binary_mask_np, width, height)
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes for OpenCV cleanup.")

    # Fix EXIF orientation if present
    img = fix_exif_orientation(img, image_bytes)

    # 1. Safer annotation masking & safer crop validation on full source image
    cleaned_bgr, raw_mask, final_crop, crop_rejected, meta = safer_annotation_masking(
        img, annotation_regions, crop_box
    )

    # 2. Crop to validated ROI box (cy1, cx1, cy2, cx2)
    cy1, cx1, cy2, cx2 = final_crop
    cropped = cleaned_bgr[cy1:cy2, cx1:cx2].copy()

    # 3. Detail mode upscaling & edge-preserving preprocessing
    if detail_mode == "high_fidelity":
        scale_factor = 2.0
    elif detail_mode == "balanced":
        scale_factor = 1.5
    else:
        scale_factor = 1.0

    if scale_factor > 1.0:
        target_w = int(round(cropped.shape[1] * scale_factor))
        target_h = int(round(cropped.shape[0] * scale_factor))
        proc_img = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
    else:
        proc_img = cropped.copy()

    ch, cw = proc_img.shape[:2]
    gray = cv2.cvtColor(proc_img, cv2.COLOR_BGR2GRAY)

    # 4. Filtering & Thresholding
    if detail_mode == "high_fidelity":
        filtered = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
    else:
        filtered = cv2.GaussianBlur(gray, (3, 3), 0)

    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Clear outer border edge noise proportional to scale_factor
    border_px = int(math.ceil(3 * scale_factor))
    thresh[0:border_px, :] = 0
    thresh[-border_px:, :] = 0
    thresh[:, 0:border_px] = 0
    thresh[:, -border_px:] = 0

    # 5. Morphological closing to bridge line gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    _, png_buf = cv2.imencode(".png", cleaned)
    cleaned_bytes = png_buf.tobytes()

    return cleaned_bytes, cleaned, cw, ch


def extract_pixel_contours(
    cleaned_mask: np.ndarray,
    scale_calibration: Optional[ScaleCalibration] = None,
    is_complex_expected: bool = True,
    detail_mode: str = "high_fidelity",
) -> Dict[str, Any]:
    """Extract non-convex outer contour, enclosed inner contours, and hierarchy from OpenCV.

    Returns dict containing:
        traced_outer_contour: TracedContour
        traced_hole_contours: List[TracedContour]
        raw_outer_point_count: int
        simplified_outer_point_count: int
        inner_contour_count: int
        scale_calibration: ScaleCalibration
        fidelity_metrics: Dict[str, Any]
        warnings: List[str]
        rejection_reasons: List[str]
    """
    contours, hierarchy = cv2.findContours(cleaned_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    if not contours or hierarchy is None:
        return {
            "success": False,
            "rejection_reasons": ["No valid edge contours found in cleaned image."],
        }

    # Group contours with areas & points
    contour_records = []
    for idx, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        parent = hierarchy[0][idx][3]
        child = hierarchy[0][idx][2]
        contour_records.append(
            {
                "idx": idx,
                "area": area,
                "cnt": cnt,
                "parent": parent,
                "child": child,
                "len": len(cnt),
            }
        )

    contour_records.sort(key=lambda c: c["area"], reverse=True)
    if not contour_records or contour_records[0]["area"] < 10.0:
        return {
            "success": False,
            "rejection_reasons": ["Extracted outer contour area is too small or invalid."],
        }

    outer_rec = contour_records[0]
    outer_idx = outer_rec["idx"]
    outer_cnt = outer_rec["cnt"]
    outer_area = outer_rec["area"]
    raw_outer_count = len(outer_cnt)

    # Outer contour simplification according to detail_mode
    if detail_mode == "high_fidelity":
        adaptive_outer_px = simplify_contour_adaptively(
            outer_cnt, base_eps_ratio=0.0008, min_angle_deg=1.8
        )
    elif detail_mode == "balanced":
        adaptive_outer_px = simplify_contour_adaptively(
            outer_cnt, base_eps_ratio=0.0020, min_angle_deg=2.5
        )
    else:
        perimeter = cv2.arcLength(outer_cnt, True)
        approx = cv2.approxPolyDP(outer_cnt, 0.004 * perimeter, True)
        adaptive_outer_px = approx.reshape(-1, 2).astype(np.float64)

    simplified_outer_count = len(adaptive_outer_px)

    # Bounding box of outer contour in mask pixel space
    x, y, w, h = cv2.boundingRect(outer_cnt)
    bbox_w = max(w, 1.0)
    bbox_h = max(h, 1.0)

    # Determine mm scale conversion factor
    if scale_calibration and scale_calibration.pixel_distance > 0:
        mm_per_pixel = scale_calibration.real_distance_mm / scale_calibration.pixel_distance
    else:
        real_mm = scale_calibration.real_distance_mm if scale_calibration else 40.0
        mm_per_pixel = real_mm / max(bbox_w, bbox_h)
        scale_calibration = ScaleCalibration(
            source="inferred",
            reference_dimension="overall_width",
            pixel_distance=float(max(bbox_w, bbox_h)),
            real_distance_mm=real_mm,
            confidence=0.90,
            confirmed=False,
        )

    center_x = x + bbox_w / 2.0
    center_y = y + bbox_h / 2.0

    def px_pts_to_mm(pts_array: np.ndarray) -> List[Point2D]:
        mm_points = []
        for pt in pts_array:
            if pt.ndim > 1:
                px, py = float(pt[0][0]), float(pt[0][1])
            else:
                px, py = float(pt[0]), float(pt[1])
            mx = round((px - center_x) * mm_per_pixel, 2)
            my = round(-(py - center_y) * mm_per_pixel, 2)
            mm_points.append(Point2D(x=mx, y=my))
        return mm_points

    outer_mm_pts = px_pts_to_mm(adaptive_outer_px)

    # Calculate outer contour fidelity metrics (deviation in mm)
    raw_outer_px = outer_cnt.reshape(-1, 2).astype(np.float64)
    max_dev_px, mean_dev_px = point_to_polyline_dist_fast(raw_outer_px, adaptive_outer_px)
    max_dev_mm = round(max_dev_px * mm_per_pixel, 4)
    mean_dev_mm = round(mean_dev_px * mm_per_pixel, 4)

    warnings: List[str] = []
    rejection_reasons: List[str] = []

    if is_complex_expected and simplified_outer_count == 4:
        rejection_reasons.append(
            "Profile flagged complex requires detailed non-convex perimeter; "
            "4-point bounding box fallback was generated."
        )

    # Rejection check 2: Self-intersection
    if check_self_intersection(outer_mm_pts):
        perimeter = cv2.arcLength(outer_cnt, True)
        fallback_approx = cv2.approxPolyDP(outer_cnt, 0.003 * perimeter, True)
        fallback_mm_pts = px_pts_to_mm(fallback_approx)
        if not check_self_intersection(fallback_mm_pts):
            outer_mm_pts = fallback_mm_pts
            simplified_outer_count = len(fallback_mm_pts)
            warnings.append("Self-intersection detected; applied robust fallback.")
        else:
            rejection_reasons.append("Outer contour intersects itself.")

    # Process inner contours (holes / cutouts)
    inner_contours: List[TracedContour] = []
    min_hole_area = 0.001 * outer_area
    fitted_circles_count = 0

    for rec in contour_records[1:]:
        c_area = rec["area"]
        c_cnt = rec["cnt"]
        parent = rec["parent"]

        if c_area < min_hole_area:
            continue

        p = parent
        is_enclosed = False
        while p != -1:
            if p == outer_idx:
                is_enclosed = True
                break
            p = hierarchy[0][p][3]

        if not is_enclosed:
            continue

        c_perimeter = cv2.arcLength(c_cnt, True)
        if c_perimeter == 0:
            continue

        classification = "hole"
        decision = "include"
        if c_area < 0.002 * outer_area:
            decision = "ignore"
            classification = "noise"

        # Check circle fitting
        circle_fit = (
            fit_circle_if_valid(c_cnt, mm_per_pixel, center_x, center_y)
            if detail_mode != "fast"
            else None
        )
        if circle_fit and decision != "ignore":
            hole_mm_pts = circle_fit["points"]
            fitted_circles_count += 1
            classification = "circle"
        else:
            simp_inner_px = simplify_contour_adaptively(
                c_cnt, base_eps_ratio=0.0012, min_angle_deg=2.0
            )
            if len(simp_inner_px) < 3:
                continue
            hole_mm_pts = px_pts_to_mm(simp_inner_px)
            if len(simp_inner_px) > 35:
                classification = "cavity"

        inner_contours.append(
            TracedContour(
                id=f"region_{len(inner_contours) + 1}",
                points=hole_mm_pts,
                is_closed=True,
                classification=classification,
                decision=decision,
                provenance="opencv_traced",
                confidence=0.95 if circle_fit else 0.92,
            )
        )

    success = len(rejection_reasons) == 0

    traced_outer = TracedContour(
        id="outer_contour",
        points=outer_mm_pts,
        is_closed=True,
        classification="outer_contour",
        provenance="opencv_traced",
        confidence=0.95 if success else 0.50,
    )

    fidelity_metrics = {
        "detail_mode": detail_mode,
        "raw_outer_point_count": raw_outer_count,
        "simplified_outer_point_count": simplified_outer_count,
        "max_deviation_mm": max_dev_mm,
        "mean_deviation_mm": mean_dev_mm,
        "inner_contour_count": len(inner_contours),
        "fitted_circles_count": fitted_circles_count,
        "small_features_preserved": simplified_outer_count > 30,
    }

    return {
        "success": success,
        "traced_outer_contour": traced_outer,
        "traced_hole_contours": inner_contours,
        "raw_outer_point_count": raw_outer_count,
        "simplified_outer_point_count": simplified_outer_count,
        "inner_contour_count": len(inner_contours),
        "scale_calibration": scale_calibration,
        "fidelity_metrics": fidelity_metrics,
        "warnings": warnings,
        "rejection_reasons": rejection_reasons,
    }


def generate_svg_trace_and_overlay(
    outer_contour: TracedContour,
    hole_contours: List[TracedContour],
    original_image_bytes: bytes,
    cleaned_image_bytes: bytes,
    img_w: int = 400,
    img_h: int = 400,
) -> Tuple[str, str, str]:
    """Generate SVG Trace and Real Source Overlay SVG content strings.

    Returns:
        (trace_svg_content, overlay_svg_content, b64_original_image)
    """
    all_pts = list(outer_contour.points)
    for h in hole_contours:
        all_pts.extend(h.points)

    if not all_pts:
        min_x, max_x, min_y, max_y = -20.0, 20.0, -20.0, 20.0
    else:
        min_x = min(p.x for p in all_pts)
        max_x = max(p.x for p in all_pts)
        min_y = min(p.y for p in all_pts)
        max_y = max(p.y for p in all_pts)

    range_x = max_x - min_x or 1.0
    range_y = max_y - min_y or 1.0

    margin = 30
    vw = 400
    vh = 400
    draw_w = vw - margin * 2
    draw_h = vh - margin * 2
    scale = min(draw_w / range_x, draw_h / range_y)

    def to_svg_poly(pts: List[Point2D]) -> str:
        coords = []
        for p in pts:
            sx = margin + (p.x - min_x) * scale
            sy = margin + (max_y - p.y) * scale
            coords.append(f"{sx:.2f},{sy:.2f}")
        return " ".join(coords)

    outer_poly = to_svg_poly(outer_contour.points)

    # 1. Generate Clean Standalone SVG Trace
    holes_svg_elements = []
    for h in hole_contours:
        poly_str = to_svg_poly(h.points)
        stroke = "#00e676"  # included opening: green/cyan
        fill = "rgba(0, 230, 118, 0.25)"
        dash = ""
        if h.classification == "circle":
            stroke = "#76ff03"  # fitted circle: bright lime green
            fill = "rgba(118, 255, 3, 0.30)"
        elif h.decision == "ignore":
            stroke = "#ff9100"  # ignored region: orange
            fill = "rgba(255, 145, 0, 0.20)"
            dash = ' stroke-dasharray="4 2"'
        elif h.decision == "unsure":
            stroke = "#d500f9"  # uncertain contour: purple
            fill = "rgba(213, 0, 249, 0.20)"
            dash = ' stroke-dasharray="3 3"'

        holes_svg_elements.append(
            f'  <polygon points="{poly_str}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.8"{dash} data-feature-id="{h.id}" />'
        )

    holes_rendered = "\n".join(holes_svg_elements)

    trace_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
        f'width="100%" height="100%" aria-label="OpenCV Vector Profile Trace">\n'
        f'  <rect width="{vw}" height="{vh}" fill="#0d1117" rx="6" />\n'
        f'  <polygon points="{outer_poly}" fill="rgba(0, 229, 255, 0.20)" '
        f'stroke="#00e5ff" stroke-width="2.5" data-feature-id="outer_contour" />\n'
        f"{holes_rendered}\n"
        f'  <g transform="translate(12, {vh - 20})">\n'
        f'    <rect x="0" y="0" width="10" height="4" fill="#00e5ff" rx="1" />\n'
        f'    <text x="14" y="5" fill="#8b949e" font-size="9">Outer boundary</text>\n'
        f'    <rect x="95" y="0" width="10" height="4" fill="#00e676" rx="1" />\n'
        f'    <text x="109" y="5" fill="#8b949e" font-size="9">Included opening</text>\n'
        f'    <rect x="195" y="0" width="10" height="4" fill="#76ff03" rx="1" />\n'
        f'    <text x="209" y="5" fill="#8b949e" font-size="9">Fitted circle</text>\n'
        f'    <rect x="275" y="0" width="10" height="4" fill="#ff9100" rx="1" />\n'
        f'    <text x="289" y="5" fill="#8b949e" font-size="9">Ignored region</text>\n'
        f"  </g>\n"
        f"</svg>"
    )

    # 2. Generate Real Source Image Overlay SVG
    b64_orig = base64.b64encode(original_image_bytes).decode("ascii")
    img_mime = "image/jpeg"
    if original_image_bytes.startswith(b"\x89PNG"):
        img_mime = "image/png"

    overlay_svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" '
        f'width="100%" height="100%" aria-label="Real Source Image Profile Overlay">\n'
        f'  <image href="data:{img_mime};base64,{b64_orig}" width="{vw}" height="{vh}" '
        f'preserveAspectRatio="xMidYMid meet" opacity="0.65" />\n'
        f'  <polygon points="{outer_poly}" fill="rgba(0, 229, 255, 0.25)" '
        f'stroke="#00e5ff" stroke-width="2.5" />\n'
        f"{holes_rendered}\n"
        f"</svg>"
    )

    return trace_svg, overlay_svg, b64_orig
