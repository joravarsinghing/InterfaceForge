import base64
import hashlib
import io
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

try:
    import msgpack  # type: ignore[import-untyped]
except ImportError:
    msgpack = None

from app.core.config import settings
from app.models.schema import Project
from app.services.geometry_generator import (
    generate_adapter_obj,
    get_geometry_hash,
    parse_obj_mesh,
    set_prohibit_local_obj,
)



def current_iso_timestamp() -> str:
    """Generate ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def redact_secrets(text: str, token: str = "") -> str:
    """Redact authorization headers, tokens, and secrets from string content."""
    if not text:
        return ""
    redacted = text
    if token:
        redacted = redacted.replace(token, "[REDACTED_TOKEN]")
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r"api-[a-f0-9\-]+", "[REDACTED_API_KEY]", redacted)
    return redacted


def unpack_msgpack(data: bytes, offset: int = 0) -> Tuple[Any, int]:
    """Pure Python lightweight MessagePack unpacker for Zoo WebSocket binary frames."""
    if offset >= len(data):
        raise ValueError("Buffer underflow")

    b = data[offset]
    offset += 1

    # Positive fixint
    if b <= 0x7F:
        return b, offset
    # Fixmap
    if 0x80 <= b <= 0x8F:
        size = b & 0x0F
        res = {}
        for _ in range(size):
            k, offset = unpack_msgpack(data, offset)
            v, offset = unpack_msgpack(data, offset)
            res[k] = v
        return res, offset
    # Fixarray
    if 0x90 <= b <= 0x9F:
        size = b & 0x0F
        res_list = []
        for _ in range(size):
            elem, offset = unpack_msgpack(data, offset)
            res_list.append(elem)
        return res_list, offset
    # Fixstr
    if 0xA0 <= b <= 0xBF:
        size = b & 0x1F
        s = data[offset : offset + size].decode("utf-8", errors="ignore")
        return s, offset + size
    # Nil / bool
    if b == 0xC0:
        return None, offset
    if b == 0xC2:
        return False, offset
    if b == 0xC3:
        return True, offset
    # Bin8
    if b == 0xC4:
        size = data[offset]
        offset += 1
        return data[offset : offset + size], offset + size
    # Bin16
    if b == 0xC5:
        size = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        return data[offset : offset + size], offset + size
    # Bin32
    if b == 0xC6:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        return data[offset : offset + size], offset + size
    # Str8
    if b == 0xD9:
        size = data[offset]
        offset += 1
        s = data[offset : offset + size].decode("utf-8", errors="ignore")
        return s, offset + size
    # Str16
    if b == 0xDA:
        size = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        s = data[offset : offset + size].decode("utf-8", errors="ignore")
        return s, offset + size
    # Str32
    if b == 0xDB:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        s = data[offset : offset + size].decode("utf-8", errors="ignore")
        return s, offset + size
    # Array16
    if b == 0xDC:
        size = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        res_list = []
        for _ in range(size):
            elem, offset = unpack_msgpack(data, offset)
            res_list.append(elem)
        return res_list, offset
    # Array32
    if b == 0xDD:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        res_list = []
        for _ in range(size):
            elem, offset = unpack_msgpack(data, offset)
            res_list.append(elem)
        return res_list, offset
    # Map16
    if b == 0xDE:
        size = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        res = {}
        for _ in range(size):
            k, offset = unpack_msgpack(data, offset)
            v, offset = unpack_msgpack(data, offset)
            res[k] = v
        return res, offset
    # Map32
    if b == 0xDF:
        size = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4
        res = {}
        for _ in range(size):
            k, offset = unpack_msgpack(data, offset)
            v, offset = unpack_msgpack(data, offset)
            res[k] = v
        return res, offset
    # Int8/16/32/64
    if b == 0xD0:
        return struct.unpack(">b", data[offset : offset + 1])[0], offset + 1
    if b == 0xD1:
        return struct.unpack(">h", data[offset : offset + 2])[0], offset + 2
    if b == 0xD2:
        return struct.unpack(">i", data[offset : offset + 4])[0], offset + 4
    if b == 0xD3:
        return struct.unpack(">q", data[offset : offset + 8])[0], offset + 8
    # Uint8/16/32/64
    if b == 0xCC:
        return data[offset], offset + 1
    if b == 0xCD:
        return struct.unpack(">H", data[offset : offset + 2])[0], offset + 2
    if b == 0xCE:
        return struct.unpack(">I", data[offset : offset + 4])[0], offset + 4
    if b == 0xCF:
        return struct.unpack(">Q", data[offset : offset + 8])[0], offset + 8
    # Negative fixint
    if b >= 0xE0:
        return b - 256, offset

    raise ValueError(f"Unsupported MessagePack byte: 0x{b:02x}")


class ExportResult(BaseModel):
    """Container for per-format export operation result."""

    success: bool
    format: str  # "stl", "step", "kcl"
    artifact_ref: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    facet_count: Optional[int] = None
    entity_count: Optional[int] = None
    bounding_box: Optional[Tuple[float, float, float, float, float, float]] = None
    dimensions_mm: Optional[Tuple[float, float, float]] = None
    geometry_hash: Optional[str] = None
    zoo_model_id: Optional[str] = None
    kcl_hash: Optional[str] = None
    error_id: Optional[str] = None
    error_message: Optional[str] = None
    recovery_steps: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=current_iso_timestamp)
    is_mock: bool = True






def inspect_stl_bounded(file_bytes: bytes) -> Dict[str, Any]:
    """Inspect live Zoo STL output without retaining vertices or edge topology.

    This is intentionally a bounded geometric sanity check, not exhaustive
    closed-manifold validation. The strict offline validator remains available.
    """
    empty = {"is_valid": False, "facet_count": 0, "bounding_box": None,
             "dimensions_mm": None, "volume": 0.0, "error": ""}
    if not file_bytes:
        empty["error"] = "Empty STL file (0 bytes)."
        return empty
    if len(file_bytes) > settings.max_live_stl_bytes:
        empty["error"] = "STL payload exceeds the configured live safety limit."
        return empty

    view = memoryview(file_bytes)
    facet_count = 0
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    volume = 0.0
    vertex_count = 0
    triangle: list[tuple[float, float, float]] = []
    is_ascii = bytes(view[:512]).lstrip().lower().startswith(b"solid")

    def add_triangle(vertices: list[tuple[float, float, float]]) -> None:
        nonlocal min_x, min_y, min_z, max_x, max_y, max_z, volume
        for x, y, z in vertices:
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                raise ValueError("STL contains non-finite vertex coordinates.")
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            min_z, max_z = min(min_z, z), max(max_z, z)
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vertices
        volume += ((ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx)
                    + az * (bx * cy - by * cx)) / 6.0)

    try:
        if not is_ascii and len(view) >= 84:
            facet_count = struct.unpack_from("<I", view, 80)[0]
            if facet_count == 0:
                empty["error"] = "Binary STL header specifies 0 facets."
                return empty
            if facet_count > settings.max_live_stl_facets:
                empty["facet_count"] = facet_count
                empty["error"] = "STL facet count exceeds the configured live safety limit."
                return empty
            expected_size = 84 + facet_count * 50
            if len(view) != expected_size:
                empty["facet_count"] = facet_count
                empty["error"] = f"Binary STL size mismatch (expected {expected_size} bytes, got {len(view)})."
                return empty
            for index in range(facet_count):
                values = struct.unpack_from("<12fH", view, 84 + index * 50)
                add_triangle([(values[3], values[4], values[5]),
                              (values[6], values[7], values[8]),
                              (values[9], values[10], values[11])])
        else:
            for raw_line in io.BytesIO(view):
                line = raw_line.decode("ascii", errors="ignore").strip()
                lower = line.lower()
                if lower.startswith("facet "):
                    facet_count += 1
                    if facet_count > settings.max_live_stl_facets:
                        empty["facet_count"] = facet_count
                        empty["error"] = "STL facet count exceeds the configured live safety limit."
                        return empty
                elif lower.startswith("vertex "):
                    fields = line.split()
                    if len(fields) != 4:
                        raise ValueError("ASCII STL vertex line is malformed.")
                    triangle.append((float(fields[1]), float(fields[2]), float(fields[3])))
                    vertex_count += 1
                    if len(triangle) == 3:
                        add_triangle(triangle)
                        triangle.clear()
            if facet_count == 0 or vertex_count != facet_count * 3 or triangle:
                empty["facet_count"] = facet_count
                empty["error"] = "ASCII STL is empty or malformed."
                return empty
    except (struct.error, ValueError, OverflowError) as exc:
        empty["facet_count"] = facet_count
        empty["error"] = str(exc)
        return empty

    dx, dy, dz = max_x - min_x, max_y - min_y, max_z - min_z
    if not all(math.isfinite(value) for value in (dx, dy, dz, volume)):
        empty["facet_count"] = facet_count
        empty["error"] = "STL geometry contains non-finite values."
        return empty
    if dx <= 0 or dy <= 0 or dz <= 0:
        empty["facet_count"] = facet_count
        empty["bounding_box"] = (min_x, max_x, min_y, max_y, min_z, max_z)
        empty["dimensions_mm"] = (dx, dy, dz)
        empty["error"] = "STL geometry has a zero dimension."
        return empty
    if abs(volume) <= 1e-6:
        empty["facet_count"] = facet_count
        empty["error"] = "STL mesh has zero volume."
        return empty
    return {"is_valid": True, "facet_count": facet_count,
            "bounding_box": (round(min_x, 3), round(max_x, 3), round(min_y, 3),
                             round(max_y, 3), round(min_z, 3), round(max_z, 3)),
            "dimensions_mm": (round(dx, 3), round(dy, 3), round(dz, 3)),
            "volume": abs(volume), "error": ""}


def parse_and_validate_stl(file_bytes: bytes) -> Dict[str, Any]:
    """Parse and validate STL file (binary or ASCII) for real geometry.

    Returns dict with keys: is_valid, facet_count, bounding_box, dimensions_mm, error.
    Rejects zero-byte files, empty ASCII 'solid/endsolid' files, zero-facet files,
    and invalid headers.
    """

    if not file_bytes or len(file_bytes) == 0:
        return {
            "is_valid": False,
            "facet_count": 0,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "Empty STL file (0 bytes).",
        }

    # Detect ASCII vs Binary STL
    sample = file_bytes[:512].decode("utf-8", errors="ignore").lstrip()
    is_ascii = sample.lower().startswith("solid") and b"facet" in file_bytes.lower()

    vertices: List[Tuple[float, float, float]] = []
    facet_count = 0

    if is_ascii:
        text = file_bytes.decode("utf-8", errors="ignore")
        facet_matches = re.findall(r"facet\s+normal\s+([^\n]+)", text, re.IGNORECASE)
        facet_count = len(facet_matches)
        if facet_count == 0:
            return {
                "is_valid": False,
                "facet_count": 0,
                "bounding_box": None,
                "dimensions_mm": None,
                "error": "ASCII STL contains no facets (empty solid/endsolid).",
            }

        v_matches = re.findall(
            r"vertex\s+([\-0-9\.eE\+]+)\s+([\-0-9\.eE\+]+)\s+([\-0-9\.eE\+]+)",
            text,
            re.IGNORECASE,
        )
        for vx, vy, vz in v_matches:
            try:
                vertices.append((float(vx), float(vy), float(vz)))
            except ValueError:
                pass
    else:
        if len(file_bytes) < 84:
            return {
                "is_valid": False,
                "facet_count": 0,
                "bounding_box": None,
                "dimensions_mm": None,
                "error": "Binary STL header incomplete (< 84 bytes).",
            }

        facet_count = struct.unpack("<I", file_bytes[80:84])[0]
        if facet_count == 0:
            return {
                "is_valid": False,
                "facet_count": 0,
                "bounding_box": None,
                "dimensions_mm": None,
                "error": "Binary STL header specifies 0 facets.",
            }

        expected_min_size = 84 + (facet_count * 50)
        if len(file_bytes) < expected_min_size:
            return {
                "is_valid": False,
                "facet_count": facet_count,
                "bounding_box": None,
                "dimensions_mm": None,
                "error": (
                    f"Binary STL size mismatch (expected >= {expected_min_size} bytes, "
                    f"got {len(file_bytes)})."
                ),
            }

        offset = 84
        for _ in range(facet_count):
            if offset + 50 > len(file_bytes):
                break
            data = struct.unpack("<12fH", file_bytes[offset : offset + 50])
            vertices.append((data[3], data[4], data[5]))
            vertices.append((data[6], data[7], data[8]))
            vertices.append((data[9], data[10], data[11]))
            offset += 50

    if not vertices:
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "Failed to extract valid vertices from STL file.",
        }

    # A valid offline STL must be a closed 2-manifold, not merely a non-empty
    # triangle list. STL repeats triangle vertices, so quantize coordinates to
    # reconstruct shared edges deterministically.
    if len(vertices) != facet_count * 3:
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "STL facet payload is incomplete.",
        }
    edge_counts: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
    signed_volume = 0.0

    def key(v: tuple[float, float, float]) -> tuple[int, int, int]:
        return (round(v[0] * 1000), round(v[1] * 1000), round(v[2] * 1000))

    for index in range(0, len(vertices), 3):
        tri = vertices[index : index + 3]
        for first, second in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            first_key, second_key = sorted((key(first), key(second)))
            edge = (first_key, second_key)
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
        ax, ay, az = tri[0]
        bx, by, bz = tri[1]
        cx, cy, cz = tri[2]
        signed_volume += abs(
            (
                ax * (by * cz - bz * cy)
                - ay * (bx * cz - bz * cx)
                + az * (bx * cy - by * cx)
            )
            / 6.0
        )
    if any(count != 2 for count in edge_counts.values()):
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "STL topology is not a closed manifold.",
        }
    if abs(signed_volume) <= 1e-6:
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "STL mesh has zero volume.",
        }

    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    min_z = min(v[2] for v in vertices)
    max_z = max(v[2] for v in vertices)

    dx = max_x - min_x
    dy = max_y - min_y
    dz = max_z - min_z

    if not (math.isfinite(dx) and math.isfinite(dy) and math.isfinite(dz)):
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": None,
            "dimensions_mm": None,
            "error": "STL bounding box contains non-finite dimensions.",
        }

    if dx == 0 and dy == 0 and dz == 0:
        return {
            "is_valid": False,
            "facet_count": facet_count,
            "bounding_box": (min_x, max_x, min_y, max_y, min_z, max_z),
            "dimensions_mm": (dx, dy, dz),
            "error": "STL bounding box is a zero-volume point.",
        }

    return {
        "is_valid": True,
        "facet_count": facet_count,
        "bounding_box": (
            round(min_x, 3),
            round(max_x, 3),
            round(min_y, 3),
            round(max_y, 3),
            round(min_z, 3),
            round(max_z, 3),
        ),
        "dimensions_mm": (round(dx, 3), round(dy, 3), round(dz, 3)),
        "error": "",
    }


def parse_and_validate_step(file_bytes: bytes) -> Dict[str, Any]:
    """Parse and validate STEP (ISO 10303-21) file for real body/solid content.

    Returns dict with keys: is_valid, entity_count, solid_entities, error.
    Rejects header-only files and files without solid or geometry entities.
    """
    if not file_bytes or len(file_bytes) == 0:
        return {
            "is_valid": False,
            "entity_count": 0,
            "solid_entities": [],
            "error": "Empty STEP file (0 bytes).",
        }

    text = file_bytes.decode("utf-8", errors="ignore")
    if "ISO-10303-21;" not in text or "END-ISO-10303-21;" not in text:
        return {
            "is_valid": False,
            "entity_count": 0,
            "solid_entities": [],
            "error": "STEP file missing ISO-10303-21 start/end headers.",
        }

    data_start = text.find("DATA;")
    data_end = text.find("ENDSEC;", data_start)
    if data_start == -1 or data_end == -1:
        return {
            "is_valid": False,
            "entity_count": 0,
            "solid_entities": [],
            "error": "STEP DATA section delimiters not found.",
        }

    data_section = text[data_start:data_end]
    entities = re.findall(r"#\d+\s*=\s*([A-Za-z0-9_]+)", data_section)
    entity_count = len(entities)

    if entity_count == 0:
        return {
            "is_valid": False,
            "entity_count": 0,
            "solid_entities": [],
            "error": "STEP DATA section contains 0 entities (header-only file).",
        }

    body_types = [
        "MANIFOLD_SOLID_BREP",
        "FACETED_BREP",
        "CLOSED_SHELL",
        "ADVANCED_FACE",
        "FACE_SURFACE",
        "EDGE_LOOP",
        "ORIENTED_EDGE",
        "CARTESIAN_POINT",
        "LINE",
        "PLANE",
        "CYLINDRICAL_SURFACE",
    ]
    found_solids = [e for e in entities if e in body_types]
    has_nonempty_shell = bool(re.search(r"CLOSED_SHELL\s*\([^,]*,\s*\((?!\s*\))", data_section))
    has_faces = any(e in entities for e in ("ADVANCED_FACE", "FACE_SURFACE"))
    has_edges = any(e in entities for e in ("EDGE_LOOP", "ORIENTED_EDGE"))
    has_surfaces = any(
        e in entities for e in ("PLANE", "CYLINDRICAL_SURFACE", "SURFACE_OF_LINEAR_EXTRUSION")
    )

    if (
        not found_solids
        or not has_nonempty_shell
        or not has_faces
        or not has_edges
        or not has_surfaces
    ):
        return {
            "is_valid": False,
            "entity_count": entity_count,
            "solid_entities": [],
            "error": "STEP DATA section contains no solid body or 3D geometry entities.",
        }

    return {
        "is_valid": True,
        "entity_count": entity_count,
        "solid_entities": found_solids,
        "error": "",
    }


def validate_stl_signature(file_bytes: bytes) -> bool:
    """Validate STL binary/ASCII geometry and signature."""
    return bool(parse_and_validate_stl(file_bytes)["is_valid"])


def validate_step_signature(file_bytes: bytes) -> bool:
    """Validate STEP ISO-10303-21 geometry and signature."""
    return bool(parse_and_validate_step(file_bytes)["is_valid"])


def validate_kcl_signature(file_bytes: bytes) -> bool:
    """Validate KCL source with the installed Zoo KCL parser."""
    if not file_bytes or len(file_bytes.strip()) == 0:
        return False
    try:
        import asyncio
        import threading

        import kcl  # type: ignore[import-not-found]

        code = file_bytes.decode("utf-8")
        kcl.parse_code(code)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(kcl.mock_execute_code(code)) is True
        result_box: list[object] = []
        worker = threading.Thread(
            target=lambda: result_box.append(asyncio.run(kcl.mock_execute_code(code)))
        )
        worker.start()
        worker.join()
        return bool(result_box and result_box[0] is True)
    except Exception:
        return False


def validate_artifact_content(format_name: str, file_bytes: bytes) -> bool:
    """Perform format-specific content & non-zero file validation."""
    if not file_bytes or len(file_bytes) == 0:
        return False
    fmt = format_name.lower()
    if fmt == "stl":
        return bool(parse_and_validate_stl(file_bytes)["is_valid"])
    elif fmt == "step":
        return bool(parse_and_validate_step(file_bytes)["is_valid"])
    elif fmt == "kcl":
        return validate_kcl_signature(file_bytes)
    return len(file_bytes) > 0


class ExportProvider(ABC):
    """Abstract Base Class for CAD File Format Export Providers per ADR-006 & S8.3."""

    @abstractmethod
    async def export_format(
        self,
        project_id: str,
        model_revision: int,
        format_name: str,
        kcl_code: str,
        kcl_artifact_ref: Optional[str] = None,
        mock_scenario: Optional[str] = None,
        project: Optional[Project] = None,
        zoo_model_id: Optional[str] = None,
        kcl_hash: Optional[str] = None,
    ) -> ExportResult:
        """Export model geometry into requested format (stl, step, kcl)."""
        pass


def _obj_to_mock_stl_bytes(obj_content: str, model_revision: int) -> bytes:
    """Convert Wavefront OBJ geometry string to valid binary STL bytes."""
    vertices: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int]] = []

    for line in obj_content.splitlines():
        line = line.strip()
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            parts = line.split()
            if len(parts) >= 4:
                faces.append(
                    (
                        int(parts[1].split("/")[0]) - 1,
                        int(parts[2].split("/")[0]) - 1,
                        int(parts[3].split("/")[0]) - 1,
                    )
                )

    if not faces or not vertices:
        header = f"InterfaceForge Mock STL Rev {model_revision}".encode("utf-8").ljust(80, b"\x00")[
            :80
        ]
        return header + struct.pack("<I", 0)

    header = f"InterfaceForge STL Rev {model_revision}".encode("utf-8").ljust(80, b"\x00")[:80]
    body = struct.pack("<I", len(faces))

    for v1_idx, v2_idx, v3_idx in faces:
        v1 = vertices[v1_idx]
        v2 = vertices[v2_idx]
        v3 = vertices[v3_idx]

        # Calculate face normal via cross product
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx, vy, vz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / length, ny / length, nz / length

        tri_data = (
            nx,
            ny,
            nz,
            v1[0],
            v1[1],
            v1[2],
            v2[0],
            v2[1],
            v2[2],
            v3[0],
            v3[1],
            v3[2],
            0,
        )
        body += struct.pack("<ffffffffffffH", *tri_data)

    return header + body


class MockExportProvider(ExportProvider):
    """Deterministic Mock Export Provider for testing and offline execution."""

    async def export_format(
        self,
        project_id: str,
        model_revision: int,
        format_name: str,
        kcl_code: str,
        kcl_artifact_ref: Optional[str] = None,
        mock_scenario: Optional[str] = None,
        project: Optional[Project] = None,
        zoo_model_id: Optional[str] = None,
        kcl_hash: Optional[str] = None,
    ) -> ExportResult:
        fmt = format_name.lower()
        if fmt not in ("stl", "step", "kcl"):
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-002",
                error_message=(
                    f"Unsupported export format '{format_name}'. Supported: stl, step, kcl."
                ),
                recovery_steps=["Request export in a supported format (stl, step, kcl)."],
                is_mock=True,
            )

        if fmt == "step":
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-007",
                error_message="Editable STEP solid export is planned for a future iteration using the Zoo geometry pipeline.",
                recovery_steps=["Use STL or KCL formats for active exports."],
                is_mock=True,
            )

        if mock_scenario in ("failure", f"{fmt}_failure"):

            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-001",
                error_message=f"Mock export engine failed to process format '{fmt}'.",
                recovery_steps=["Retry export for this format."],
                is_mock=True,
            )

        if mock_scenario in ("zero_byte", f"{fmt}_zero_byte"):
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-004",
                error_message=f"Export generation produced a zero-byte file for '{fmt}'.",
                recovery_steps=["Re-generate export artifact."],
                is_mock=True,
            )

        # Obtain 3D OBJ payload for project
        proj_obj = project or Project(
            project_id=project_id,
            project_token="tok_mock",
            current_schema_revision=1,
            current_model_revision=model_revision,
        )
        obj_content = generate_adapter_obj(proj_obj)
        geom_hash = kcl_hash or get_geometry_hash(obj_content)
        model_id = zoo_model_id or f"mock_model_{project_id[:8]}"

        os.makedirs("artifacts", exist_ok=True)
        filename = f"export_{project_id}_rev{model_revision}_mock_{geom_hash[:8]}.{fmt}"
        artifact_path = os.path.join("artifacts", filename)

        if os.path.exists(artifact_path) and os.path.getsize(artifact_path) > 0:
            with open(artifact_path, "rb") as f:
                existing_bytes = f.read()
            if validate_artifact_content(fmt, existing_bytes):
                stl_val = parse_and_validate_stl(existing_bytes) if fmt == "stl" else {}
                step_val = parse_and_validate_step(existing_bytes) if fmt == "step" else {}
                return ExportResult(
                    success=True,
                    format=fmt,
                    artifact_ref=artifact_path,
                    filename=f"interfaceforge_adapter_rev{model_revision}.{fmt}",
                    size_bytes=len(existing_bytes),
                    facet_count=stl_val.get("facet_count"),
                    entity_count=step_val.get("entity_count"),
                    bounding_box=stl_val.get("bounding_box"),
                    dimensions_mm=stl_val.get("dimensions_mm"),
                    geometry_hash=geom_hash,
                    zoo_model_id=model_id,
                    kcl_hash=geom_hash,
                    is_mock=True,
                )

        if fmt == "stl":
            file_bytes = _obj_to_mock_stl_bytes(obj_content, model_revision)
        else:  # kcl
            file_bytes = kcl_code.encode("utf-8") if kcl_code else b"// Empty KCL"



        if not validate_artifact_content(fmt, file_bytes):
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-004",
                error_message=f"Generated export artifact for '{fmt}' failed geometry validation.",
                recovery_steps=["Verify geometry compiler output."],
                is_mock=True,
            )

        with open(artifact_path, "wb") as f:
            f.write(file_bytes)

        stl_val = parse_and_validate_stl(file_bytes) if fmt == "stl" else {}
        step_val = parse_and_validate_step(file_bytes) if fmt == "step" else {}

        return ExportResult(
            success=True,
            format=fmt,
            artifact_ref=artifact_path,
            filename=f"interfaceforge_adapter_rev{model_revision}.{fmt}",
            size_bytes=len(file_bytes),
            facet_count=stl_val.get("facet_count"),
            entity_count=step_val.get("entity_count"),
            bounding_box=stl_val.get("bounding_box"),
            dimensions_mm=stl_val.get("dimensions_mm"),
            geometry_hash=geom_hash,
            zoo_model_id=model_id,
            kcl_hash=geom_hash,
            is_mock=True,
        )


def _get_dim_val(interface: Any, dim_id: str, default: float) -> float:
    """Helper to extract a positive finite dimension value from an interface."""
    for d in getattr(interface, "dimensions", []):
        if getattr(d, "id", None) == dim_id:
            val = getattr(d, "value", 0.0)
            if math.isfinite(val) and val > 0:
                return float(val)
    return default


async def _build_ngon_sketch(send_cmd: Any, plane_id: str, radius: float, n_sides: int = 16) -> str:
    """Build a smooth closed n-gon circle approximation on plane_id."""
    await send_cmd(
        {
            "type": "enable_sketch_mode",
            "entity_id": plane_id,
            "ortho": False,
            "animated": False,
            "adjust_camera": False,
        }
    )
    r_start = await send_cmd({"type": "start_path"})
    path_id = r_start.get("request_id")

    pts = []
    for i in range(n_sides):
        ang = 2.0 * math.pi * i / n_sides
        pts.append((round(radius * math.cos(ang), 4), round(radius * math.sin(ang), 4)))

    await send_cmd(
        {"type": "move_path_pen", "path": path_id, "to": {"x": pts[0][0], "y": pts[0][1], "z": 0.0}}
    )
    for px, py in pts[1:]:
        await send_cmd(
            {
                "type": "extend_path",
                "path": path_id,
                "segment": {"type": "line", "end": {"x": px, "y": py, "z": 0.0}, "relative": False},
            }
        )
    await send_cmd({"type": "close_path", "path_id": path_id})
    await send_cmd({"type": "sketch_mode_disable"})
    return str(path_id or "")


async def _build_rect_sketch(send_cmd: Any, plane_id: str, width: float, height: float) -> str:
    """Build a closed rectangle path on plane_id."""
    half_w = width / 2.0
    half_h = height / 2.0
    await send_cmd(
        {
            "type": "enable_sketch_mode",
            "entity_id": plane_id,
            "ortho": False,
            "animated": False,
            "adjust_camera": False,
        }
    )
    r_start = await send_cmd({"type": "start_path"})
    path_id = r_start.get("request_id")

    await send_cmd(
        {"type": "move_path_pen", "path": path_id, "to": {"x": -half_w, "y": -half_h, "z": 0.0}}
    )
    await send_cmd(
        {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": half_w, "y": -half_h, "z": 0.0},
                "relative": False,
            },
        }
    )
    await send_cmd(
        {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": half_w, "y": half_h, "z": 0.0},
                "relative": False,
            },
        }
    )
    await send_cmd(
        {
            "type": "extend_path",
            "path": path_id,
            "segment": {
                "type": "line",
                "end": {"x": -half_w, "y": half_h, "z": 0.0},
                "relative": False,
            },
        }
    )
    await send_cmd({"type": "close_path", "path_id": path_id})
    await send_cmd({"type": "sketch_mode_disable"})
    return str(path_id or "")


class ZooExportProvider(ExportProvider):
    """Authoritative Zoo-Native Export Provider per Stage S8.3.

    Recomputes and verifies SHA-256 of stored KCL artifact against executed KCL.
    Opens a Zoo Modeling WebSocket session, executes the model geometry via Zoo Engine,
    and issues the Zoo-native 'export' command to obtain authoritative STL or STEP bytes.

    STRICTLY PROHIBITS OBJ CONVERSION ENDPOINTS AND LOCAL GEOMETRY RECONSTRUCTION.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ) -> None:
        self.api_token = api_token
        self.api_base_url = api_base_url

    async def export_format(
        self,
        project_id: str,
        model_revision: int,
        format_name: str,
        kcl_code: str,
        kcl_artifact_ref: Optional[str] = None,
        mock_scenario: Optional[str] = None,
        project: Optional[Project] = None,
        zoo_model_id: Optional[str] = None,
        kcl_hash: Optional[str] = None,
    ) -> ExportResult:
        fmt = format_name.lower()
        if fmt not in ("stl", "step", "kcl"):
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-002",
                error_message=(
                    f"Unsupported export format '{format_name}'. Supported: stl, step, kcl."
                ),
                recovery_steps=["Request export in a supported format (stl, step, kcl)."],
                is_mock=False,
            )

        # Require successful Zoo Engine model reference (zoo_model_id) per S8.2/S8.3
        if not zoo_model_id:
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-003",
                error_message=(
                    "Export requires a successful Zoo Engine model reference "
                    "(zoo_model_id is missing). Production export rejected per "
                    "Stage S8.3 requirements."
                ),
                recovery_steps=[
                    "Execute 3D model generation on Zoo Engine before requesting export.",
                    "Ensure model status is CURRENT on Zoo Engine.",
                ],
                is_mock=False,
            )

        # Recompute and verify stored vs executed KCL SHA-256 hash equality
        computed_kcl_hash = (
            hashlib.sha256(kcl_code.encode("utf-8")).hexdigest() if kcl_code else "kcl_empty"
        )
        if kcl_hash and kcl_hash != computed_kcl_hash:
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-005",
                error_message=(
                    f"KCL hash mismatch between model revision ({kcl_hash[:8]}) and "
                    f"export payload ({computed_kcl_hash[:8]})."
                ),
                recovery_steps=[
                    "Re-compile KCL artifact and re-run model generation on Zoo Engine."
                ],
                is_mock=False,
            )
        effective_kcl_hash = kcl_hash or computed_kcl_hash

        if fmt == "kcl":
            return await MockExportProvider().export_format(
                project_id,
                model_revision,
                "kcl",
                kcl_code,
                kcl_artifact_ref,
                project=project,
                zoo_model_id=zoo_model_id,
                kcl_hash=effective_kcl_hash,
            )

        os.makedirs("artifacts", exist_ok=True)
        filename = (
            f"export_{project_id}_rev{model_revision}_zoo_native_"
            f"{zoo_model_id[:8]}_{effective_kcl_hash[:8]}.{fmt}"
        )
        artifact_path = os.path.join("artifacts", filename)

        if os.path.exists(artifact_path) and os.path.getsize(artifact_path) > 0:
            with open(artifact_path, "rb") as f:
                existing_bytes = f.read()
            if validate_artifact_content(fmt, existing_bytes):
                stl_val = parse_and_validate_stl(existing_bytes) if fmt == "stl" else {}
                step_val = parse_and_validate_step(existing_bytes) if fmt == "step" else {}
                set_prohibit_local_obj(False)
                return ExportResult(
                    success=True,
                    format=fmt,
                    artifact_ref=artifact_path,
                    filename=f"interfaceforge_adapter_rev{model_revision}.{fmt}",
                    size_bytes=len(existing_bytes),
                    facet_count=stl_val.get("facet_count"),
                    entity_count=step_val.get("entity_count"),
                    bounding_box=stl_val.get("bounding_box"),
                    dimensions_mm=stl_val.get("dimensions_mm"),
                    geometry_hash=effective_kcl_hash,
                    zoo_model_id=zoo_model_id,
                    kcl_hash=effective_kcl_hash,
                    is_mock=False,
                )

        token = self.api_token or settings.zoo_api_token
        if not token:
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-ZOO-401",
                error_message="Zoo API token is not configured in backend environment.",
                recovery_steps=[
                    "Configure ZOO_API_TOKEN in backend/.env file.",
                    "Set EXPORT_PROVIDER=mock for offline development.",
                ],
                is_mock=False,
            )

        previous_token = os.environ.get("ZOO_API_TOKEN")
        os.environ["ZOO_API_TOKEN"] = token
        try:
            out_bytes: bytes | None = None
            package_import_error: Exception | None = None
            try:
                import kcl  # type: ignore[import-not-found]
            except Exception as exc:
                package_import_error = exc
            else:
                export_format = (
                    kcl.FileExportFormat.Stl if fmt == "stl" else kcl.FileExportFormat.Step
                )
                files = await kcl.execute_code_and_export(kcl_code, export_format)
                if not files:
                    raise ValueError(f"Zoo KCL export returned no files for '{fmt}'.")

                first_file = files[0]
                payload = getattr(first_file, "contents", None)
                if isinstance(payload, str):
                    out_bytes = base64.b64decode(payload)
                elif isinstance(payload, list):
                    out_bytes = bytes(payload)
                elif isinstance(payload, bytes):
                    out_bytes = payload
                else:
                    raise ValueError(
                        f"Zoo KCL export returned unsupported file payload for '{fmt}'."
                    )

            if out_bytes is None:
                zoo_cli = shutil.which("zoo")
                if zoo_cli is None:
                    detail = (
                        f"Could not import kcl: {redact_secrets(str(package_import_error), token)}"
                        if package_import_error
                        else "The kcl package is unavailable."
                    )
                    return ExportResult(
                        success=False,
                        format=fmt,
                        error_id="IF-EXPORT-006",
                        error_message=(
                            "Live export requires Zoo KCL execution/export tooling. "
                            f"{detail}; zoo CLI was not found on PATH."
                        ),
                        recovery_steps=[
                            "Install a Zoo KCL export tool compatible with the backend runtime.",
                            "Use Python 3.11+ for zoo-kcl or install the zoo CLI.",
                            "Retry export after dependency installation.",
                        ],
                        is_mock=False,
                    )

                os.makedirs("artifacts", exist_ok=True)
                with tempfile.TemporaryDirectory(
                    prefix="zoo_kcl_export_", dir="artifacts"
                ) as output_dir:
                    completed = subprocess.run(
                        [
                            zoo_cli,
                            "kcl",
                            "export",
                            f"--output-format={fmt}",
                            "-",
                            output_dir,
                        ],
                        input=kcl_code.encode("utf-8"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    if completed.returncode != 0:
                        stderr = completed.stderr.decode("utf-8", errors="ignore")
                        raise RuntimeError(
                            "zoo kcl export failed: "
                            f"{redact_secrets(stderr.strip(), token) or completed.returncode}"
                        )
                    exported = [
                        os.path.join(output_dir, name)
                        for name in os.listdir(output_dir)
                        if name.lower().endswith(f".{fmt}")
                    ]
                    if not exported:
                        raise ValueError(f"zoo kcl export produced no '.{fmt}' file.")
                    with open(exported[0], "rb") as exported_file:
                        out_bytes = exported_file.read()

            if fmt == "stl":
                stl_res = parse_and_validate_stl(out_bytes)
                if not stl_res["is_valid"]:
                    raise ValueError(
                        f"Zoo KCL STL export failed geometry validation: {stl_res['error']}"
                    )
            else:
                step_res = parse_and_validate_step(out_bytes)
                if not step_res["is_valid"]:
                    raise ValueError(
                        f"Zoo KCL STEP export failed geometry validation: {step_res['error']}"
                    )

            with open(artifact_path, "wb") as f_out:
                f_out.write(out_bytes)

            stl_val = parse_and_validate_stl(out_bytes) if fmt == "stl" else {}
            step_val = parse_and_validate_step(out_bytes) if fmt == "step" else {}
            return ExportResult(
                success=True,
                format=fmt,
                artifact_ref=artifact_path,
                filename=f"interfaceforge_adapter_rev{model_revision}.{fmt}",
                size_bytes=len(out_bytes),
                facet_count=stl_val.get("facet_count"),
                entity_count=step_val.get("entity_count"),
                bounding_box=stl_val.get("bounding_box"),
                dimensions_mm=stl_val.get("dimensions_mm"),
                geometry_hash=effective_kcl_hash,
                zoo_model_id=zoo_model_id,
                kcl_hash=effective_kcl_hash,
                is_mock=False,
            )
        except Exception as e:
            err_msg = redact_secrets(str(e), token)
            return ExportResult(
                success=False,
                format=fmt,
                error_id="IF-EXPORT-001",
                error_message=f"Zoo KCL export failed for '{fmt}': {err_msg}",
                recovery_steps=[
                    "Verify Zoo KCL execution/export service connection.",
                    "Retry export operation.",
                ],
                is_mock=False,
            )
        finally:
            if previous_token is None:
                os.environ.pop("ZOO_API_TOKEN", None)
            else:
                os.environ["ZOO_API_TOKEN"] = previous_token
            set_prohibit_local_obj(False)


def get_export_provider(provider_mode: str | None = None) -> ExportProvider:
    """Factory function returning active ExportProvider based on configuration or project mode."""
    # A project-level mock selection is an explicit offline boundary. Do not
    # let a deployment-wide EXPORT_PROVIDER=zoo setting leak live export calls
    # into mock projects.
    if provider_mode == "mock":
        return MockExportProvider()

    provider_name = (
        "zoo"
        if provider_mode == "live" and settings.zoo_api_token
        else settings.get_effective_export_provider()
    )
    if provider_name == "zoo":
        return ZooExportProvider()
    return MockExportProvider()
