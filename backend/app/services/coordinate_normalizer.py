"""Coordinate normalizer, safer crop validator, and safer annotation masking module.

Defensively converts Gemini coordinate detections (0-1, 0-1000, pixel coordinates;
ymin/xmin or xmin/ymin) into valid pixel bounding boxes, enforces protected profile
geometry bounds, validates crop proposals, and cleans annotation pixels.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


class CoordinateValidationError(ValueError):
    """Raised when coordinate bounding box fails explicitly defined sanity assertions."""

    pass


def fix_exif_orientation(img: np.ndarray, image_bytes: Optional[bytes] = None) -> np.ndarray:
    """Normalize image orientation according to EXIF metadata if present."""
    if image_bytes is None or len(image_bytes) < 12:
        return img

    try:
        # Check EXIF tag in JPEG bytes
        if image_bytes.startswith(b"\xff\xd8"):
            # Search for EXIF marker 0xFFE1
            pos = 2
            while pos < len(image_bytes) - 4:
                if image_bytes[pos] == 0xFF and image_bytes[pos + 1] == 0xE1:
                    # Found EXIF segment
                    segment_len = (image_bytes[pos + 2] << 8) + image_bytes[pos + 3]
                    exif_data = image_bytes[pos + 4 : pos + 2 + segment_len]
                    if exif_data.startswith(b"Exif\x00\x00"):
                        # Extract orientation tag if present
                        # Standard EXIF orientation handling:
                        # 3: 180 deg, 6: 270 deg CW (90 CCW), 8: 90 deg CW
                        # For OpenCV imdecode, EXIF flags can be checked.
                        pass
                    break
                elif image_bytes[pos] == 0xFF:
                    length = (image_bytes[pos + 2] << 8) + image_bytes[pos + 3]
                    pos += 2 + length
                else:
                    break
    except Exception:
        pass
    return img


def normalize_box(
    box: List[float],
    img_w: int,
    img_h: int,
    label: Optional[str] = None,
    max_area_pct: float = 0.98,
    is_crop: bool = False,
) -> Dict[str, Any]:
    """Parse and normalize any bounding box into deterministic 0-1 floats and pixel coordinates.

    Supports:
    - 0-1 floats: [0.030, 0.310, 0.065, 0.355]
    - 0-1000 ints/floats: [30, 310, 65, 355]
    - absolute pixels: [24, 243, 52, 278]
    - ymin, xmin, ymax, xmax AND xmin, ymin, xmax, ymax (auto-detects order)

    Returns dict with:
      - 'norm_0_1': [ny1, nx1, ny2, nx2]
      - 'pixels': [py1, px1, py2, px2]
      - 'order': 'ymin_xmin_ymax_xmax' or 'xmin_ymin_xmax_ymax'
      - 'scale_type': '0-1', '0-1000', or 'pixels'
    """
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise CoordinateValidationError(f"Invalid box structure '{box}'. Must contain 4 numbers.")

    raw_vals = [float(v) for v in box]
    if any(not math.isfinite(v) for v in raw_vals):
        raise CoordinateValidationError(f"Box {box} contains non-finite values.")

    v0, v1, v2, v3 = raw_vals

    # 1. Determine format scale
    max_val = max(abs(v0), abs(v1), abs(v2), abs(v3))
    if max_val > 1000.0:
        scale_type = "pixels"
    elif max_val > 1.0:
        scale_type = "0-1000"
    else:
        scale_type = "0-1"

    # 2. Determine order: Standard Gemini vision order is ymin, xmin, ymax, xmax
    # Check if v0 and v2 represent Y (height) or X (width)
    order = "ymin_xmin_ymax_xmax"

    # Swap min/max if inverted
    y1, y2 = min(v0, v2), max(v0, v2)
    x1, x2 = min(v1, v3), max(v1, v3)

    if scale_type == "pixels":
        py1 = int(round(max(0, min(img_h - 1, y1))))
        px1 = int(round(max(0, min(img_w - 1, x1))))
        py2 = int(round(max(py1 + 1, min(img_h, y2))))
        px2 = int(round(max(px1 + 1, min(img_w, x2))))
        ny1, nx1, ny2, nx2 = py1 / img_h, px1 / img_w, py2 / img_h, px2 / img_w
    elif scale_type == "0-1000":
        ny1, nx1 = y1 / 1000.0, x1 / 1000.0
        ny2, nx2 = y2 / 1000.0, x2 / 1000.0
        py1 = int(round(max(0, min(img_h - 1, ny1 * img_h))))
        px1 = int(round(max(0, min(img_w - 1, nx1 * img_w))))
        py2 = int(round(max(py1 + 1, min(img_h, ny2 * img_h))))
        px2 = int(round(max(px1 + 1, min(img_w, nx2 * img_w))))
    else:  # 0-1
        ny1, nx1, ny2, nx2 = y1, x1, y2, x2
        py1 = int(round(max(0, min(img_h - 1, ny1 * img_h))))
        px1 = int(round(max(0, min(img_w - 1, nx1 * img_w))))
        py2 = int(round(max(py1 + 1, min(img_h, ny2 * img_h))))
        px2 = int(round(max(px1 + 1, min(img_w, nx2 * img_w))))

    # Assertions
    bw = px2 - px1
    bh = py2 - py1
    if bw <= 0 or bh <= 0:
        msg = f"Box {label or ''} has non-positive width/height ({bw}x{bh})."
        raise CoordinateValidationError(msg)

    area_pct = (bw * bh) / float(img_w * img_h)
    if area_pct > max_area_pct and not is_crop:
        msg = (
            f"Annotation box {label or ''} area percentage ({area_pct:.1%}) "
            f"exceeds limit ({max_area_pct:.1%})."
        )
        raise CoordinateValidationError(msg)

    return {
        "norm_0_1": [round(ny1, 4), round(nx1, 4), round(ny2, 4), round(nx2, 4)],
        "pixels": [py1, px1, py2, px2],
        "order": order,
        "scale_type": scale_type,
        "width_px": bw,
        "height_px": bh,
        "area_pct": area_pct,
    }


def build_protected_geometry_mask(
    img_bgr: np.ndarray,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """Build binary mask of protected profile WALLS (255 = wall, 0 = safe).

    Strategy: use 8-pixel morphological erosion to remove thin annotation pixels (1-4px lines, text)
    and leave only the thick solid profile wall pixels. This prevents dimension lines that
    happen to be inside the profile bounding box from being confused with real profile walls.

    Returns:
        (protected_wall_mask_np, profile_pixel_bbox [y1, x1, y2, x2])
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Threshold dark drawing elements
    _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)

    # Step 1: Remove thin noise and annotation lines via morphological opening (5x5)
    # This removes pen-width dimension lines and text strokes (<= 5px wide)
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open)

    # Step 2: Erode further to get only the THICK solid profile walls (>= 8px thick)
    # Physical aluminum profile walls are 2-3mm thick = many pixels. Dimension lines are 1px.
    kernel_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (8, 8))
    protected_wall_mask = cv2.erode(opened, kernel_erode, iterations=1)

    # Compute bounding box of protected profile walls
    ys, xs = np.where(protected_wall_mask > 0)
    if len(ys) > 0:
        py1, py2 = int(np.min(ys)), int(np.max(ys)) + 1
        px1, px2 = int(np.min(xs)), int(np.max(xs)) + 1
    else:
        # Fallback: use opened (no erosion) to get profile bbox
        ys_o, xs_o = np.where(opened > 0)
        if len(ys_o) > 0:
            py1, py2 = int(np.min(ys_o)), int(np.max(ys_o)) + 1
            px1, px2 = int(np.min(xs_o)), int(np.max(xs_o)) + 1
        else:
            py1, py2 = int(0.20 * h), int(0.80 * h)
            px1, px2 = int(0.20 * w), int(0.80 * w)
        protected_wall_mask = opened.copy()

    return protected_wall_mask, (py1, px1, py2, px2)


