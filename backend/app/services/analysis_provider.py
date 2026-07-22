"""Analysis Provider interface and deterministic Mock implementation per S4A contract."""

import math
from abc import ABC, abstractmethod

from app.core.exceptions import AnalysisRejectedError, MalformedProviderResponseError
from app.models.schema import (
    AnalysisResult,
    Dimension,
    DimensionProvenance,
    Point2D,
    ProfileType,
)


class AnalysisProvider(ABC):
    """Abstract interface for interface profile analysis providers."""

    @abstractmethod
    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        """Analyze an interface image and return structured profile candidates."""
        pass


class MockAnalysisProvider(AnalysisProvider):
    """Deterministic mock analysis provider returning structured profile candidates."""

    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        fn_lower = filename.lower()

        if "malformed" in fn_lower:
            raise MalformedProviderResponseError(
                "Analysis provider returned malformed response: missing profile metadata."
            )

        if "poor" in fn_lower or "reject" in fn_lower:
            raise AnalysisRejectedError(
                message="Image quality is too low to reliably detect interface profile boundaries.",
                recovery_steps=[
                    "Ensure adequate lighting across the interface surface.",
                    "Position the camera directly square-on to the interface face.",
                    "Avoid dark shadows or reflections obscure profile edges.",
                ],
            )

        if "rectangle" in fn_lower and "rounded" not in fn_lower:
            # Candidate 2D points for rectangle (60mm x 40mm)
            rect_points = [
                Point2D(x=-30.0, y=-20.0),
                Point2D(x=30.0, y=-20.0),
                Point2D(x=30.0, y=20.0),
                Point2D(x=-30.0, y=20.0),
            ]
            rect_dims = [
                Dimension(
                    id="width",
                    label="Width",
                    value=60.0,
                    unit="mm",
                    provenance=DimensionProvenance.IMAGE_EXTRACTED,
                    confidence=0.92,
                    critical=True,
                ),
                Dimension(
                    id="height",
                    label="Height",
                    value=40.0,
                    unit="mm",
                    provenance=DimensionProvenance.IMAGE_EXTRACTED,
                    confidence=0.90,
                    critical=True,
                ),
            ]
            return AnalysisResult(
                profile_type=ProfileType.RECTANGLE,
                candidate_points=rect_points,
                candidate_dimensions=rect_dims,
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.92,
                warnings=[],
                rejection_reasons=[],
                success=True,
            )

        if "rounded" in fn_lower or "rounded_rectangle" in fn_lower:
            # Candidate points for rounded rectangle (80mm x 50mm, r=5mm)
            rounded_points = [
                Point2D(x=-35.0, y=-25.0),
                Point2D(x=35.0, y=-25.0),
                Point2D(x=40.0, y=-20.0),
                Point2D(x=40.0, y=20.0),
                Point2D(x=35.0, y=25.0),
                Point2D(x=-35.0, y=25.0),
                Point2D(x=-40.0, y=20.0),
                Point2D(x=-40.0, y=-20.0),
            ]
            rounded_dims = [
                Dimension(
                    id="width",
                    label="Width",
                    value=80.0,
                    unit="mm",
                    provenance=DimensionProvenance.IMAGE_EXTRACTED,
                    confidence=0.88,
                    critical=True,
                ),
                Dimension(
                    id="height",
                    label="Height",
                    value=50.0,
                    unit="mm",
                    provenance=DimensionProvenance.IMAGE_EXTRACTED,
                    confidence=0.88,
                    critical=True,
                ),
                Dimension(
                    id="corner_radius",
                    label="Corner Radius",
                    value=5.0,
                    unit="mm",
                    provenance=DimensionProvenance.IMAGE_EXTRACTED,
                    confidence=0.85,
                    critical=False,
                ),
            ]
            return AnalysisResult(
                profile_type=ProfileType.ROUNDED_RECTANGLE,
                candidate_points=rounded_points,
                candidate_dimensions=rounded_dims,
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.88,
                warnings=["Corner radius detected with moderate confidence."],
                rejection_reasons=[],
                success=True,
            )

        # Default fallback: Circle profile (diameter 50mm)
        circle_points = []
        radius = 25.0
        for i in range(16):
            angle = (2 * math.pi / 16) * i
            circle_points.append(
                Point2D(x=round(radius * math.cos(angle), 2), y=round(radius * math.sin(angle), 2))
            )

        circle_dims = [
            Dimension(
                id="outer_diameter",
                label="Outer Diameter",
                value=50.0,
                unit="mm",
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.95,
                critical=True,
            ),
            Dimension(
                id="wall_thickness",
                label="Wall Thickness",
                value=5.0,
                unit="mm",
                provenance=DimensionProvenance.IMAGE_EXTRACTED,
                confidence=0.90,
                critical=False,
            ),
        ]

        return AnalysisResult(
            profile_type=ProfileType.CIRCLE,
            candidate_points=circle_points,
            candidate_dimensions=circle_dims,
            provenance=DimensionProvenance.IMAGE_EXTRACTED,
            confidence=0.95,
            warnings=[],
            rejection_reasons=[],
            success=True,
        )
