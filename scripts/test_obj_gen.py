import math
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

def generate_adapter_obj(project) -> str:
    """Generate 3D OBJ mesh representation from a Project's canonical geometry specs."""
    if_a = project.interface_a
    if_b = project.interface_b
    conn = project.connection
    mfg = project.manufacturing

    # Helper to get dimension value
    def get_dim(iface, dim_id, default):
        for d in iface.dimensions:
            if d.id == dim_id and math.isfinite(d.value) and d.value > 0:
                return float(d.value)
        return default

    # Sample profile 2D points (outer and inner)
    def sample_profile_points(iface, is_outer, num_segments=16):
        p_type = iface.profile_type
        wall = mfg.wall_thickness_mm
        clearance = mfg.clearance_a_mm if iface == if_a else mfg.clearance_b_mm
        
        pts = []
        if p_type.value == "circle":
            outer_dia = get_dim(iface, "outer_diameter", 50.0)
            eff_dia = (outer_dia + 2*clearance) if is_outer else (outer_dia + 2*clearance - 2*wall)
            r = max(eff_dia / 2.0, 1.0)
            for i in range(num_segments):
                theta = 2.0 * math.pi * i / num_segments
                pts.append((r * math.cos(theta), r * math.sin(theta)))
        elif p_type.value in ("rectangle", "rounded_rectangle"):
            w = get_dim(iface, "width", 50.0)
            h = get_dim(iface, "height", 50.0)
            eff_w = (w + 2*clearance) if is_outer else (w + 2*clearance - 2*wall)
            eff_h = (h + 2*clearance) if is_outer else (h + 2*clearance - 2*wall)
            hw = max(eff_w / 2.0, 1.0)
            hh = max(eff_h / 2.0, 1.0)
            
            # Simple 4-corner profile for rectangle
            pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return pts

    # Sample 2D points for Interface A (z=0) and Interface B (z=length)
    outer_a_2d = sample_profile_points(if_a, is_outer=True)
    inner_a_2d = sample_profile_points(if_a, is_outer=False)
    
    outer_b_2d = sample_profile_points(if_b, is_outer=True)
    inner_b_2d = sample_profile_points(if_b, is_outer=False)

    # Ensure same number of points for lofting
    n = max(len(outer_a_2d), len(outer_b_2d))
    if len(outer_a_2d) != n:
        outer_a_2d = sample_profile_points(if_a, is_outer=True, num_segments=n)
        inner_a_2d = sample_profile_points(if_a, is_outer=False, num_segments=n)
    if len(outer_b_2d) != n:
        outer_b_2d = sample_profile_points(if_b, is_outer=True, num_segments=n)
        inner_b_2d = sample_profile_points(if_b, is_outer=False, num_segments=n)

    vertices = []
    # 1. Outer A (z=0)
    for x, y in outer_a_2d:
        vertices.append((x, y, 0.0))
    # 2. Inner A (z=0)
    for x, y in inner_a_2d:
        vertices.append((x, y, 0.0))

    # Interface B transformation (offset_x, offset_y, z=length, angle_deg)
    ang_rad = math.radians(conn.angle_deg)
    cos_a = math.cos(ang_rad)
    sin_a = math.sin(ang_rad)

    def transform_b(x, y):
        # Rotate around X-axis by angle_deg, then translate by offset and length
        ry = y * cos_a
        rz = y * sin_a
        return (x + conn.offset_x_mm, ry + conn.offset_y_mm, rz + conn.length_mm)

    # 3. Outer B
    for x, y in outer_b_2d:
        vertices.append(transform_b(x, y))
    # 4. Inner B
    for x, y in inner_b_2d:
        vertices.append(transform_b(x, y))

    # Vertex indices offset (1-based in OBJ)
    # Range 1..n: Outer A
    # Range n+1..2n: Inner A
    # Range 2n+1..3n: Outer B
    # Range 3n+1..4n: Inner B

    faces = []
    for i in range(n):
        next_i = (i + 1) % n
        # Outer wall quad (Outer A -> Outer B)
        v_oa1 = i + 1
        v_oa2 = next_i + 1
        v_ob1 = 2*n + i + 1
        v_ob2 = 2*n + next_i + 1
        faces.append((v_oa1, v_oa2, v_ob2))
        faces.append((v_oa1, v_ob2, v_ob1))

        # Inner wall quad (Inner B -> Inner A)
        v_ia1 = n + i + 1
        v_ia2 = n + next_i + 1
        v_ib1 = 3*n + i + 1
        v_ib2 = 3*n + next_i + 1
        faces.append((v_ib1, v_ib2, v_ia2))
        faces.append((v_ib1, v_ia2, v_ia1))

        # Bottom ring (z=0)
        faces.append((v_oa1, v_ia1, v_ia2))
        faces.append((v_oa1, v_ia2, v_oa2))

        # Top ring (z=length)
        faces.append((v_ob1, v_ob2, v_ib2))
        faces.append((v_ob1, v_ib2, v_ib1))

    obj_lines = [f"# InterfaceForge OBJ Export for Project {project.project_id}"]
    for v in vertices:
        obj_lines.append(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}")
    for f in faces:
        obj_lines.append(f"f {f[0]} {f[1]} {f[2]}")

    return "\n".join(obj_lines)

# Quick sanity check for case 1..4
if __name__ == "__main__":
    from app.models.schema import Project, Connection, ConnectionMode, ProfileType, Dimension
    
    for case_i in [1, 2, 3, 4]:
        p = Project(project_id=f"case_{case_i}", project_token="tok_test", current_schema_revision=1)
        if case_i == 1:
            p.interface_a.profile_type = ProfileType.RECTANGLE
            p.interface_b.profile_type = ProfileType.RECTANGLE
        elif case_i == 2:
            p.interface_a.profile_type = ProfileType.CIRCLE
            p.interface_b.profile_type = ProfileType.CIRCLE
        elif case_i == 3:
            p.interface_a.profile_type = ProfileType.CIRCLE
            p.interface_b.profile_type = ProfileType.CIRCLE
            p.connection.mode = ConnectionMode.OFFSET
            p.connection.offset_x_mm = 15.0
        elif case_i == 4:
            p.interface_a.profile_type = ProfileType.CIRCLE
            p.interface_b.profile_type = ProfileType.CIRCLE
            p.connection.mode = ConnectionMode.ANGLED
            p.connection.angle_deg = 10.0
            
        obj_str = generate_adapter_obj(p)
        h = hashlib.sha256(obj_str.encode()).hexdigest()[:8]
        print(f"Case {case_i}: OBJ lines={len(obj_str.splitlines())}, sha={h}")
