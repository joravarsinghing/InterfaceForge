"""3D Geometry Generator for InterfaceForge (Stage S8.1).

Converts canonical project geometry specifications into deterministic 3D Wavefront OBJ mesh
representations for downstream STL and STEP conversions via Zoo File Format API
per ADR-001 and Stage S8.1.
"""

import hashlib
import math
from typing import List, Tuple

from app.models.schema import Interface, ProfileType, Project

_PROHIBIT_LOCAL_OBJ_GENERATION: bool = False
_LOCAL_OBJ_CALL_COUNT: int = 0


def set_prohibit_local_obj(prohibit: bool = True) -> None:
    """Enable or disable prohibition guard for local OBJ generation."""
    global _PROHIBIT_LOCAL_OBJ_GENERATION
    _PROHIBIT_LOCAL_OBJ_GENERATION = prohibit


def is_local_obj_prohibited() -> bool:
    """Query prohibition state."""
    return _PROHIBIT_LOCAL_OBJ_GENERATION


def get_local_obj_call_count() -> int:
    """Query total calls made to local OBJ generator."""
    return _LOCAL_OBJ_CALL_COUNT


def reset_local_obj_call_count() -> None:
    """Reset call counter for testing."""
    global _LOCAL_OBJ_CALL_COUNT
    _LOCAL_OBJ_CALL_COUNT = 0


def _get_dim_val(interface: Interface, dim_id: str, default: float) -> float:
    """Helper to extract a positive finite dimension value from an interface."""
    for d in interface.dimensions:
        if d.id == dim_id and math.isfinite(d.value) and d.value > 0:
            return float(d.value)
    return default


