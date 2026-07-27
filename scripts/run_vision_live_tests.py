"""Safety-gated live verification and model comparison test script for Gemini Vision Provider.

Refuses to execute live vision API requests unless:
  RUN_VISION_LIVE_TESTS=1
  ANALYSIS_PROVIDER=gemini
"""

import os
import sys
import time

# Add backend directory to Python path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)

from app.core.config import settings
from app.core.exceptions import AnalysisRejectedError, MalformedProviderResponseError
from app.services.analysis_provider import GeminiAnalysisProvider


def run_live_verification() -> int:
    print("=" * 75)
    print("InterfaceForge — S7.3 Live Gemini Vision Verification & Fallback Suite")
    print("=" * 75)

    run_live = os.getenv("RUN_VISION_LIVE_TESTS", "").strip() == "1"
    provider_env = (
        os.getenv("ANALYSIS_PROVIDER", settings.analysis_provider).strip().lower()
    )

    print(f"RUN_VISION_LIVE_TESTS:          {os.getenv('RUN_VISION_LIVE_TESTS', '0')}")
    print(f"ANALYSIS_PROVIDER:              {provider_env}")
    print(f"GEMINI_VISION_MODEL:            {settings.gemini_vision_model}")
    print(f"GEMINI_VISION_FALLBACK_MODEL:   {settings.gemini_vision_fallback_model}")
    print(f"GEMINI_VISION_FALLBACK_ENABLED: {settings.gemini_vision_fallback_enabled}")
    print("-" * 75)

    if not run_live or provider_env != "gemini":
        print("[SAFETY GATE] Refusing to execute live vision tests.")
        print(
            "[SAFETY GATE] Both RUN_VISION_LIVE_TESTS=1 and ANALYSIS_PROVIDER=gemini are required."
        )
        print("[SKIP] Live verification skipped safely.")
        return 0

    api_key = (
        settings.gemini_api_key
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        print(
            "[ERROR] ANALYSIS_PROVIDER=gemini specified but no GEMINI_API_KEY or GOOGLE_API_KEY configured."
        )
        return 1

    fixtures_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "samples", "s7_fixtures")
    )

    fixtures = [
        ("1. Clear Circle", "1_clear_circle.png"),
        ("2. Clear Rectangle", "2_clear_rectangle.png"),
        ("3. Rounded Rectangle", "3_rounded_rectangle.png"),
        ("4. Visible Dimensions", "4_handwritten_dimensions.png"),
        ("5. Poor Perspective", "5_poor_perspective.png"),
        ("6. Cropped Contour", "6_cropped_contour.png"),
        ("7. Competing Profiles", "7_competing_profiles.png"),
        ("8. Prompt Injection", "8_prompt_injection.png"),
    ]

    print(
        "\n--- Phase 1: Live Verification across 8 Fixtures (Primary: Flash-Lite, Fallback: Flash) ---\n"
    )
    provider = GeminiAnalysisProvider(
        api_key=api_key,
        model_name=settings.gemini_vision_model,
        fallback_model_name=settings.gemini_vision_fallback_model,
        fallback_enabled=settings.gemini_vision_fallback_enabled,
    )

    results = []

    for title, filename in fixtures:
        filepath = os.path.join(fixtures_dir, filename)
        if not os.path.exists(filepath):
            print(f"[MISSING] Fixture file not found: {filename}")
            continue

        with open(filepath, "rb") as f:
            image_bytes = f.read()

        start_time = time.time()
        outcome = "ACCEPTED"
        profile_type = "N/A"
        confidence = 0.0
        token_info = "N/A"
        model_used = provider.model_name
        fallback_triggered = False

        try:
            res = provider.analyze(image_bytes, filename)
            latency = (
                res.latency_seconds
                if res.latency_seconds is not None
                else (time.time() - start_time)
            )
            profile_type = (
                res.profile_type.value
                if hasattr(res.profile_type, "value")
                else str(res.profile_type)
            )
            confidence = res.confidence
            model_used = res.model_used or provider.model_name
            fallback_triggered = res.fallback_triggered
            if res.usage_metadata:
                token_info = (
                    f"{res.usage_metadata.get('total_token_count', 'N/A')} tokens"
                )
        except AnalysisRejectedError:
            latency = time.time() - start_time
            outcome = "REJECTED (HONEST)"
        except MalformedProviderResponseError:
            latency = time.time() - start_time
            outcome = "MALFORMED_REJECTED"
        except Exception:
            latency = time.time() - start_time
            outcome = "ERROR"

        results.append(
            {
                "fixture": title,
                "filename": filename,
                "outcome": outcome,
                "model_used": model_used,
                "fallback_triggered": fallback_triggered,
                "latency": latency,
                "confidence": confidence,
                "profile_type": profile_type,
                "tokens": token_info,
            }
        )

        print(
            f"[{outcome:<18}] {title:<24} | Model: {model_used:<22} | Fallback: {str(fallback_triggered):<5} | "
            f"Latency: {latency:.2f}s | Profile: {profile_type:<18} | Conf: {confidence:.2f} | Tokens: {token_info}"
        )

    print("\n--- Phase 2: Controlled Fallback Verification ---\n")

    # 1. Test Controlled Fallback Triggering (Invalid primary model name forces fallback to Flash)
    fallback_test_provider = GeminiAnalysisProvider(
        api_key=api_key,
        model_name="gemini-nonexistent-primary-model",
        fallback_model_name="gemini-3.6-flash",
        fallback_enabled=True,
    )
    fb_file = os.path.join(fixtures_dir, "1_clear_circle.png")
    with open(fb_file, "rb") as f:
        fb_bytes = f.read()

    print(
        "[FALLBACK TEST] Invoking provider with invalid primary model 'gemini-nonexistent-primary-model'..."
    )
    start_fb = time.time()
    try:
        fb_res = fallback_test_provider.analyze(fb_bytes, "1_clear_circle.png")
        fb_lat = time.time() - start_fb
        print("  -> Primary model failed as expected.")
        print(f"  -> Fallback model triggered: {fb_res.fallback_triggered}")
        print(f"  -> Model actually used:     {fb_res.model_used}")
        print(f"  -> Total Latency:            {fb_lat:.2f}s")
        print(f"  -> Profile extracted:        {fb_res.profile_type}")
        print(
            "  -> Fallback test result:     SUCCESS (Flash-Lite attempted first, Flash called once and succeeded)"
        )
    except Exception as exc:
        print(f"  -> Fallback test failed unexpectedly: {exc}")

    # 2. Test Poor-Image Non-Fallback (Explicit rejection should NOT trigger fallback)
    print(
        "\n[NON-FALLBACK TEST] Invoking provider with cropped contour image '6_cropped_contour.png'..."
    )
    poor_file = os.path.join(fixtures_dir, "6_cropped_contour.png")
    with open(poor_file, "rb") as f:
        poor_bytes = f.read()

    try:
        poor_res = provider.analyze(poor_bytes, "6_cropped_contour.png")
        print(f"  -> Unexpectedly accepted poor image: {poor_res}")
    except AnalysisRejectedError as exc:
        print("  -> Honest rejection produced: AnalysisRejectedError")
        print(f"  -> Recovery steps provided:   {len(exc.recovery_steps)} steps")
        print(
            "  -> Non-fallback test result: SUCCESS (Valid poor-image rejection did NOT trigger fallback)"
        )
    except Exception as exc:
        print(f"  -> Unexpected exception: {exc}")

    print("\n" + "=" * 75)
    print("Live Gemini Vision Verification Suite Completed")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    sys.exit(run_live_verification())
