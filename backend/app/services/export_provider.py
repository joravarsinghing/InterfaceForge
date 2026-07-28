import base64
import hashlib
import json
import math
import os
import re
import struct
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import websockets
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
        "OPEN_SHELL",
        "ADVANCED_FACE",
        "FACE_SURFACE",
        "SHELL_BASED_SURFACE_MODEL",
        "GEOMETRIC_SET",
        "AXIS2_PLACEMENT_3D",
        "CARTESIAN_POINT",
    ]
    found_solids = [e for e in entities if e in body_types]

    if not found_solids:
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
    """Validate non-empty KCL source code."""
    return bool(file_bytes and len(file_bytes.strip()) > 0)


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


def _obj_to_mock_step_bytes(obj_content: str, model_revision: int) -> bytes:
    """Convert Wavefront OBJ geometry string to valid ISO-10303-21 STEP bytes."""
    timestamp = current_iso_timestamp()
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('InterfaceForge Adapter Model Rev {model_revision}'),'2;1');",
        (
            f"FILE_NAME('interfaceforge_adapter_rev{model_revision}.step','{timestamp}',"
            "('InterfaceForge'),('Makeathon 2026'),'InterfaceForge Compiler','Zoo API','');"
        ),
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));",
        "ENDSEC;",
        "DATA;",
    ]

    vertices: List[Tuple[float, float, float]] = []
    for line in obj_content.splitlines():
        line = line.strip()
        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))

    entity_idx = 10
    point_refs = []
    for v in vertices:
        lines.append(f"#{entity_idx}=CARTESIAN_POINT('',({v[0]:.4f},{v[1]:.4f},{v[2]:.4f}));")
        point_refs.append(f"#{entity_idx}")
        entity_idx += 1

    axis_idx = entity_idx
    lines.append(f"#{axis_idx}=DIRECTION('',(0.,0.,1.));")
    entity_idx += 1
    dir_idx = entity_idx
    lines.append(f"#{dir_idx}=DIRECTION('',(1.,0.,0.));")
    entity_idx += 1
    placement_idx = entity_idx
    pref = point_refs[0] if point_refs else 10
    lines.append(f"#{placement_idx}=AXIS2_PLACEMENT_3D('',#{pref},#{axis_idx},#{dir_idx});")
    entity_idx += 1

    lines.append(f"#{entity_idx}=CLOSED_SHELL('AdapterShell',());")
    shell_idx = entity_idx
    entity_idx += 1

    lines.append(f"#{entity_idx}=MANIFOLD_SOLID_BREP('AdapterSolid',#{shell_idx});")
    lines.append("ENDSEC;")
    lines.append("END-ISO-10303-21;")

    return "\n".join(lines).encode("utf-8")


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
        elif fmt == "step":
            file_bytes = _obj_to_mock_step_bytes(obj_content, model_revision)
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

        token = settings.zoo_api_token
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

        # Enforce prohibition guard against local generate_adapter_obj() per S8.3
        set_prohibit_local_obj(True)

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

        ws_url = f"{settings.zoo_api_base_url.replace('http', 'ws')}/ws/modeling/commands"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            # Execute Zoo-native export via live Zoo Modeling WebSocket session
            async with websockets.connect(ws_url, additional_headers=headers) as ws:

                async def send_cmd(cmd_dict: dict) -> Dict[str, Any]:
                    c_id = str(uuid.uuid4())
                    payload = {
                        "type": "modeling_cmd_req",
                        "cmd_id": c_id,
                        "cmd": cmd_dict,
                    }
                    await ws.send(json.dumps(payload))

                    while True:
                        recv_msg = await ws.recv()
                        if isinstance(recv_msg, bytes):
                            if msgpack is not None:
                                res_b = msgpack.unpackb(recv_msg, raw=False)
                                return dict(res_b) if isinstance(res_b, dict) else {}
                            obj, _ = unpack_msgpack(recv_msg)
                            return dict(obj) if isinstance(obj, dict) else {}
                        data = json.loads(recv_msg)
                        r_type = data.get("resp", {}).get("type")
                        if r_type in (
                            "modeling_session_data",
                            "ice_server_info",
                            "metrics_request",
                        ):
                            continue
                        if not data.get("success", True):
                            errs = data.get("errors", [])
                            err_msg = (
                                errs[0].get("message", "Zoo Engine error")
                                if errs
                                else "Zoo Engine error"
                            )
                            raise RuntimeError(f"ZOO_ENGINE_ERROR: {err_msg}")
                        if r_type == "modeling":
                            return dict(data)
                    return {}

                # 1. Set Units
                await send_cmd({"type": "set_scene_units", "unit": "mm"})

                # Extract schema parameters
                if_a_type = project.interface_a.profile_type.value if project else "circle"
                if_b_type = project.interface_b.profile_type.value if project else "circle"

                length_mm = project.connection.length_mm if project else 40.0
                wall_mm = project.manufacturing.wall_thickness_mm if project else 2.4
                clearance_a = project.manufacturing.clearance_a_mm if project else 0.0
                clearance_b = project.manufacturing.clearance_b_mm if project else 0.0

                offset_x = project.connection.offset_x_mm if project else 0.0
                offset_y = project.connection.offset_y_mm if project else 0.0
                angle_deg = project.connection.angle_deg if project else 0.0

                if if_a_type == "circle":
                    outer_dia_a = (
                        _get_dim_val(project.interface_a, "outer_diameter", 50.0)
                        if project
                        else 50.0
                    )
                    size_a_outer = outer_dia_a + (2.0 * clearance_a)
                    size_a_inner = size_a_outer - (2.0 * wall_mm)
                else:
                    w_a = _get_dim_val(project.interface_a, "width", 50.0) if project else 50.0
                    h_a = _get_dim_val(project.interface_a, "height", 50.0) if project else 50.0
                    outer_w_a = w_a + (2.0 * clearance_a)
                    outer_h_a = h_a + (2.0 * clearance_a)
                    inner_w_a = outer_w_a - (2.0 * wall_mm)
                    inner_h_a = outer_h_a - (2.0 * wall_mm)

                if if_b_type == "circle":
                    outer_dia_b = (
                        _get_dim_val(project.interface_b, "outer_diameter", 34.5)
                        if project
                        else 34.5
                    )
                    size_b_outer = outer_dia_b - (2.0 * clearance_b)
                    size_b_inner = size_b_outer - (2.0 * wall_mm)
                else:
                    w_b = _get_dim_val(project.interface_b, "width", 50.0) if project else 50.0
                    h_b = _get_dim_val(project.interface_b, "height", 50.0) if project else 50.0
                    outer_w_b = w_b - (2.0 * clearance_b)
                    outer_h_b = h_b - (2.0 * clearance_b)
                    inner_w_b = outer_w_b - (2.0 * wall_mm)
                    inner_h_b = outer_h_b - (2.0 * wall_mm)

                # 2. Make plane A (Z=0)
                await send_cmd(
                    {
                        "type": "make_plane",
                        "origin": {"x": 0, "y": 0, "z": 0},
                        "x_axis": {"x": 1, "y": 0, "z": 0},
                        "y_axis": {"x": 0, "y": 1, "z": 0},
                        "size": 100,
                        "clobber": False,
                        "hide": True,
                    }
                )

                # 3. Make plane B (Z=length_mm, with offset and angle rotation)
                rad_a = math.radians(angle_deg)
                cos_a = math.cos(rad_a)
                sin_a = math.sin(rad_a)

                await send_cmd(
                    {
                        "type": "make_plane",
                        "origin": {"x": offset_x, "y": offset_y, "z": length_mm},
                        "x_axis": {"x": 1.0, "y": 0.0, "z": 0.0},
                        "y_axis": {"x": 0.0, "y": cos_a, "z": sin_a},
                        "size": 100,
                        "clobber": False,
                        "hide": True,
                    }
                )

                r_plane = await send_cmd(
                    {"type": "scene_get_entity_ids", "filter": ["plane"], "skip": 0, "take": 10}
                )
                plane_ids = (
                    r_plane.get("resp", {})
                    .get("data", {})
                    .get("modeling_response", {})
                    .get("data", {})
                    .get("entity_ids", [[]])[0]
                )
                plane_a_id = plane_ids[0]
                plane_b_id = plane_ids[1]

                # 4. Construct outer and inner sketches
                if if_a_type == "circle":
                    path_outer_a = await _build_ngon_sketch(
                        send_cmd, plane_a_id, size_a_outer / 2.0
                    )
                    path_inner_a = await _build_ngon_sketch(
                        send_cmd, plane_a_id, size_a_inner / 2.0
                    )
                else:
                    path_outer_a = await _build_rect_sketch(
                        send_cmd, plane_a_id, outer_w_a, outer_h_a
                    )
                    path_inner_a = await _build_rect_sketch(
                        send_cmd, plane_a_id, inner_w_a, inner_h_a
                    )

                if if_b_type == "circle":
                    path_outer_b = await _build_ngon_sketch(
                        send_cmd, plane_b_id, size_b_outer / 2.0
                    )
                    path_inner_b = await _build_ngon_sketch(
                        send_cmd, plane_b_id, size_b_inner / 2.0
                    )
                else:
                    path_outer_b = await _build_rect_sketch(
                        send_cmd, plane_b_id, outer_w_b, outer_h_b
                    )
                    path_inner_b = await _build_rect_sketch(
                        send_cmd, plane_b_id, inner_w_b, inner_h_b
                    )

                # 5. Loft outer solid
                r_loft_outer = await send_cmd(
                    {
                        "type": "loft",
                        "section_ids": [path_outer_a, path_outer_b],
                        "v_degree": 1,
                        "bez_approximate_rational": False,
                        "tolerance": 0.001,
                    }
                )
                outer_solid_id = (
                    r_loft_outer.get("resp", {})
                    .get("data", {})
                    .get("modeling_response", {})
                    .get("data", {})
                    .get("solid_id")
                )

                # 6. Loft inner solid
                r_loft_inner = await send_cmd(
                    {
                        "type": "loft",
                        "section_ids": [path_inner_a, path_inner_b],
                        "v_degree": 1,
                        "bez_approximate_rational": False,
                        "tolerance": 0.001,
                    }
                )
                inner_solid_id = (
                    r_loft_inner.get("resp", {})
                    .get("data", {})
                    .get("modeling_response", {})
                    .get("data", {})
                    .get("solid_id")
                )

                # 7. Boolean subtract inner void from outer solid
                if outer_solid_id and inner_solid_id:
                    await send_cmd(
                        {
                            "type": "boolean_subtract",
                            "target_ids": [outer_solid_id],
                            "tool_ids": [inner_solid_id],
                            "tolerance": 0.001,
                        }
                    )

                # 8. Retrieve solid3d entity IDs
                r_solid = await send_cmd(
                    {"type": "scene_get_entity_ids", "filter": ["solid3d"], "skip": 0, "take": 10}
                )
                solid_ids = (
                    r_solid.get("resp", {})
                    .get("data", {})
                    .get("modeling_response", {})
                    .get("data", {})
                    .get("entity_ids", [[]])[0]
                )

                # 9. Issue Zoo-native export command
                if fmt == "stl":
                    export_cmd = {
                        "type": "export",
                        "entity_ids": solid_ids,
                        "format": {
                            "type": "stl",
                            "coords": {
                                "forward": {"axis": "y", "direction": "negative"},
                                "up": {"axis": "z", "direction": "positive"},
                            },
                            "selection": {"type": "default_scene"},
                            "storage": "binary",
                            "units": "mm",
                        },
                    }
                else:  # step
                    export_cmd = {
                        "type": "export",
                        "entity_ids": solid_ids,
                        "format": {
                            "type": "step",
                            "coords": {
                                "forward": {"axis": "y", "direction": "negative"},
                                "up": {"axis": "z", "direction": "positive"},
                            },
                            "selection": {"type": "default_scene"},
                        },
                    }

                export_res = await send_cmd(export_cmd)

                # Extract files payload from native export response
                files_list = (
                    export_res.get("resp", {})
                    .get("data", {})
                    .get("modeling_response", {})
                    .get("data", {})
                    .get("files", [])
                )
                if not files_list:
                    files_list = export_res.get("resp", {}).get("data", {}).get("files", [])

                out_bytes = None
                for fitem in files_list:
                    if isinstance(fitem, dict) and "contents" in fitem:
                        c_val = fitem["contents"]
                        if isinstance(c_val, bytes):
                            out_bytes = c_val
                        elif isinstance(c_val, str):
                            out_bytes = base64.b64decode(c_val)
                        elif isinstance(c_val, list):
                            out_bytes = bytes(c_val)
                        break

                if not out_bytes:
                    raise ValueError(f"Zoo-native export command returned no files for '{fmt}'.")

                # Perform deep topology validation on returned file bytes
                if fmt == "stl":
                    stl_res = parse_and_validate_stl(out_bytes)
                    if not stl_res["is_valid"]:
                        raise ValueError(
                            f"Zoo-native STL export failed geometry validation: {stl_res['error']}"
                        )
                elif fmt == "step":
                    step_res = parse_and_validate_step(out_bytes)
                    if not step_res["is_valid"]:
                        raise ValueError(
                            "Zoo-native STEP export failed geometry validation: "
                            f"{step_res['error']}"
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
                error_message=f"Zoo-native export failed for '{fmt}': {err_msg}",
                recovery_steps=[
                    "Verify Zoo Engine API service connection.",
                    "Retry export operation.",
                ],
                is_mock=False,
            )
        finally:
            set_prohibit_local_obj(False)


def get_export_provider() -> ExportProvider:
    """Factory function returning active ExportProvider based on configuration."""
    provider_name = settings.get_effective_export_provider()
    if provider_name == "zoo":
        return ZooExportProvider()
    return MockExportProvider()