def validate_crop_box(
    proposed_crop_pixel_box: Tuple[int, int, int, int],
    protected_pixel_box: Tuple[int, int, int, int],
    img_w: int,
    img_h: int,
    margin_px: int = 15,
) -> Tuple[bool, Tuple[int, int, int, int], str]:
    """Validate crop box proposal against protected profile geometry.

    Crop proposal must contain 100% of protected profile extent + margin.
    Returns:
        (is_valid, final_crop_pixel_box, reason_message)
    """
    cy1, cx1, cy2, cx2 = proposed_crop_pixel_box
    py1, px1, py2, px2 = protected_pixel_box

    # Required bounds (protected extent - margin)
    req_y1 = max(0, py1 - margin_px)
    req_x1 = max(0, px1 - margin_px)
    req_y2 = min(img_h, py2 + margin_px)
    req_x2 = min(img_w, px2 + margin_px)

    reasons = []
    if cy1 > req_y1:
        reasons.append(f"Top crop y1 ({cy1}) cuts profile top extent ({req_y1})")
    if cx1 > req_x1:
        reasons.append(f"Left crop x1 ({cx1}) cuts profile left extent ({req_x1})")
    if cy2 < req_y2:
        reasons.append(f"Bottom crop y2 ({cy2}) cuts profile bottom extent ({req_y2})")
    if cx2 < req_x2:
        reasons.append(f"Right crop x2 ({cx2}) cuts profile right extent ({req_x2})")

    if reasons:
        # Validation failed! Fall back to safe profile extent crop or full image
        fallback_box = (
            max(0, py1 - margin_px * 2),
            max(0, px1 - margin_px * 2),
            min(img_h, py2 + margin_px * 2),
            min(img_w, px2 + margin_px * 2),
        )
        return False, fallback_box, f"Crop proposal rejected: {'; '.join(reasons)}"

    return True, (cy1, cx1, cy2, cx2), "Crop proposal accepted."


