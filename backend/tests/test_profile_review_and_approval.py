"""Tests for Stage S4B Ã¢â‚¬â€ Profile Review and Structural Validation."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.models.schema import DimensionProvenance, ProfileType, WorkflowState


def create_sample_png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img.save(buf, format="PNG")
    return buf.getvalue()
