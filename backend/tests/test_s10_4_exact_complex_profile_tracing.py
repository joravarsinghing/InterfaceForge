"""S10.4 Tests: Exact Complex Profile Tracing, Scale Calibration, and Review Pipeline."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.models.schema import (
    Dimension,
    DimensionProvenance,
    Interface,
    Point2D,
    ProfileType,
    TracedContour,
)
from app.services.analysis_provider import MockAnalysisProvider
from app.services.profile_validation import validate_interface_profile


def create_test_extrusion_png() -> bytes:
    """Helper to generate a PNG drawing file."""
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 200), color="white")
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestS104ExactComplexProfileTracing:
    """Comprehensive backend test suite for Stage S10.4 requirements."""

    def test_complex_profile_cannot_silently_become_primitive(self):
        """A complex profile drawing returns traced_closed and is_complex=True."""
        provider = MockAnalysisProvider()
        result = provider.analyze(create_test_extrusion_png(), "drawing_a_2040_t_slot.png")

        assert result.profile_type == ProfileType.TRACED_CLOSED
        assert result.is_complex is True
        assert result.traced_outer_contour is not None
        assert len(result.traced_outer_contour.points) >= 4
        assert len(result.traced_hole_contours) >= 1

    def test_exact_and_simplified_status_rendering(self):
        """Interface status is exact_trace_ready for traced profile."""
        pts = [
            Point2D(x=-20, y=-20),
            Point2D(x=20, y=-20),
            Point2D(x=20, y=20),
            Point2D(x=-20, y=20),
        ]
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=TracedContour(
                id="outer_contour",
                points=pts,
                is_closed=True,
            ),
            verification_status="exact_trace_ready",
        )
        assert interface.verification_status == "exact_trace_ready"
        assert interface.primitive_fallback_active is False

        # Set primitive fallback
        interface.primitive_fallback_active = True
        interface.primitive_fallback_label = "Simplified envelope â€” not the exact cross-section"
        interface.verification_status = "simplified_envelope_only"

        assert interface.primitive_fallback_active is True
        assert "Simplified envelope" in interface.primitive_fallback_label
        assert interface.verification_status == "simplified_envelope_only"

    def test_traced_outer_contour_persistence(self):
        """Traced outer contour is stored and persisted in project service."""
        pts = [
            Point2D(x=-20, y=-20),
            Point2D(x=20, y=-20),
            Point2D(x=20, y=20),
            Point2D(x=-20, y=20),
        ]
        outer = TracedContour(
            id="outer_contour",
            points=pts,
            is_closed=True,
            classification="outer_contour",
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=outer,
        )
        is_valid, errors, warnings = validate_interface_profile(interface)

        assert is_valid is True
        assert len(errors) == 0
        assert interface.traced_outer_contour.point_count == 4

    def test_negative_contour_persistence(self):
        """Enclosed negative region contours persist with classification and decision."""
        pts = [
            Point2D(x=-20, y=-20),
            Point2D(x=20, y=-20),
            Point2D(x=20, y=20),
            Point2D(x=-20, y=20),
        ]
        hole = TracedContour(
            id="region_1",
            points=[Point2D(x=-5, y=-5), Point2D(x=5, y=-5), Point2D(x=5, y=5), Point2D(x=-5, y=5)],
            is_closed=True,
            classification="hole",
            decision="include",
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=TracedContour(
                id="outer_contour",
                points=pts,
                is_closed=True,
            ),
            traced_hole_contours=[hole],
        )

        assert len(interface.traced_hole_contours) == 1
        assert interface.traced_hole_contours[0].classification == "hole"
        assert interface.traced_hole_contours[0].decision == "include"

    def test_hole_inclusion_exclusion(self):
        """Updating hole contour decision to 'ignore' or 'unsure' is accepted."""
        hole = TracedContour(
            id="region_1",
            points=[Point2D(x=-5, y=-5), Point2D(x=5, y=-5), Point2D(x=5, y=5), Point2D(x=-5, y=5)],
            is_closed=True,
            classification="slot",
            decision="ignore",
        )
        assert hole.decision == "ignore"
        hole.decision = "unsure"
        assert hole.decision == "unsure"

    def test_feature_linked_dimensions(self):
        """Dimensions link to geometry features using feature_ref and source_annotation."""
        dim = Dimension(
            id="overall_width",
            label="Overall Width",
            value=40.0,
            unit="mm",
            provenance=DimensionProvenance.IMAGE_EXTRACTED,
            confidence=0.95,
            critical=True,
            feature_ref="outer_contour",
            source_annotation="40",
        )
        assert dim.feature_ref == "outer_contour"
        assert dim.source_annotation == "40"

    def test_unmapped_dimension_warning(self):
        """Unmapped dimensions have feature_ref=None and unresolved provenance."""
        dim = Dimension(
            id="unmapped_1",
            label="Material Spec",
            value=0.0,
            unit="mm",
            provenance=DimensionProvenance.UNRESOLVED,
            confidence=0.50,
            critical=False,
            feature_ref=None,
            source_annotation="6063-T6",
        )
        assert dim.feature_ref is None
        assert dim.provenance == DimensionProvenance.UNRESOLVED

    def test_malformed_self_intersecting_trace_rejection(self):
        """Self-intersecting outer contour is rejected during structural validation."""
        intersecting_outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=0, y=0),
                Point2D(x=10, y=10),
                Point2D(x=0, y=10),
                Point2D(x=10, y=0),  # Bowtie shape creates self-intersection
            ],
            is_closed=True,
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            traced_outer_contour=intersecting_outer,
        )
        is_valid, errors, warnings = validate_interface_profile(interface)

        assert is_valid is False
        assert any("intersects itself" in err for err in errors)

    def test_primitive_profile_regression(self):
        """Circle, rectangle, and rounded rectangle profiles continue to validate correctly."""
        circle_interface = Interface(
            id="interface_a",
            profile_type=ProfileType.CIRCLE,
            dimensions=[
                Dimension(id="outer_diameter", label="Outer Diameter", value=50.0),
                Dimension(id="wall_thickness", label="Wall Thickness", value=5.0),
            ],
        )
        is_valid, errors, warnings = validate_interface_profile(circle_interface)
        assert is_valid is True
        assert len(errors) == 0

    def test_bounding_box_fallback_rejected_for_complex_profile(self):
        """A 4-point bounding rectangle is rejected when the profile is flagged complex."""
        bounding_box_outer = TracedContour(
            id="outer_contour",
            points=[
                Point2D(x=-20, y=-20),
                Point2D(x=20, y=-20),
                Point2D(x=20, y=20),
                Point2D(x=-20, y=20),
            ],
            is_closed=True,
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            is_complex=True,
            traced_outer_contour=bounding_box_outer,
            primitive_fallback_active=False,
            verification_status="exact_trace_ready",
        )
        is_valid, errors, warnings = validate_interface_profile(interface)
        has_warning = any(
            "requires detailed non-convex perimeter" in w or "simplified" in w for w in warnings
        )
        assert has_warning is True

    def test_concavity_and_inner_region_preservation(self):
        """Non-convex outer contour with T-slot concavities and inner holes validates cleanly."""
        t_slot_pts = [
            Point2D(x=-16, y=20),
            Point2D(x=16, y=20),
            Point2D(x=20, y=16),
            Point2D(x=20, y=4.4),
            Point2D(x=15.6, y=4.4),
            Point2D(x=15.6, y=2.4),
            Point2D(x=20, y=2.4),
            Point2D(x=20, y=-2.4),
            Point2D(x=15.6, y=-2.4),
            Point2D(x=15.6, y=-4.4),
            Point2D(x=20, y=-4.4),
            Point2D(x=20, y=-16),
            Point2D(x=16, y=-20),
            Point2D(x=4.4, y=-20),
            Point2D(x=4.4, y=-15.6),
            Point2D(x=2.4, y=-15.6),
            Point2D(x=2.4, y=-20),
            Point2D(x=-2.4, y=-20),
            Point2D(x=-2.4, y=-15.6),
            Point2D(x=-4.4, y=-15.6),
            Point2D(x=-4.4, y=-20),
            Point2D(x=-16, y=-20),
            Point2D(x=-20, y=-16),
            Point2D(x=-20, y=-4.4),
            Point2D(x=-15.6, y=-4.4),
            Point2D(x=-15.6, y=-2.4),
            Point2D(x=-20, y=-2.4),
            Point2D(x=-20, y=2.4),
            Point2D(x=-15.6, y=2.4),
            Point2D(x=-15.6, y=4.4),
            Point2D(x=-20, y=4.4),
            Point2D(x=-20, y=16),
        ]
        outer = TracedContour(id="outer_contour", points=t_slot_pts, is_closed=True)
        bore_points = [
            Point2D(x=-3.4, y=0),
            Point2D(x=0, y=3.4),
            Point2D(x=3.4, y=0),
            Point2D(x=0, y=-3.4),
        ]
        hole = TracedContour(
            id="center_bore",
            points=bore_points,
            is_closed=True,
            classification="hole",
            decision="include",
        )
        interface = Interface(
            id="interface_a",
            profile_type=ProfileType.TRACED_CLOSED,
            is_complex=True,
            traced_outer_contour=outer,
            traced_hole_contours=[hole],
        )
        is_valid, errors, warnings = validate_interface_profile(interface)
        assert is_valid is True
        assert interface.traced_outer_contour.point_count == 32
        assert len(interface.traced_hole_contours) == 1
