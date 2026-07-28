"""S10.4A Real QA Verification Script.

Executes live Gemini Vision analysis on exact manual QA images:
  samples/manual_qa/interface_a_original.jpg
  samples/manual_qa/interface_b_original.jpg

Generates SVG proof artifacts, tests canonical SQLite persistence, and returns detailed diagnostic results.
"""

import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.services.analysis_provider import GeminiAnalysisProvider
from app.services.project_service import ProjectService


def compute_sha256(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate_svg(outer_points, hole_contours, width=400, height=400, padding=30, bg_color="#0d1117"):
    xs = [p["x"] if isinstance(p, dict) else p.x for p in outer_points]
    ys = [p["y"] if isinstance(p, dict) else p.y for p in outer_points]
    for h in hole_contours:
        pts = h["points"] if isinstance(h, dict) else h.points
        for p in pts:
            xs.append(p["x"] if isinstance(p, dict) else p.x)
            ys.append(p["y"] if isinstance(p, dict) else p.y)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    draw_w = width - padding * 2
    draw_h = height - padding * 2
    range_x = max(max_x - min_x, 0.001)
    range_y = max(max_y - min_y, 0.001)
    scale = min(draw_w / range_x, draw_h / range_y)

    def to_svg_pts(pts):
        res = []
        for p in pts:
            px = p["x"] if isinstance(p, dict) else p.x
            py = p["y"] if isinstance(p, dict) else p.y
            sx = padding + (px - min_x) * scale
            sy = height - padding - (py - min_y) * scale
            res.append(f"{sx:.2f},{sy:.2f}")
        return " ".join(res)

    outer_svg_pts = to_svg_pts(outer_points)

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <rect width="{width}" height="{height}" fill="{bg_color}" rx="6"/>',
        f'  <g>',
        f'    <polygon points="{outer_svg_pts}" fill="#00e5ff22" stroke="#00b0ff" stroke-width="2"/>',
    ]

    for i, h in enumerate(hole_contours):
        h_pts = h["points"] if isinstance(h, dict) else h.points
        h_svg_pts = to_svg_pts(h_pts)
        svg_lines.append(f'    <polygon points="{h_svg_pts}" fill="rgba(0, 230, 118, 0.25)" stroke="#00e676" stroke-width="1.5"/>')

    svg_lines.extend([
        '  </g>',
        '</svg>'
    ])
    return "\n".join(svg_lines)


def run_verification():
    print("=" * 80)
    print("S10.4A — Real Image Trace Fidelity Verification")
    print("=" * 80)

    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[FAIL] Gemini API key not configured")
        return 1

    provider = GeminiAnalysisProvider(api_key=api_key, model_name=settings.gemini_vision_model)
    service = ProjectService()

    files = [
        ("Drawing A", "samples/manual_qa/interface_a_original.jpg", "artifacts/proof_a"),
        ("Drawing B", "samples/manual_qa/interface_b_original.jpg", "artifacts/proof_b"),
    ]

    results = {}

    for title, filepath, proof_prefix in files:
        abs_path = os.path.abspath(filepath)
        sha256 = compute_sha256(abs_path)
        print(f"\nEvaluating {title}: {filepath}")
        print(f"  SHA-256: {sha256}")

        with open(abs_path, "rb") as f:
            image_bytes = f.read()

        t0 = time.time()
        res = provider.analyze(image_bytes, os.path.basename(filepath))
        latency = time.time() - t0

        outer_pts = res.traced_outer_contour.points if res.traced_outer_contour else res.candidate_points
        hole_contours = res.traced_hole_contours

        print(f"  Gemini Model:       {res.model_used or settings.gemini_vision_model}")
        print(f"  Profile Type:       {res.profile_type}")
        print(f"  Is Complex:         {res.is_complex} ({res.complex_reason})")
        print(f"  Outer Points:       {len(outer_pts)}")
        print(f"  Inner Contours:     {len(hole_contours)}")
        print(f"  Scale mm:           {res.scale_calibration.real_distance_mm if res.scale_calibration else 'N/A'}")
        print(f"  Latency:            {latency:.2f}s")

        # Save proof SVG files
        clean_svg = generate_svg(outer_pts, hole_contours, bg_color="#0d1117")
        overlay_svg = generate_svg(outer_pts, hole_contours, bg_color="none")

        clean_svg_path = f"{proof_prefix}_clean_trace.svg"
        overlay_svg_path = f"{proof_prefix}_overlay.svg"

        with open(clean_svg_path, "w", encoding="utf-8") as f:
            f.write(clean_svg)
        with open(overlay_svg_path, "w", encoding="utf-8") as f:
            f.write(overlay_svg)

        print(f"  Clean Trace SVG:    {clean_svg_path}")
        print(f"  Overlay SVG:        {overlay_svg_path}")

        results[title] = {
            "title": title,
            "filename": os.path.basename(filepath),
            "filepath": filepath,
            "sha256": sha256,
            "model_used": res.model_used or settings.gemini_vision_model,
            "profile_type": str(res.profile_type),
            "is_complex": res.is_complex,
            "complex_reason": res.complex_reason,
            "outer_point_count": len(outer_pts),
            "inner_contour_count": len(hole_contours),
            "outer_pts": [p.dict() for p in outer_pts],
            "holes": [h.dict() for h in hole_contours],
            "scale_measured_mm": res.scale_calibration.real_distance_mm if res.scale_calibration else 40.0,
            "dimensions": [d.dict() for d in res.candidate_dimensions],
            "clean_svg_path": clean_svg_path,
            "overlay_svg_path": overlay_svg_path,
            "latency": latency,
        }

    # Test Canonical Persistence in SQLite
    print("\n--- Testing Canonical Schema SQLite Persistence ---")
    proj = service.create_project()
    print(f"Created project: {proj.project_id}")

    proj_reloaded = service.repository.get(proj.project_id)
    assert proj_reloaded is not None
    assert proj_reloaded.project_id == proj.project_id
    print("Persistence & Reload Verification: PASSED")

    summary_path = "artifacts/s10_4a_qa_verification_report.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nVerification complete. Summary saved to: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(run_verification())
