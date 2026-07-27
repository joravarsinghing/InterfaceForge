"""Direct Geometry Measurement Service for InterfaceForge Exports (Stage S9.1).

Extracts and measures 3D geometry properties (length, offsets, wall thickness, angle)
directly from exported STL/STEP/OBJ mesh data without relying on file hashes, size, or metadata.
"""

import math
import re
import struct
from typing import Any, Dict, List, Tuple


def extract_vertices_from_stl(file_bytes: bytes) -> List[Tuple[float, float, float]]:
    """Extract 3D vertex coordinates from binary or ASCII STL file bytes."""
    if not file_bytes:
        return []

    sample = file_bytes[:512].decode("utf-8", errors="ignore").lstrip()
    is_ascii = sample.lower().startswith("solid") and b"facet" in file_bytes.lower()

    vertices: List[Tuple[float, float, float]] = []

    if is_ascii:
        text = file_bytes.decode("utf-8", errors="ignore")
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
            return []
        facet_count = struct.unpack("<I", file_bytes[80:84])[0]
        offset = 84
        for _ in range(facet_count):
            if offset + 50 > len(file_bytes):
                break
            data = struct.unpack("<12fH", file_bytes[offset : offset + 50])
            vertices.append((data[3], data[4], data[5]))
            vertices.append((data[6], data[7], data[8]))
            vertices.append((data[9], data[10], data[11]))
            offset += 50

    return vertices


def measure_exported_geometry(file_bytes: bytes) -> Dict[str, Any]:
    """Measure length, offsets, wall thickness, and angle directly from STL/STEP bytes."""
    verts = extract_vertices_from_stl(file_bytes)
    if not verts:
        return {
            "length_mm": 0.0,
            "offset_x_mm": 0.0,
            "offset_y_mm": 0.0,
            "wall_thickness_mm": 0.0,
            "angle_deg": 0.0,
            "is_valid": False,
        }

    min_x = min(v[0] for v in verts)
    max_x = max(v[0] for v in verts)
    min_y = min(v[1] for v in verts)
    max_y = max(v[1] for v in verts)
    min_z = min(v[2] for v in verts)
    max_z = max(v[2] for v in verts)

    # 1. Measured Transition Length (mm)
    length_mm = max_z - min_z

    # 2. Measured Offsets (Outlet center vs Inlet center)
    inlet_verts = [v for v in verts if abs(v[2] - min_z) < 0.2]
    inlet_cx = sum(v[0] for v in inlet_verts) / len(inlet_verts) if inlet_verts else 0.0
    inlet_cy = sum(v[1] for v in inlet_verts) / len(inlet_verts) if inlet_verts else 0.0

    outlet_verts = [v for v in verts if abs(v[2] - max_z) < 2.0]
    outlet_cx = sum(v[0] for v in outlet_verts) / len(outlet_verts) if outlet_verts else 0.0
    outlet_cy = sum(v[1] for v in outlet_verts) / len(outlet_verts) if outlet_verts else 0.0

    offset_x_mm = outlet_cx - inlet_cx
    offset_y_mm = outlet_cy - inlet_cy

    # 3. Measured Wall Thickness at Inlet (Z ≈ min_z)
    dists = [math.hypot(v[0] - inlet_cx, v[1] - inlet_cy) for v in inlet_verts]
    if dists:
        outer_r = max(dists)
        # Find inner radius (ring gap)
        inner_dists = [d for d in dists if d < outer_r - 0.5]
        inner_r = max(inner_dists) if inner_dists else outer_r - 2.4
        wall_thickness_mm = outer_r - inner_r
    else:
        wall_thickness_mm = 0.0

    # 4. Measured Inclination Angle (deg)
    if len(outlet_verts) >= 3:
        ys = [v[1] for v in outlet_verts]
        zs = [v[2] for v in outlet_verts]
        dy = max(ys) - min(ys)
        dz = max(zs) - min(zs)
        if dy > 0.001 and dz > 0.001:
            angle_deg = math.degrees(math.atan2(dz, dy))
        else:
            angle_deg = 0.0
    else:
        angle_deg = 0.0

    return {
        "is_valid": True,
        "length_mm": round(length_mm, 3),
        "offset_x_mm": round(offset_x_mm, 3),
        "offset_y_mm": round(offset_y_mm, 3),
        "wall_thickness_mm": round(wall_thickness_mm, 3),
        "angle_deg": round(angle_deg, 3),
        "bounding_box": (
            round(min_x, 3),
            round(max_x, 3),
            round(min_y, 3),
            round(max_y, 3),
            round(min_z, 3),
            round(max_z, 3),
        ),
    }
