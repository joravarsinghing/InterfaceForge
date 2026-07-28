"""S10.5C Comparison Script — Compare Dimensioned vs Clean Profile Inputs.

Tests three profile input routes:
Route 1: Dimensioned image (interface_b_original.jpg) directly -> OpenCV trace
Route 2: Dimensioned image (interface_b_original.jpg) -> Gemini cleanup -> OpenCV trace
Route 3: Already-clean shaded profile (interface_a_original.jpg) -> OpenCV trace
"""

import os
import cv2
import numpy as np
from app.services.opencv_tracer import (
    cleanup_image_v2,
    extract_pixel_contours,
    generate_svg_trace_and_overlay,
)

def run_pipeline_for_image(
    source_img_path: str,
    overlay_source_path: str,
    route_name: str,
    cleaned_out_path: str,
    trace_svg_out_path: str,
    overlay_svg_out_path: str,
):
    with open(source_img_path, "rb") as f:
        src_bytes = f.read()

    with open(overlay_source_path, "rb") as f:
        overlay_src_bytes = f.read()

    # 1. Cleanup / Preprocessing
    cleaned_bytes, cleaned_mask, w, h = cleanup_image_v2(src_bytes)

    with open(cleaned_out_path, "wb") as f:
        f.write(cleaned_bytes)

    # 2. OpenCV Contour Extraction
    trace_res = extract_pixel_contours(cleaned_mask, is_complex_expected=True)

    success = trace_res.get("success", False)
    outer_contour = trace_res.get("traced_outer_contour")
    hole_contours = trace_res.get("traced_hole_contours", [])
    raw_outer_cnt = trace_res.get("raw_outer_point_count", 0)
    simp_outer_cnt = trace_res.get("simplified_outer_point_count", 0)
    inner_cnt = trace_res.get("inner_contour_count", 0)
    rejection_reasons = trace_res.get("rejection_reasons", [])
    warnings = trace_res.get("warnings", [])

    print(f"=== {route_name} ===")
    print(f"  Success: {success}")
    print(f"  Raw outer point count: {raw_outer_cnt}")
    print(f"  Simplified outer point count: {simp_outer_cnt}")
    print(f"  Inner contour count: {inner_cnt}")
    if rejection_reasons:
        print(f"  Rejection reasons: {rejection_reasons}")
    if warnings:
        print(f"  Warnings: {warnings}")

    # 3. SVG Trace and Overlay Generation
    if outer_contour:
        trace_svg, overlay_svg, _ = generate_svg_trace_and_overlay(
            outer_contour=outer_contour,
            hole_contours=hole_contours,
            original_image_bytes=overlay_src_bytes,
            cleaned_image_bytes=cleaned_bytes,
            img_w=w,
            img_h=h,
        )

        with open(trace_svg_out_path, "w", encoding="utf-8") as f:
            f.write(trace_svg)

        with open(overlay_svg_out_path, "w", encoding="utf-8") as f:
            f.write(overlay_svg)

    return {
        "route_name": route_name,
        "success": success,
        "raw_outer_point_count": raw_outer_cnt,
        "simplified_outer_point_count": simp_outer_cnt,
        "inner_contour_count": inner_cnt,
        "rejection_reasons": rejection_reasons,
        "warnings": warnings,
        "hole_details": [
            {
                "id": h.id,
                "points_len": len(h.points),
                "classification": h.classification,
                "decision": h.decision,
            }
            for h in hole_contours
        ],
    }

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    artifacts_dir = os.path.join(repo_root, "artifacts")
    samples_dir = os.path.join(repo_root, "samples", "manual_qa")

    img_a = os.path.join(samples_dir, "interface_a_original.jpg")
    img_b = os.path.join(samples_dir, "interface_b_original.jpg")
    gemini_b = r"C:\Users\jvsin\.gemini\antigravity-cli\brain\9489b6a8-1d50-452a-95dd-5ec1525a2f41\gemini_cleaned_b_1785226046092.jpg"

    # Route 1: Dimensioned image directly
    r1 = run_pipeline_for_image(
        source_img_path=img_b,
        overlay_source_path=img_b,
        route_name="Route 1: Dimensioned Direct (interface_b_original.jpg)",
        cleaned_out_path=os.path.join(artifacts_dir, "s10_5c_route1_cleaned.png"),
        trace_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route1_trace.svg"),
        overlay_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route1_overlay.svg"),
    )

    # Route 2: Dimensioned image after Gemini cleanup
    # Also save Gemini cleaned image copy into artifacts for documentation
    gemini_cleaned_artifact_path = os.path.join(artifacts_dir, "s10_5c_route2_gemini_cleaned.jpg")
    with open(gemini_b, "rb") as f_in, open(gemini_cleaned_artifact_path, "wb") as f_out:
        f_out.write(f_in.read())

    r2 = run_pipeline_for_image(
        source_img_path=gemini_cleaned_artifact_path,
        overlay_source_path=img_b,  # overlay on real source image to evaluate true fidelity
        route_name="Route 2: Gemini Cleaned (interface_b_original.jpg -> Gemini -> OpenCV)",
        cleaned_out_path=os.path.join(artifacts_dir, "s10_5c_route2_opencv_cleaned.png"),
        trace_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route2_trace.svg"),
        overlay_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route2_overlay.svg"),
    )

    run_pipeline_for_image(
        source_img_path=gemini_cleaned_artifact_path,
        overlay_source_path=gemini_cleaned_artifact_path,
        route_name="Route 2 (on Gemini source): Gemini Cleaned Overlay",
        cleaned_out_path=os.path.join(artifacts_dir, "s10_5c_route2_opencv_cleaned_temp.png"),
        trace_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route2_trace_temp.svg"),
        overlay_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route2_overlay_on_gemini.svg"),
    )

    # Route 3: Already-clean shaded image
    r3 = run_pipeline_for_image(
        source_img_path=img_a,
        overlay_source_path=img_a,
        route_name="Route 3: Clean Shaded Profile Direct (interface_a_original.jpg)",
        cleaned_out_path=os.path.join(artifacts_dir, "s10_5c_route3_cleaned.png"),
        trace_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route3_trace.svg"),
        overlay_svg_out_path=os.path.join(artifacts_dir, "s10_5c_route3_overlay.svg"),
    )

if __name__ == "__main__":
    main()
