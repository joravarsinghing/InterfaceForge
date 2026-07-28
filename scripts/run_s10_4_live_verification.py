"""Live verification script for S10.4 Exact Complex Profile Tracing with Gemini Vision Provider."""

import json
import os
import sys
import time

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.services.analysis_provider import GeminiAnalysisProvider, MockAnalysisProvider


def run_live_s10_4_verification() -> int:
    print("=" * 75)
    print("InterfaceForge — S10.4 Live Gemini Vision Verification Suite")
    print("=" * 75)

    api_key = (
        settings.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        print("[ERROR] No GEMINI_API_KEY or GOOGLE_API_KEY configured.")
        return 1

    provider = GeminiAnalysisProvider(
        api_key=api_key,
        model_name=settings.gemini_vision_model,
        fallback_model_name=settings.gemini_vision_fallback_model,
        fallback_enabled=True,
    )

    fixtures_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "samples", "s10_fixtures")
    )
    fixtures = [
        ("Drawing A (40x40 mm T-Slot Extrusion)", "drawing_a_2040_t_slot.png"),
        ("Drawing B (30x30 mm Profile)", "drawing_b_3030_profile.png"),
    ]

    reports = []

    for title, filename in fixtures:
        filepath = os.path.join(fixtures_dir, filename)
        if not os.path.exists(filepath):
            print(f"[MISSING] Fixture file not found: {filename}")
            continue

        with open(filepath, "rb") as f:
            image_bytes = f.read()

        print(f"\n--- Analyzing {title} ({filename}) ---")
        start_time = time.time()

        try:
            res = provider.analyze(image_bytes, filename)
            latency = time.time() - start_time

            report = {
                "title": title,
                "filename": filename,
                "provider_used": res.analysis_provider_name or "gemini",
                "model_used": res.model_used or provider.model_name,
                "profile_type": res.profile_type.value if hasattr(res.profile_type, "value") else str(res.profile_type),
                "is_complex": res.is_complex,
                "complex_reason": res.complex_reason,
                "confidence": res.confidence,
                "outer_point_count": len(res.traced_outer_contour.points) if res.traced_outer_contour else len(res.candidate_points),
                "inner_region_count": len(res.traced_hole_contours),
                "scale_source": res.scale_calibration.source if res.scale_calibration else "inferred",
                "scale_measured_mm": res.scale_calibration.real_distance_mm if res.scale_calibration else 40.0,
                "dimensions_count": len(res.candidate_dimensions),
                "dimensions": [
                    {
                        "label": d.label,
                        "value": d.value,
                        "unit": d.unit,
                        "feature_ref": d.feature_ref,
                        "source_annotation": d.source_annotation,
                    }
                    for d in res.candidate_dimensions
                ],
                "latency_seconds": round(latency, 2),
            }

            reports.append(report)

            print(f"  Provider Used:        {report['provider_used']} ({report['model_used']})")
            print(f"  Profile Type:         {report['profile_type']}")
            print(f"  Is Complex:           {report['is_complex']} ({report['complex_reason']})")
            print(f"  Outer Points:         {report['outer_point_count']}")
            print(f"  Inner Regions:        {report['inner_region_count']}")
            print(f"  Scale Measured:       {report['scale_measured_mm']} mm (Source: {report['scale_source']})")
            print(f"  Extracted Dimensions: {report['dimensions_count']}")
            for d in report['dimensions']:
                print(f"    - {d['label']}: {d['value']} {d['unit']} (Ref: {d['feature_ref']}, Source: {d['source_annotation']})")

        except Exception as exc:
            print(f"  [FAIL] Analysis failed for {filename}: {exc}")
            return 1

    summary_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "artifacts", "s10_4_live_verification_report.json")
    )
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2)

    print("\n" + "=" * 75)
    print(f"S10.4 Live Verification Complete. Report saved to: {summary_file}")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(run_live_s10_4_verification())
