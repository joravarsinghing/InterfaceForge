"""3D Geometry Generator for InterfaceForge (Stage S8.1).

Converts canonical project geometry specifications into deterministic 3D Wavefront OBJ mesh
representations for downstream STL and STEP conversions via Zoo File Format API
per ADR-001 and Stage S8.1.
"""

import hashlib
import math
from typing import List, Sequence, Tuple

from app.models.schema import Interface, ProfileType, Project
from app.services.loft_plan import ensure_loft_plan
from app.services.contour_loft import align_contours_with_diagnostics

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
    num_segments: int = 32,
) -> List[Tuple[float, float]]:
    """Return a continuous CCW perimeter, seam-anchored at the +X midpoint."""
    count = max(int(num_segments), 4)
    p_type = iface.profile_type
    if iface.traced_outer_contour is not None or p_type in (ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED):
        contour = iface.traced_outer_contour
        if contour is None or len(contour.points) < 3:
            raise ValueError('Approved custom_closed profile has no authoritative outer contour.')
        points = normalize_contour([(point.x, point.y) for point in contour.points])
        if is_outer:
            return resample_closed(points, count)
        return resample_closed(inward_offset(points, wall_thickness + clearance), count)
    if p_type == ProfileType.CIRCLE:
        diameter = _get_dim_val(iface, "outer_diameter", 50.0)
        effective = diameter + 2.0 * clearance
        if not is_outer:
            effective -= 2.0 * wall_thickness
        radius = max(effective / 2.0, 1.0)
        return [
            (
                radius * math.cos(2.0 * math.pi * i / count),
                radius * math.sin(2.0 * math.pi * i / count),
            )
            for i in range(count)
        ]

    width = _get_dim_val(iface, "width", 50.0)
    height = _get_dim_val(iface, "height", 50.0)
    if is_outer:
        width += 2.0 * clearance
        height += 2.0 * clearance
    else:
        width += 2.0 * clearance - 2.0 * wall_thickness
        height += 2.0 * clearance - 2.0 * wall_thickness
    hw, hh = max(width / 2.0, 1.0), max(height / 2.0, 1.0)

    if p_type == ProfileType.RECTANGLE:
        path = [(hw, 0.0), (hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
    else:
        radius = min(_get_dim_val(iface, "corner_radius", 5.0), hw * 0.8, hh * 0.8)
        if radius <= 1e-9:
            path = [(hw, 0.0), (hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
        else:
            path = [(hw, 0.0), (hw, hh - radius)]
            corners = (
                (0.0, math.pi / 2.0, hw - radius, hh - radius),
                (math.pi / 2.0, math.pi, -hw + radius, hh - radius),
                (math.pi, 3.0 * math.pi / 2.0, -hw + radius, -hh + radius),
                (3.0 * math.pi / 2.0, 2.0 * math.pi, hw - radius, -hh + radius),
            )
            for start, end, cx, cy in corners:
                for j in range(1, 5):
                    theta = start + (end - start) * j / 4.0
                    path.append((cx + radius * math.cos(theta), cy + radius * math.sin(theta)))
            path.append((hw, 0.0))
    return _resample_closed_polyline(path, count)


def _resample_closed_polyline(
    points: Sequence[Tuple[float, float]], count: int
) -> List[Tuple[float, float]]:
    """Resample a closed path at equal arc-length intervals."""
    clean: List[Tuple[float, float]] = []
    for point in points:
        if not clean or math.dist(clean[-1], point) > 1e-9:
            clean.append(point)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= 1e-9:
        clean.pop()
    cumulative = [0.0]
    for i, point in enumerate(clean):
        cumulative.append(cumulative[-1] + math.dist(point, clean[(i + 1) % len(clean)]))
    perimeter = cumulative[-1]
    result: List[Tuple[float, float]] = []
    for sample in range(count):
        distance = perimeter * sample / count
        segment = next(i for i in range(len(clean)) if cumulative[i + 1] >= distance)
        span = cumulative[segment + 1] - cumulative[segment]
        fraction = (distance - cumulative[segment]) / span if span else 0.0
        start, end = clean[segment], clean[(segment + 1) % len(clean)]
        result.append(
            (start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction)
        )
    return result


def ring_signed_area(ring: Sequence[Tuple[float, float]]) -> float:
    """Return signed area; positive rings are counter-clockwise."""
    return 0.5 * sum(
        ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
        for i in range(len(ring))
    )


def _segments_intersect(a, b, c, d) -> bool:
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return orient(a, b, c) * orient(a, b, d) < -1e-9 and orient(c, d, a) * orient(c, d, b) < -1e-9


def ring_is_simple(ring: Sequence[Tuple[float, float]]) -> bool:
    """Return False for non-adjacent crossing edges."""
    for i in range(len(ring)):
        for j in range(i + 1, len(ring)):
            if j in (i, (i + 1) % len(ring), (i - 1) % len(ring)):
                continue
            if _segments_intersect(
                ring[i], ring[(i + 1) % len(ring)], ring[j], ring[(j + 1) % len(ring)]
            ):
                return False
    return True


def align_ring_correspondence(
    source: Sequence[Tuple[float, float]],
    target: Sequence[Tuple[float, float]],
    preserve_zero_rotation: bool = False,
) -> List[Tuple[float, float]]:
    """Compatibility wrapper around the validated contour correspondence search."""
    aligned, _diagnostics = align_contours_with_diagnostics(
        source, target, coaxial=preserve_zero_rotation
    )
    return aligned


def generate_adapter_obj(project: Project) -> str:
    """Generate the offline mock mesh from the exact persisted LoftPlan."""
    global _LOCAL_OBJ_CALL_COUNT
    _LOCAL_OBJ_CALL_COUNT += 1
    if _PROHIBIT_LOCAL_OBJ_GENERATION:
        raise RuntimeError("PRODUCTION EXPORT VIOLATION: Local generate_adapter_obj() called in production export path per ADR-001/S8.2.")
    plan = ensure_loft_plan(project)
    n = plan.point_count
    vertices: List[Tuple[float, float, float]] = []
    for section in plan.sections:
        vertices.extend((p.x, p.y, section.z_mm) for p in section.outer)
        vertices.extend((p.x, p.y, section.z_mm) for p in section.inner)
    faces: List[Tuple[int, int, int]] = []
    rings = len(plan.sections)
    for k in range(rings - 1):
        oa, ob = k * 2 * n, (k + 1) * 2 * n
        ia, ib = oa + n, ob + n
        for i in range(n):
            j = (i + 1) % n
            faces.extend([(oa+i+1, oa+j+1, ob+j+1), (oa+i+1, ob+j+1, ob+i+1)])
            faces.extend([(ib+i+1, ib+j+1, ia+j+1), (ib+i+1, ia+j+1, ia+i+1)])
        if k == 0:
            for i in range(n):
                j = (i + 1) % n
                faces.extend([(i+1, n+i+1, n+j+1), (i+1, n+j+1, j+1)])
        if k == rings - 2:
            for i in range(n):
                j = (i + 1) % n
                faces.extend([(ob+i+1, ob+j+1, ib+j+1), (ob+i+1, ib+j+1, ib+i+1)])
    lines = [f"# InterfaceForge OBJ Export for Project {project.project_id}", f"# LoftPlan hash={plan.geometry_hash} sections={len(plan.sections)} points={n}", f"# CORRESPONDENCE outer shift={plan.outer_shift} reversed={plan.outer_reversed}", f"# CORRESPONDENCE inner shift={plan.inner_shift} reversed={plan.inner_reversed}"]
    lines.extend(f"# CORRESPONDENCE_LINE outer {i} {a.x:.6f} {a.y:.6f} -> {b.x:.6f} {b.y:.6f}" for i, (a, b) in enumerate(zip(plan.outer_a, plan.outer_b)))
    lines.extend(f"v {x:.6f} {y:.6f} {z:.6f}" for x,y,z in vertices)
    lines.extend(f"f {a} {b} {c}" for a,b,c in faces)
    return "\n".join(lines)
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
            faces.append(
                (
                    int(parts[1].split("/")[0]) - 1,
                    int(parts[2].split("/")[0]) - 1,
                    int(parts[3].split("/")[0]) - 1,
                )
            )
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
    """Render the exact mesh with an aspect-preserving X/Y/Z isometric projection."""
    vertices, faces = parse_obj_mesh(obj_content)
    if not vertices or not faces:
        return "3D preview unavailable in offline mode."

    def project(vertex: Tuple[float, float, float]) -> Tuple[float, float]:
        x, y, z = vertex
        return (x - 0.62 * y, z - 0.36 * y)

    projected = [project(vertex) for vertex in vertices]
    min_x = min(point[0] for point in projected)
    max_x = max(point[0] for point in projected)
    min_y = min(point[1] for point in projected)
    max_y = max(point[1] for point in projected)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    scale = min(340.0 / width, 240.0 / height)
    offset_x = (400.0 - width * scale) / 2.0
    offset_y = (300.0 - height * scale) / 2.0

    def point(vertex: Tuple[float, float, float]) -> str:
        px, py = project(vertex)
        return f"{offset_x + (px - min_x) * scale:.2f},{offset_y + (max_y - py) * scale:.2f}"

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img" aria-label="Generated adapter mesh preview">',  # noqa: E501
        '<rect width="400" height="300" fill="#0d1117"/>',
    ]
    for a, b, c in faces:
        lines.append(
            f'<path d="M {point(vertices[a])} L {point(vertices[b])} L {point(vertices[c])} Z" fill="#238636" fill-opacity="0.18" stroke="#3fb950" stroke-width="0.7" opacity="0.8"/>'  # noqa: E501
        )
    lines.append(
        f'<text x="12" y="18" fill="#3fb950" font-family="monospace" font-size="11">INTERFACEFORGE 3D PREVIEW - ISOMETRIC MESH</text><text x="12" y="292" fill="#88aa99" font-family="monospace" font-size="10">JOB: {job_id[:12]}</text></svg>'  # noqa: E501
    )
    return "".join(lines)



