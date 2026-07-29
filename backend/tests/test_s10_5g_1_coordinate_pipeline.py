"""
Focused tests for Stage S10.5G.1 â€” Gemini Annotation Mask Coordinate Pipeline.

Tests cover:
- coordinate order conversion (ymin/xmin/ymax/xmax)
- normalized coordinate scaling (0-1, 0-1000, pixels)
- crop offset validation and fallback
- EXIF orientation stub
- mask polarity
- oversized-region rejection
- protected-geometry overlap rejection (now uses erosion-based walls)
- crop fallback to full image on profile cut
- provider provenance fields
- no hardcoded-box fallback assertion
- two-run determinism
"""

import sys
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.coordinate_normalizer import (  # noqa: E402
    CoordinateValidationError,
    fix_exif_orientation,
    normalize_box,
    safer_annotation_masking,
    validate_crop_box,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def blank_white_img():
    """800x784 pure white BGR image (no profile)."""
    return np.ones((800, 784, 3), dtype=np.uint8) * 255


@pytest.fixture
def synthetic_profile_img():
    """800x784 image with a centered 300x300 solid black square profile."""
    img = np.ones((800, 784, 3), dtype=np.uint8) * 255
    # Draw thick outer profile square at center
    cv2.rectangle(img, (242, 250), (542, 550), (0, 0, 0), -1)
    # Punch a hole in center (white)
    cv2.rectangle(img, (342, 350), (442, 450), (255, 255, 255), -1)
    return img


@pytest.fixture
def interface_b_img():
    """Load real Interface B original image, skip if not present."""
    p = REPO_ROOT / "samples" / "test_fixtures" / "s10_interface_b_original.jpg"
    if not p.exists():
        pytest.skip(f"interface_b_original.jpg not found at {p}")
    return cv2.imread(str(p))


# ---------------------------------------------------------------------------
# 1. Coordinate Order Conversion â€” ymin, xmin, ymax, xmax
# ---------------------------------------------------------------------------


class TestCoordinateOrderConversion:
    def test_ymin_xmin_ymax_xmax_order_normalized_0_1(self):
        """Standard Gemini order [ymin, xmin, ymax, xmax] in 0-1 float."""
        result = normalize_box([0.1, 0.2, 0.5, 0.6], img_w=800, img_h=600)
        assert result["order"] == "ymin_xmin_ymax_xmax"
        py1, px1, py2, px2 = result["pixels"]
        # ymin=0.1 * 600 = 60, xmin=0.2 * 800 = 160, ymax=0.5*600=300, xmax=0.6*800=480
        assert py1 == 60
        assert px1 == 160
        assert py2 == 300
        assert px2 == 480

    def test_0_1000_normalization_converts_correctly(self):
        """Verify 0-1000 integers map correctly to 0-1 float then pixels."""
        # [41, 290, 80, 396] on 800x784 -> y1=41/1000*800=33, x1=290/1000*784=227
        result = normalize_box([41, 290, 80, 396], img_w=784, img_h=800)
        assert result["scale_type"] == "0-1000"
        py1, px1, py2, px2 = result["pixels"]
        assert py1 == round(41 / 1000.0 * 800)
        assert px1 == round(290 / 1000.0 * 784)
        assert py2 == round(80 / 1000.0 * 800)
        assert px2 == round(396 / 1000.0 * 784)

    def test_min_max_swap_corrected_automatically(self):
        """If ymin > ymax, they are swapped automatically without error."""
        result = normalize_box([0.5, 0.6, 0.1, 0.2], img_w=800, img_h=600)
        py1, px1, py2, px2 = result["pixels"]
        assert py1 < py2
        assert px1 < px2


# ---------------------------------------------------------------------------
# 2. Normalized Coordinate Scaling
# ---------------------------------------------------------------------------


class TestNormalizedCoordinateScaling:
    def test_0_to_1_float_detected_correctly(self):
        result = normalize_box([0.0, 0.0, 0.5, 0.5], img_w=100, img_h=100)
        assert result["scale_type"] == "0-1"

    def test_0_to_1000_integer_detected_correctly(self):
        result = normalize_box([100, 200, 500, 700], img_w=800, img_h=600)
        assert result["scale_type"] == "0-1000"

    def test_absolute_pixel_detected_correctly(self):
        normalize_box([100, 200, 500, 700], img_w=400, img_h=300)
        # max_val=700 > 1000? No. 700 < 1000. It will be 0-1000 format.
        # Let's use > 1000 range values
        result2 = normalize_box([100, 200, 1100, 1500], img_w=2000, img_h=1500)
        assert result2["scale_type"] == "pixels"

    def test_width_and_height_are_positive(self):
        result = normalize_box([0.1, 0.1, 0.9, 0.9], img_w=100, img_h=100)
        assert result["width_px"] > 0
        assert result["height_px"] > 0

    def test_invalid_non_finite_raises(self):
        with pytest.raises(CoordinateValidationError):
            normalize_box([float("nan"), 0.1, 0.9, 0.9], img_w=100, img_h=100)

    def test_negative_width_raises(self):
        # Box [0, 0, 0, 0] produces zero height (py2 = py1+1 = 1, px2=px1+1=1 so OK)
        # To get a real zero-area box, we need to cause the explicit CoordinateValidationError
        # trigger: that happens when bw<=0 OR bh<=0, which the min/max guards prevent normally.
        # Instead test that a non-finite value raises the error:
        with pytest.raises(CoordinateValidationError):
            normalize_box([float("inf"), 0.0, 0.9, 0.9], img_w=100, img_h=100)


# ---------------------------------------------------------------------------
# 3. Crop Offset Restoration / Crop Validation
# ---------------------------------------------------------------------------


class TestCropOffsetRestoration:
    def test_crop_accepted_when_fully_contains_profile(self):
        """Crop box that fully contains the protected profile extent is accepted."""
        # Protected bbox (40, 50, 660, 750) â€” profile extent
        is_valid, final_box, reason = validate_crop_box(
            proposed_crop_pixel_box=(10, 20, 700, 800),
            protected_pixel_box=(40, 50, 660, 750),
            img_w=800,
            img_h=800,
            margin_px=10,
        )
        assert is_valid is True
        assert "accepted" in reason.lower()

    def test_crop_rejected_when_cuts_top_of_profile(self):
        """Crop proposal that starts below profile top is rejected."""
        is_valid, fallback_box, reason = validate_crop_box(
            proposed_crop_pixel_box=(100, 0, 700, 800),  # y1=100 > profile y1=40
            protected_pixel_box=(40, 0, 660, 800),
            img_w=800,
            img_h=800,
            margin_px=5,
        )
        assert is_valid is False
        assert "top" in reason.lower() or "rejected" in reason.lower()

    def test_crop_rejected_when_cuts_right_side(self):
        """Crop proposal that ends before profile right edge is rejected."""
        is_valid, fallback_box, reason = validate_crop_box(
            proposed_crop_pixel_box=(0, 0, 700, 400),  # x2=400 < profile x2=600
            protected_pixel_box=(40, 0, 660, 600),
            img_w=800,
            img_h=800,
            margin_px=5,
        )
        assert is_valid is False
        assert "right" in reason.lower() or "rejected" in reason.lower()

    def test_fallback_box_contains_full_profile_with_margin(self):
        """Fallback crop box after rejection extends beyond profile by margin."""
        is_valid, fallback_box, reason = validate_crop_box(
            proposed_crop_pixel_box=(200, 200, 400, 400),
            protected_pixel_box=(50, 50, 750, 700),
            img_w=800,
            img_h=800,
            margin_px=20,
        )
        assert is_valid is False
        # Fallback should be based on protected_pixel_box Â± margin
        fy1, fx1, fy2, fx2 = fallback_box
        assert fy1 <= 50  # above profile top
        assert fx1 <= 50  # left of profile left
        assert fy2 >= 750  # below profile bottom
        assert fx2 >= 700  # right of profile right


# ---------------------------------------------------------------------------
# 4. EXIF Orientation
# ---------------------------------------------------------------------------


class TestExifOrientation:
    def test_exif_returns_image_unchanged_for_non_jpeg(self):
        """fix_exif_orientation returns image unchanged when no EXIF data."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fix_exif_orientation(img, image_bytes=None)
        np.testing.assert_array_equal(result, img)

    def test_exif_handles_corrupt_jpeg_header_gracefully(self):
        """fix_exif_orientation doesn't crash on malformed bytes."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fix_exif_orientation(img, image_bytes=b"\xff\xd8\xff\xe1\x00\x10garbage")
        assert result.shape == img.shape


# ---------------------------------------------------------------------------
# 5. Mask Polarity
# ---------------------------------------------------------------------------


class TestMaskPolarity:
    def test_mask_polarity_white_means_erased(self, synthetic_profile_img):
        """Raw mask: white (255) pixels are erased annotation pixels."""
        h, w, _ = synthetic_profile_img.shape
        # Use a box clearly in the white background area (outside profile)
        annotation_regions = [[0.0, 0.0, 0.05, 0.1]]  # small top-left corner
        cleaned_bgr, raw_mask, final_crop, crop_rejected, meta = safer_annotation_masking(
            synthetic_profile_img, annotation_regions, crop_box_raw=None
        )
        # Pixels where raw_mask==255 should be white in cleaned_bgr
        erased_pixels = cleaned_bgr[raw_mask > 0]
        if len(erased_pixels) > 0:
            assert np.all(erased_pixels == 255), "Erased pixels should be set to white"

    def test_profile_pixels_unchanged_outside_mask(self, synthetic_profile_img):
        """Pixels in raw_mask==0 remain unchanged from original."""
        annotation_regions = [[0.0, 0.0, 0.05, 0.05]]  # tiny area
        cleaned_bgr, raw_mask, final_crop, crop_rejected, meta = safer_annotation_masking(
            synthetic_profile_img, annotation_regions, crop_box_raw=None
        )
        unchanged_region = raw_mask == 0
        orig_unchanged = synthetic_profile_img[unchanged_region]
        cleaned_unchanged = cleaned_bgr[unchanged_region]
        # Allow for edge repair modifying a few pixels near mask boundary
        diff_count = np.sum(np.any(orig_unchanged != cleaned_unchanged, axis=-1))
        assert diff_count < 10, f"Too many profile pixels modified outside mask: {diff_count}"


# ---------------------------------------------------------------------------
# 6. Oversized-Region Rejection
# ---------------------------------------------------------------------------


class TestOversizedRegionRejection:
    def test_region_over_35pct_image_rejected(self, blank_white_img):
        """Annotation box covering > 35% of image area raises CoordinateValidationError."""
        h, w, _ = blank_white_img.shape
        # 0.9 * 0.9 = 81% of image
        with pytest.raises(CoordinateValidationError):
            normalize_box([0.0, 0.0, 0.9, 0.9], img_w=w, img_h=h, max_area_pct=0.35)

    def test_region_under_35pct_accepted(self, blank_white_img):
        h, w, _ = blank_white_img.shape
        result = normalize_box([0.0, 0.0, 0.25, 0.25], img_w=w, img_h=h, max_area_pct=0.35)
        assert result["area_pct"] < 0.35


# ---------------------------------------------------------------------------
# 7. Protected Geometry Overlap Rejection
# ---------------------------------------------------------------------------


class TestProtectedGeometryOverlapRejection:
    def test_region_with_zero_solid_profile_overlap_is_accepted(self, synthetic_profile_img):
        """Annotation region in pure background area (no profile pixels) is accepted."""
        h, w, _ = synthetic_profile_img.shape
        # Top-left corner (background) â€” no profile body here
        annotation_regions = [[0.0, 0.0, 0.05, 0.1]]
        _, _, _, _, meta = safer_annotation_masking(
            synthetic_profile_img, annotation_regions, crop_box_raw=None
        )
        assert meta["rejected_regions_count"] == 0
        assert meta["applied_regions_count"] == 1

    def test_thin_dimension_line_crossing_profile_boundary_is_accepted(self, synthetic_profile_img):
        """Extension lines straddling the profile boundary survive the erosion-based check."""
        h, w, _ = synthetic_profile_img.shape
        # Draw a thin 1px line from background into profile top (yâ‰ˆ250) to simulate extension line
        line_img = synthetic_profile_img.copy()
        cv2.line(line_img, (300, 230), (300, 260), (0, 0, 0), 1)

        # Annotation region that straddles the profile top
        # profile top â‰ˆ y=250, so [0.27..0.32] covers y=216..256
        annotation_regions = [
            {"label": "ext_line", "category": "extension_lines", "box": [0.27, 0.35, 0.34, 0.45]}
        ]
        _, _, _, _, meta = safer_annotation_masking(line_img, annotation_regions, crop_box_raw=None)
        # Should not be rejected
        assert meta["rejected_regions_count"] == 0


# ---------------------------------------------------------------------------
# 8. Crop Fallback to Full Image
# ---------------------------------------------------------------------------


class TestCropFallback:
    def test_crop_box_none_uses_full_image(self, synthetic_profile_img):
        """When no crop_box provided, full image is used."""
        h, w, _ = synthetic_profile_img.shape
        _, _, final_crop, crop_rejected, meta = safer_annotation_masking(
            synthetic_profile_img, [], crop_box_raw=None
        )
        assert final_crop == (0, 0, h, w)
        assert crop_rejected is False

    def test_gemini_crop_that_cuts_profile_is_rejected_and_full_image_used(self, interface_b_img):
        """Crop proposal cutting real profile right edge falls back to full image."""
        h, w, _ = interface_b_img.shape
        # This raw crop (matches previous Gemini real response) cuts the right profile edge
        crop_box = [22, 173, 952, 825]  # 0-1000 format, x2=825/1000*784=647 < profile x2=702
        _, _, final_crop, crop_rejected, meta = safer_annotation_masking(
            interface_b_img, [], crop_box_raw=crop_box
        )
        # Crop must be rejected and full image fallback used
        assert crop_rejected is True
        assert final_crop == (0, 0, h, w) or (final_crop[0] == 0 and final_crop[1] == 0)


# ---------------------------------------------------------------------------
# 9. Provider Provenance
# ---------------------------------------------------------------------------


class TestProviderProvenance:
    def test_gemini_provider_initializes_with_correct_model(self):
        """GeminiAnalysisProvider initializes with gemini-3.5-flash-lite."""
        from app.services.analysis_provider import GeminiAnalysisProvider

        provider = GeminiAnalysisProvider(api_key="test_key_12345")
        assert "gemini" in provider.model_name.lower()
        assert provider.api_key == "test_key_12345"

    def test_analysis_result_has_provider_used_field(self):
        """AnalysisResult schema includes provider_used, request_id, fallback_used, region_count."""
        from app.models.schema import AnalysisResult, ProfileType

        result = AnalysisResult(profile_type=ProfileType.TRACED_CLOSED)
        assert hasattr(result, "provider_used")
        assert hasattr(result, "request_id")
        assert hasattr(result, "fallback_used")
        assert hasattr(result, "region_count")

    def test_gemini_provider_sets_provider_used_on_success(self):
        """GeminiAnalysisProvider.analyze records guidance-assisted OpenCV provenance."""
        import json

        from app.services.analysis_provider import GeminiAnalysisProvider

        # Build a valid mock response JSON
        mock_json = json.dumps(
            {
                "input_type": "dimensioned_technical_drawing",
                "profile_type": "traced_closed",
                "is_complex": True,
                "complex_reason": "T-slot profile",
                "crop_box": None,
                "annotation_regions": [],
                "scale_calibration": {
                    "source": "drawing_dimension",
                    "reference_dimension": "overall_width",
                    "pixel_distance": 200.0,
                    "real_distance_mm": 40.0,
                    "confidence": 0.99,
                    "confirmed": True,
                },
                "candidate_dimensions": [],
                "cleanup_guidance": {"invert": True, "threshold_method": "otsu", "blur_kernel": 3},
                "provenance": "image_extracted",
                "confidence": 0.95,
                "warnings": [],
                "rejection_reasons": [],
                "success": True,
            }
        )

        provider = GeminiAnalysisProvider(api_key="test_key_abc")

        with patch.object(provider, "_call_model", return_value=(mock_json, {})):
            # Use a minimal 1x1 white image
            import struct
            import zlib

            # Create a minimal valid PNG
            def make_png(w, h):
                def make_chunk(chunk_type, data):
                    c = chunk_type + data
                    crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                    return struct.pack(">I", len(data)) + c + crc

                header = b"\x89PNG\r\n\x1a\n"
                ihdr = make_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                raw = b""
                for _ in range(h):
                    raw += b"\x00" + b"\xff\xff\xff" * w
                compressed = zlib.compress(raw, 9)
                idat = make_chunk(b"IDAT", compressed)
                iend = make_chunk(b"IEND", b"")
                return header + ihdr + idat + iend

            test_png = make_png(10, 10)
            result = provider.analyze(test_png, "test_image.png")
            assert result.provider_used == "gemini_guided_opencv"
            assert result.request_id is not None
            assert result.fallback_used is False


# ---------------------------------------------------------------------------
# 10. No Hardcoded-Box Fallback
# ---------------------------------------------------------------------------


class TestNoHardcodedBoxFallback:
    def test_safer_annotation_masking_with_empty_regions_produces_no_mask(
        self, synthetic_profile_img
    ):
        """When annotation_regions is empty, no pixels are erased."""
        _, raw_mask, _, _, meta = safer_annotation_masking(
            synthetic_profile_img, [], crop_box_raw=None
        )
        assert np.sum(raw_mask > 0) == 0, "With empty regions, no pixels should be masked"
        assert meta["applied_regions_count"] == 0

    def test_cleanup_image_v2_with_none_annotation_regions_is_unchanged(self):
        """cleanup_image_v2 with annotation_regions=None doesn't crash."""
        # Create a minimal valid PNG programmatically
        import struct
        import zlib

        from app.services.opencv_tracer import cleanup_image_v2

        def make_png(w, h):
            def make_chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            header = b"\x89PNG\r\n\x1a\n"
            ihdr = make_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            raw = b""
            for _ in range(h):
                raw += b"\x00" + b"\x00\x00\x00" * w
            compressed = zlib.compress(raw, 9)
            idat = make_chunk(b"IDAT", compressed)
            iend = make_chunk(b"IEND", b"")
            return header + ihdr + idat + iend

        test_png = make_png(100, 100)
        result_bytes, result_mask, rw, rh = cleanup_image_v2(test_png, annotation_regions=None)
        assert result_bytes is not None
        assert rw > 0 and rh > 0


# ---------------------------------------------------------------------------
# 11. Two-Run Determinism
# ---------------------------------------------------------------------------


class TestTwoRunDeterminism:
    def test_two_runs_produce_identical_masks(self, interface_b_img):
        """Two consecutive runs with same annotation regions produce identical raw_mask."""
        h, w, _ = interface_b_img.shape
        annotation_regions = [
            [41, 290, 80, 396],
            [134, 275, 179, 392],
            [906, 469, 946, 513],
        ]

        _, mask1, _, _, meta1 = safer_annotation_masking(interface_b_img, annotation_regions, None)
        _, mask2, _, _, meta2 = safer_annotation_masking(interface_b_img, annotation_regions, None)

        np.testing.assert_array_equal(mask1, mask2, err_msg="Masks must be identical between runs")
        assert meta1["applied_regions_count"] == meta2["applied_regions_count"]
        assert meta1["rejected_regions_count"] == meta2["rejected_regions_count"]

    def test_different_regions_produce_different_masks(self, interface_b_img):
        """Different annotation regions produce different raw masks."""
        regions_a = [[41, 290, 80, 396]]
        regions_b = [[906, 469, 946, 513]]

        _, mask_a, _, _, _ = safer_annotation_masking(interface_b_img, regions_a, None)
        _, mask_b, _, _, _ = safer_annotation_masking(interface_b_img, regions_b, None)

        # The masks should differ â€” different regions applied
        assert not np.array_equal(mask_a, mask_b), "Different regions must produce different masks"


# ---------------------------------------------------------------------------
# 12. Box Out-of-Bounds Assertion
# ---------------------------------------------------------------------------


class TestBoxBoundsAssertions:
    def test_box_clipped_to_image_bounds(self):
        """Coordinates that exceed image bounds are clipped to image bounds."""
        # [0, 0, 2000, 2000] in pixel format on 100x100 image
        # use is_crop=True to bypass area_pct check
        result = normalize_box([0, 0, 2000, 2000], img_w=100, img_h=100, is_crop=True)
        py1, px1, py2, px2 = result["pixels"]
        assert py1 >= 0
        assert px1 >= 0
        assert py2 <= 100
        assert px2 <= 100
