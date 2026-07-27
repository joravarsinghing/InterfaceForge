import struct
import re
import math
from typing import Dict, Any, Tuple

def parse_and_validate_stl(file_bytes: bytes) -> Dict[str, Any]:
    """Parse and validate STL file (binary or ASCII).
    
    Returns dict with keys:
    - is_valid: bool
    - facet_count: int
    - bounding_box: Optional[Tuple[float, float, float, float, float, float]] (min_x, max_x, min_y, max_y, min_z, max_z)
    - dimensions_mm: Optional[Tuple[float, float, float]] (dx, dy, dz)
    - error: str
    """
    if not file_bytes or len(file_bytes) == 0:
        return {"is_valid": False, "facet_count": 0, "bounding_box": None, "dimensions_mm": None, "error": "Empty STL file (0 bytes)."}

    # Check for ASCII STL
    text_sample = file_bytes[:512].decode("utf-8", errors="ignore").lstrip()
    is_ascii = text_sample.lower().startswith("solid") and b"facet" in file_bytes.lower()

    vertices = []
    facet_count = 0

    if is_ascii:
        text = file_bytes.decode("utf-8", errors="ignore")
        # Check for empty ASCII STL solid/endsolid
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        facet_matches = re.findall(r"facet\s+normal\s+([^\n]+)", text, re.IGNORECASE)
        facet_count = len(facet_matches)
        if facet_count == 0:
            return {"is_valid": False, "facet_count": 0, "bounding_box": None, "dimensions_mm": None, "error": "ASCII STL contains no facets (empty solid/endsolid)."}
        
        # Extract vertex coordinates
        v_matches = re.findall(r"vertex\s+([\-0-9\.eE\+]+)\s+([\-0-9\.eE\+]+)\s+([\-0-9\.eE\+]+)", text, re.IGNORECASE)
        for vx, vy, vz in v_matches:
            try:
                vertices.append((float(vx), float(vy), float(vz)))
            except ValueError:
                pass
    else:
        # Binary STL validation
        if len(file_bytes) < 84:
            return {"is_valid": False, "facet_count": 0, "bounding_box": None, "dimensions_mm": None, "error": "Binary STL header incomplete (< 84 bytes)."}
        
        header = file_bytes[:80]
        facet_count = struct.unpack("<I", file_bytes[80:84])[0]
        if facet_count == 0:
            return {"is_valid": False, "facet_count": 0, "bounding_box": None, "dimensions_mm": None, "error": "Binary STL header specifies 0 facets."}
        
        expected_size = 84 + (facet_count * 50)
        if len(file_bytes) < expected_size:
            return {"is_valid": False, "facet_count": facet_count, "bounding_box": None, "dimensions_mm": None, "error": f"Binary STL size mismatch (expected {expected_size} bytes, got {len(file_bytes)})."}
        
        offset = 84
        for _ in range(facet_count):
            # 12 floats: normal(3), v1(3), v2(3), v3(3)
            data = struct.unpack("<12fH", file_bytes[offset:offset+50])
            vertices.append((data[3], data[4], data[5]))
            vertices.append((data[6], data[7], data[8]))
            vertices.append((data[9], data[10], data[11]))
            offset += 50

    if not vertices:
        return {"is_valid": False, "facet_count": facet_count, "bounding_box": None, "dimensions_mm": None, "error": "Failed to extract valid vertices from STL."}

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
        return {"is_valid": False, "facet_count": facet_count, "bounding_box": None, "dimensions_mm": None, "error": "STL bounding box contains non-finite dimensions."}

    if dx == 0 and dy == 0 and dz == 0:
        return {"is_valid": False, "facet_count": facet_count, "bounding_box": (min_x, max_x, min_y, max_y, min_z, max_z), "dimensions_mm": (dx, dy, dz), "error": "STL bounding box is zero-volume point."}

    return {
        "is_valid": True,
        "facet_count": facet_count,
        "bounding_box": (min_x, max_x, min_y, max_y, min_z, max_z),
        "dimensions_mm": (round(dx, 3), round(dy, 3), round(dz, 3)),
        "error": "",
    }


def parse_and_validate_step(file_bytes: bytes) -> Dict[str, Any]:
    """Parse and validate STEP (ISO 10303-21) file for real body/solid content.
    
    Returns dict with keys:
    - is_valid: bool
    - entity_count: int
    - solid_entities: List[str]
    - error: str
    """
    if not file_bytes or len(file_bytes) == 0:
        return {"is_valid": False, "entity_count": 0, "solid_entities": [], "error": "Empty STEP file (0 bytes)."}

    text = file_bytes.decode("utf-8", errors="ignore")
    if "ISO-10303-21;" not in text or "END-ISO-10303-21;" not in text:
        return {"is_valid": False, "entity_count": 0, "solid_entities": [], "error": "STEP file missing ISO-10303-21 start/end headers."}

    if "DATA;" not in text or "ENDSEC;" not in text:
        return {"is_valid": False, "entity_count": 0, "solid_entities": [], "error": "STEP file missing DATA section."}

    # Extract DATA section
    data_start = text.find("DATA;")
    data_end = text.find("ENDSEC;", data_start)
    if data_start == -1 or data_end == -1:
        return {"is_valid": False, "entity_count": 0, "solid_entities": [], "error": "STEP DATA section delimiters not found."}

    data_section = text[data_start:data_end]
    entities = re.findall(r"#\d+\s*=\s*([A-Za-z0-9_]+)", data_section)
    entity_count = len(entities)

    if entity_count == 0:
        return {"is_valid": False, "entity_count": 0, "solid_entities": [], "error": "STEP DATA section contains 0 entities (header-only file)."}

    # Solid & surface body indicators
    body_types = [
        "MANIFOLD_SOLID_BREP",
        "FACETED_BREP",
        "CLOSED_SHELL",
        "OPEN_SHELL",
        "ADVANCED_FACE",
        "FACE_SURFACE",
        "SHELL_BASED_SURFACE_MODEL",
        "GEOMETRIC_SET",
    ]
    found_solids = [e for e in entities if e in body_types]

    if not found_solids:
        # Check if there are CARTESIAN_POINT and DIRECTION entities representing 3D geometry
        geom_types = ["CARTESIAN_POINT", "DIRECTION", "AXIS2_PLACEMENT_3D"]
        found_geom = [e for e in entities if e in geom_types]
        if not found_geom:
            return {"is_valid": False, "entity_count": entity_count, "solid_entities": [], "error": "STEP DATA section contains no solid body or 3D geometry entities."}

    return {
        "is_valid": True,
        "entity_count": entity_count,
        "solid_entities": found_solids,
        "error": "",
    }

# Test with dummy samples
if __name__ == "__main__":
    empty_ascii_stl = b"solid test\nendsolid test\n"
    print("Empty ASCII STL test:", parse_and_validate_stl(empty_ascii_stl))

    empty_step = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    print("Empty STEP test:", parse_and_validate_step(empty_step))