def _sample_profile_2d(
    iface: Interface,
    is_outer: bool,
    wall_thickness: float,
    clearance: float,
    num_segments: int = 16,
) -> List[Tuple[float, float]]:
    """Sample 2D boundary points for an interface profile."""
    p_type = iface.profile_type
    pts: List[Tuple[float, float]] = []

    if p_type == ProfileType.CIRCLE:
        outer_dia = _get_dim_val(iface, "outer_diameter", 50.0)
        if is_outer:
            eff_dia = outer_dia + (2.0 * clearance)
        else:
            eff_dia = outer_dia + (2.0 * clearance) - (2.0 * wall_thickness)

        radius = max(eff_dia / 2.0, 1.0)
        for i in range(num_segments):
            theta = 2.0 * math.pi * i / num_segments
            pts.append((radius * math.cos(theta), radius * math.sin(theta)))

    elif p_type in (ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE):
        w = _get_dim_val(iface, "width", 50.0)
        h = _get_dim_val(iface, "height", 50.0)

        if is_outer:
            eff_w = w + (2.0 * clearance)
            eff_h = h + (2.0 * clearance)
        else:
            eff_w = w + (2.0 * clearance) - (2.0 * wall_thickness)
            eff_h = h + (2.0 * clearance) - (2.0 * wall_thickness)

        hw = max(eff_w / 2.0, 1.0)
        hh = max(eff_h / 2.0, 1.0)

        if p_type == ProfileType.RECTANGLE and num_segments > 4:
            # Interpolate num_segments around rectangle perimeter
            segs_per_side = num_segments // 4
            # Bottom side (-hh) from -hw to hw
            for i in range(segs_per_side):
                pts.append((-hw + (2 * hw * i / segs_per_side), -hh))
            # Right side (hw) from -hh to hh
            for i in range(segs_per_side):
                pts.append((hw, -hh + (2 * hh * i / segs_per_side)))
            # Top side (hh) from hw to -hw
            for i in range(segs_per_side):
                pts.append((hw - (2 * hw * i / segs_per_side), hh))
            # Left side (-hw) from hh to -hh
            for i in range(segs_per_side):
                pts.append((-hw, hh - (2 * hh * i / segs_per_side)))
        elif p_type == ProfileType.RECTANGLE:
            # Keep every profile ring at exactly num_segments vertices so
            # corresponding loft indices cannot twist or reference gaps.
            segs_per_side = max(1, num_segments // 4)
            for i in range(segs_per_side):
                t = i / segs_per_side
                pts.append((-hw + 2 * hw * t, -hh))
            for i in range(segs_per_side):
                t = i / segs_per_side
                pts.append((hw, -hh + 2 * hh * t))
            for i in range(segs_per_side):
                t = i / segs_per_side
                pts.append((hw - 2 * hw * t, hh))
            for i in range(segs_per_side):
                t = i / segs_per_side
                pts.append((-hw, hh - 2 * hh * t))
        else:
            # Sample rounded rectangle with corner radii
            r = _get_dim_val(iface, "corner_radius", 5.0)
            r = min(r, hw * 0.8, hh * 0.8)
            corner_segs = max(num_segments // 4, 2)

            # Bottom-Right corner
            for i in range(corner_segs):
                th = (0.0 + (i / (corner_segs - 1)) * 0.5) * math.pi
                pts.append((hw - r + r * math.cos(th), -hh + r + r * math.sin(th)))
            # Top-Right corner
            for i in range(corner_segs):
                th = (0.5 + (i / (corner_segs - 1)) * 0.5) * math.pi
                pts.append((hw - r + r * math.cos(th), hh - r + r * math.sin(th)))
            # Top-Left corner
            for i in range(corner_segs):
                th = (1.0 + (i / (corner_segs - 1)) * 0.5) * math.pi
                pts.append((-hw + r + r * math.cos(th), hh - r + r * math.sin(th)))
            # Bottom-Left corner
            for i in range(corner_segs):
                th = (1.5 + (i / (corner_segs - 1)) * 0.5) * math.pi
                pts.append((-hw + r + r * math.cos(th), -hh + r + r * math.sin(th)))

    return pts


def generate_adapter_obj(project: Project) -> str:
    """Generate 3D Wavefront OBJ payload representing the model's exact geometry.

    Used ONLY for isolated mock testing. Prohibited in production export paths per S8.2.
    """
    global _LOCAL_OBJ_CALL_COUNT
    _LOCAL_OBJ_CALL_COUNT += 1

    if _PROHIBIT_LOCAL_OBJ_GENERATION:
        raise RuntimeError(
            "PRODUCTION EXPORT VIOLATION: Local generate_adapter_obj() called "
            "in production export path per ADR-001/S8.2."
        )

    if_a = project.interface_a
    if_b = project.interface_b
    conn = project.connection
    mfg = project.manufacturing

    # Determine segment count based on profile complexity
    num_segs_a = 16 if if_a.profile_type == ProfileType.CIRCLE else 4
    num_segs_b = 16 if if_b.profile_type == ProfileType.CIRCLE else 4
    n = max(num_segs_a, num_segs_b)

    outer_a_2d = _sample_profile_2d(if_a, True, mfg.wall_thickness_mm, mfg.clearance_a_mm, n)
    inner_a_2d = _sample_profile_2d(if_a, False, mfg.wall_thickness_mm, mfg.clearance_a_mm, n)

    outer_b_2d = _sample_profile_2d(if_b, True, mfg.wall_thickness_mm, mfg.clearance_b_mm, n)
    inner_b_2d = _sample_profile_2d(if_b, False, mfg.wall_thickness_mm, mfg.clearance_b_mm, n)

    # Re-sample if counts mismatch
    n = max(len(outer_a_2d), len(outer_b_2d))
    if len(outer_a_2d) != n:
        outer_a_2d = _sample_profile_2d(if_a, True, mfg.wall_thickness_mm, mfg.clearance_a_mm, n)
        inner_a_2d = _sample_profile_2d(if_a, False, mfg.wall_thickness_mm, mfg.clearance_a_mm, n)
    if len(outer_b_2d) != n:
        outer_b_2d = _sample_profile_2d(if_b, True, mfg.wall_thickness_mm, mfg.clearance_b_mm, n)
        inner_b_2d = _sample_profile_2d(if_b, False, mfg.wall_thickness_mm, mfg.clearance_b_mm, n)

    vertices: List[Tuple[float, float, float]] = []

    # Interface A vertices at Z = 0
    for x, y in outer_a_2d:
        vertices.append((x, y, 0.0))
    for x, y in inner_a_2d:
        vertices.append((x, y, 0.0))

    # Interface B transformation (offset_x, offset_y, Z = length, angle_deg)
    ang_rad = math.radians(conn.angle_deg)
    cos_a = math.cos(ang_rad)
    sin_a = math.sin(ang_rad)

    def transform_b(x: float, y: float) -> Tuple[float, float, float]:
        ry = y * cos_a
        rz = y * sin_a
        return (x + conn.offset_x_mm, ry + conn.offset_y_mm, rz + conn.length_mm)

    for x, y in outer_b_2d:
        vertices.append(transform_b(x, y))
    for x, y in inner_b_2d:
        vertices.append(transform_b(x, y))

    faces: List[Tuple[int, int, int]] = []
    for i in range(n):
        next_i = (i + 1) % n

        # Outer wall quad -> 2 triangles
        v_oa1 = i + 1
        v_oa2 = next_i + 1
        v_ob1 = 2 * n + i + 1
        v_ob2 = 2 * n + next_i + 1
        faces.append((v_oa1, v_oa2, v_ob2))
        faces.append((v_oa1, v_ob2, v_ob1))

        # Inner wall quad -> 2 triangles
        v_ia1 = n + i + 1
        v_ia2 = n + next_i + 1
        v_ib1 = 3 * n + i + 1
        v_ib2 = 3 * n + next_i + 1
        faces.append((v_ib1, v_ib2, v_ia2))
        faces.append((v_ib1, v_ia2, v_ia1))

        # Bottom rim ring (Z=0)
        faces.append((v_oa1, v_ia1, v_ia2))
        faces.append((v_oa1, v_ia2, v_oa2))

        # Top rim ring
        faces.append((v_ob1, v_ob2, v_ib2))
        faces.append((v_ob1, v_ib2, v_ib1))

    obj_lines = [
        f"# InterfaceForge OBJ Export for Project {project.project_id}",
        f"# Rev: {project.current_model_revision}",
    ]
    for v in vertices:
        obj_lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}")
    for f in faces:
        obj_lines.append(f"f {f[0]} {f[1]} {f[2]}")

    return "\n".join(obj_lines)


def get_geometry_hash(obj_content: str) -> str:
    """Compute SHA-256 hash string for 3D model geometry payload."""
    return hashlib.sha256(obj_content.encode("utf-8")).hexdigest()


def parse_obj_mesh(
    obj_content: str,
) -> tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    """Read the deterministic local mesh used by offline preview and STL."""
    vertices: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int]] = []
    for raw in obj_content.splitlines():
        parts = raw.split()
        if len(parts) >= 4 and parts[0] == "v":
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif len(parts) >= 4 and parts[0] == "f":
            faces.append((
                int(parts[1].split("/")[0]) - 1,
                int(parts[2].split("/")[0]) - 1,
                int(parts[3].split("/")[0]) - 1,
            ))
    return vertices, faces