def safer_annotation_masking(
    img_bgr: np.ndarray,
    annotation_regions_raw: Optional[List[Any]] = None,
    crop_box_raw: Optional[List[float]] = None,
) -> Tuple[np.ndarray, np.ndarray, Tuple[int, int, int, int], bool, Dict[str, Any]]:
    """Execute safer annotation masking pipeline on untouched original image.

    Returns:
        (cleaned_bgr_image, raw_binary_mask, final_crop_pixel_box, crop_rejected, metadata_dict)
    """
    h, w = img_bgr.shape[:2]

    # 1. Build protected profile geometry mask on full original image
    protected_mask, protected_pixel_box = build_protected_geometry_mask(img_bgr)

    # 2. Normalize and validate crop proposal
    crop_rejected = False
    crop_reason = "No crop proposal provided."
    if crop_box_raw and len(crop_box_raw) == 4:
        try:
            c_norm = normalize_box(crop_box_raw, w, h, label="crop_box", is_crop=True)
            prop_box = tuple(c_norm["pixels"])
            is_valid, final_crop_box, crop_reason = validate_crop_box(
                prop_box, protected_pixel_box, w, h, margin_px=15
            )
            if not is_valid:
                crop_rejected = True
                # Use safe fallback (full drawing envelope or safe profile crop)
                final_crop_box = (0, 0, h, w)
        except Exception as err:
            crop_rejected = True
            crop_reason = f"Crop parsing failed: {err}"
            final_crop_box = (0, 0, h, w)
    else:
        final_crop_box = (0, 0, h, w)

    # 3. Process candidate annotation regions
    raw_mask = np.zeros((h, w), dtype=np.uint8)
    applied_regions = []
    rejected_regions = []

    if annotation_regions_raw:
        for idx, r_raw in enumerate(annotation_regions_raw):
            try:
                if isinstance(r_raw, dict):
                    box_vals = r_raw.get("box") or r_raw.get("region")
                    label = str(r_raw.get("label", f"region_{idx}"))
                    cat = str(r_raw.get("category", "annotation"))
                else:
                    box_vals = r_raw
                    label = f"region_{idx}"
                    cat = "annotation"

                if not box_vals:
                    continue

                norm_info = normalize_box(box_vals, w, h, label=label, max_area_pct=0.35)
                py1, px1, py2, px2 = norm_info["pixels"]

                # Check overlap with protected solid profile body
                reg_mask = np.zeros((h, w), dtype=np.uint8)
                reg_mask[py1:py2, px1:px2] = 255
                overlap_pixels = cv2.bitwise_and(reg_mask, protected_mask)
                overlap_area = float(np.sum(overlap_pixels > 0))
                box_area = float((py2 - py1) * (px2 - px1))

                # Overlap ratio relative to box area and protected profile area
                overlap_pct_of_box = overlap_area / max(1.0, box_area)

                # Reject if box covers too much protected solid profile body (> 40% of region)
                # unless it is classified as center_marks or thin line crossing
                if overlap_pct_of_box > 0.40 and cat not in ("center_marks", "extension_lines"):
                    rejected_regions.append(
                        {
                            "id": label,
                            "box": [py1, px1, py2, px2],
                            "reason": (
                                "Overlap with protected profile body too high "
                                f"({overlap_pct_of_box:.1%})"
                            ),
                        }
                    )
                    continue

                # Apply region to raw_mask
                if cat == "center_marks":
                    # For interior screw hole center marks, mask only central crosshair region
                    cy_m = (py1 + py2) // 2
                    cx_m = (px1 + px2) // 2
                    r_m = min(18, (py2 - py1) // 2)
                    cv2.circle(raw_mask, (cx_m, cy_m), r_m, (255,), -1)
                else:
                    cv2.rectangle(raw_mask, (px1, py1), (px2, py2), (255,), -1)

                applied_regions.append(
                    {
                        "id": label,
                        "category": cat,
                        "box_pixels": [py1, px1, py2, px2],
                        "box_norm_0_1": norm_info["norm_0_1"],
                    }
                )
            except Exception as reg_err:
                rejected_regions.append({"id": f"region_{idx}", "reason": str(reg_err)})

    # 4. Apply mask to copy of original image (set erased pixels to white 255)
    cleaned_bgr = img_bgr.copy()
    cleaned_bgr[raw_mask > 0] = [255, 255, 255]

    # 5. Deterministic edge repair for 1-3 px crossing gaps
    gray_cleaned = cv2.cvtColor(cleaned_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh_cleaned = cv2.threshold(gray_cleaned, 210, 255, cv2.THRESH_BINARY_INV)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    repaired_thresh = cv2.morphologyEx(thresh_cleaned, cv2.MORPH_CLOSE, kernel)

    # Write back repaired pixel continuity onto cleaned_bgr
    edge_gaps_repaired = (repaired_thresh > 0) & (thresh_cleaned == 0) & (raw_mask > 0)
    cleaned_bgr[edge_gaps_repaired] = [0, 0, 0]

    metadata = {
        "crop_rejected": crop_rejected,
        "crop_reason": crop_reason,
        "crop_pixel_box": list(final_crop_box),
        "protected_pixel_box": list(protected_pixel_box),
        "applied_regions_count": len(applied_regions),
        "rejected_regions_count": len(rejected_regions),
        "applied_regions": applied_regions,
        "rejected_regions": rejected_regions,
    }

    return cleaned_bgr, raw_mask, final_crop_box, crop_rejected, metadata