def mesh_bounds(obj_content: str) -> Tuple[float, float, float, float, float, float]:
    vertices, _ = parse_obj_mesh(obj_content)
    if not vertices:
        return (0.0,) * 6
    return (
        min(v[0] for v in vertices),
        max(v[0] for v in vertices),
        min(v[1] for v in vertices),
        max(v[1] for v in vertices),
        min(v[2] for v in vertices),
        max(v[2] for v in vertices),
    )


def mesh_volume(obj_content: str) -> float:
    """Return absolute closed-triangle volume in cubic millimetres."""
    vertices, faces = parse_obj_mesh(obj_content)
    total = 0.0
    for a, b, c in faces:
        ax, ay, az = vertices[a]
        bx, by, bz = vertices[b]
        cx, cy, cz = vertices[c]
        total += (
            ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
        ) / 6.0
    return abs(total)


def render_mesh_svg(obj_content: str, job_id: str) -> str:
    """Render a truthful wireframe projection of the exact offline mesh."""
    vertices, faces = parse_obj_mesh(obj_content)
    if not vertices or not faces:
        return "3D preview unavailable in offline mode."
    min_x, max_x, min_y, max_y, min_z, max_z = mesh_bounds(obj_content)
    scale = min(320.0 / max(max_x - min_x, 1.0), 220.0 / max(max_z - min_z, 1.0))

    def point(v: Tuple[float, float, float]) -> str:
        x = 40 + (v[0] - min_x) * scale
        y = 260 - (v[2] - min_z) * scale
        return f"{x:.2f},{y:.2f}"

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img" aria-label="Generated adapter mesh preview">',
        '<rect width="400" height="300" fill="#0d1117"/>',
    ]
    for a, b, c in faces:
        lines.append(
            f'<path d="M {point(vertices[a])} L {point(vertices[b])} L {point(vertices[c])} Z" fill="none" stroke="#00e676" stroke-width="0.7" opacity="0.65"/>'
        )
    lines.append(
        f'<text x="12" y="18" fill="#00e676" font-family="monospace" font-size="11">INTERFACEFORGE 3D PREVIEW - GENERATED MESH</text><text x="12" y="292" fill="#88aa99" font-family="monospace" font-size="10">JOB: {job_id[:12]}</text></svg>'
    )
    return "".join(lines)
