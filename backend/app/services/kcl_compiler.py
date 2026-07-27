"""Deterministic KCL Compiler and Service Layer (Stage S5A).

Converts validated canonical project data into deterministic, readable KCL code
without calling Zoo per ADR-001 and ADR-002.
"""

import hashlib
import math
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.schema import (
    ConnectionMode,
    Interface,
    ProfileType,
    Project,
    ValidationIssue,
)
from app.services.connection_validation import validate_connection_and_manufacturing

COMPILER_VERSION = "1.0.0"


class KCLCompileResult(BaseModel):
    """Result container for KCL compilation output."""

    success: bool
    kcl_code: Optional[str] = None
    artifact_ref: Optional[str] = None
    compiler_version: str = COMPILER_VERSION
    schema_revision: int
    schema_version: str = "0.1"
    kcl_hash: Optional[str] = None
    preview_snippet: Optional[str] = None
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)


def _get_dim_val(interface: Interface, dim_id: str, default: float) -> float:
    """Helper to extract a positive finite dimension value from an interface."""
    for d in interface.dimensions:
        if d.id == dim_id and math.isfinite(d.value) and d.value > 0:
            return float(d.value)
    return default


def _validate_finite_numbers(project: Project) -> List[ValidationIssue]:
    """Validates that all geometric numbers in the project are finite numbers."""
    issues: List[ValidationIssue] = []

    conn = project.connection
    mfg = project.manufacturing

    num_checks = [
        ("length_mm", conn.length_mm),
        ("wall_thickness_mm", mfg.wall_thickness_mm),
        ("clearance_a_mm", mfg.clearance_a_mm),
        ("clearance_b_mm", mfg.clearance_b_mm),
        ("offset_x_mm", conn.offset_x_mm),
        ("offset_y_mm", conn.offset_y_mm),
        ("angle_deg", conn.angle_deg),
    ]

    for field_name, val in num_checks:
        if not math.isfinite(val):
            issues.append(
                ValidationIssue(
                    id="IF-KCL-002",
                    message=f"Parameter '{field_name}' must be a finite numerical value.",
                    field=field_name,
                    recovery_steps=["Provide a valid finite number for all parameters."],
                )
            )

    # Check interface dimensions
    for iface_name, iface in [
        ("Interface A", project.interface_a),
        ("Interface B", project.interface_b),
    ]:
        for d in iface.dimensions:
            if not math.isfinite(d.value):
                issues.append(
                    ValidationIssue(
                        id="IF-KCL-002",
                        message=(
                            f"{iface_name} dimension '{d.id}' must be a finite numerical value."
                        ),
                        field=f"{iface_name.lower().replace(' ', '_')}.{d.id}",
                        recovery_steps=[
                            "Ensure all interface dimensions have finite numeric values."
                        ],
                    )
                )

    return issues


def _generate_sketch_kcl(
    iface: Interface,
    prefix: str,
    plane_var: str,
    offset_x: float,
    offset_y: float,
    is_outer: bool,
    clearance: float,
    wall_thickness: float,
) -> str:
    """Generates KCL code string for a single profile sketch."""
    p_type = iface.profile_type
    lines: List[str] = []

    if p_type == ProfileType.CIRCLE:
        outer_dia = _get_dim_val(iface, "outer_diameter", 50.0)
        if prefix.startswith("a"):
            eff_dia = (
                outer_dia + (2.0 * clearance)
                if is_outer
                else outer_dia + (2.0 * clearance) - (2.0 * wall_thickness)
            )
        else:
            eff_dia = (
                outer_dia - (2.0 * clearance)
                if is_outer
                else outer_dia - (2.0 * clearance) - (2.0 * wall_thickness)
            )

        radius = eff_dia / 2.0
        lines.append(f"const sketch_{prefix} = startSketchOn({plane_var})")
        lines.append(
            f"  |> circle(center = [{offset_x:.3f}, {offset_y:.3f}], radius = {radius:.3f})"
        )

    elif p_type in (ProfileType.RECTANGLE, ProfileType.ROUNDED_RECTANGLE):
        w = _get_dim_val(iface, "width", 50.0)
        h = _get_dim_val(iface, "height", 50.0)

        if prefix.startswith("a"):
            eff_w = (
                w + (2.0 * clearance)
                if is_outer
                else w + (2.0 * clearance) - (2.0 * wall_thickness)
            )
            eff_h = (
                h + (2.0 * clearance)
                if is_outer
                else h + (2.0 * clearance) - (2.0 * wall_thickness)
            )
        else:
            eff_w = (
                w - (2.0 * clearance)
                if is_outer
                else w - (2.0 * clearance) - (2.0 * wall_thickness)
            )
            eff_h = (
                h - (2.0 * clearance)
                if is_outer
                else h - (2.0 * clearance) - (2.0 * wall_thickness)
            )

        half_w = eff_w / 2.0
        half_h = eff_h / 2.0

        if p_type == ProfileType.RECTANGLE:
            lines.append(f"const sketch_{prefix} = startSketchOn({plane_var})")
            lines.append(
                f"  |> startProfileAt([{offset_x - half_w:.3f}, {offset_y - half_h:.3f}], %)"
            )
            lines.append(f"  |> lineTo([{offset_x + half_w:.3f}, {offset_y - half_h:.3f}], %)")
            lines.append(f"  |> lineTo([{offset_x + half_w:.3f}, {offset_y + half_h:.3f}], %)")
            lines.append(f"  |> lineTo([{offset_x - half_w:.3f}, {offset_y + half_h:.3f}], %)")
            lines.append("  |> close(%)")

        elif p_type == ProfileType.ROUNDED_RECTANGLE:
            r = _get_dim_val(iface, "corner_radius", 5.0)
            r = min(r, half_w * 0.8, half_h * 0.8)  # prevent over-filleting
            lines.append(f"const sketch_{prefix} = startSketchOn({plane_var})")
            lines.append(
                f"  |> startProfileAt([{offset_x - half_w + r:.3f}, {offset_y - half_h:.3f}], %)"
            )
            lines.append(f"  |> lineTo([{offset_x + half_w - r:.3f}, {offset_y - half_h:.3f}], %)")
            lines.append(
                f"  |> tangentialArcTo([{offset_x + half_w:.3f}, {offset_y - half_h + r:.3f}], %)"
            )
            lines.append(f"  |> lineTo([{offset_x + half_w:.3f}, {offset_y + half_h - r:.3f}], %)")
            lines.append(
                f"  |> tangentialArcTo([{offset_x + half_w - r:.3f}, {offset_y + half_h:.3f}], %)"
            )
            lines.append(f"  |> lineTo([{offset_x - half_w + r:.3f}, {offset_y + half_h:.3f}], %)")
            lines.append(
                f"  |> tangentialArcTo([{offset_x - half_w:.3f}, {offset_y + half_h - r:.3f}], %)"
            )
            lines.append(f"  |> lineTo([{offset_x - half_w:.3f}, {offset_y - half_h + r:.3f}], %)")
            lines.append(
                f"  |> tangentialArcTo([{offset_x - half_w + r:.3f}, {offset_y - half_h:.3f}], %)"
            )
            lines.append("  |> close(%)")

    return "\n".join(lines)


def compile_project_to_kcl(
    project: Project, artifacts_dir: Optional[str] = None
) -> KCLCompileResult:
    """Compiles canonical project schema into deterministic KCL code.

    Enforces all ADR-001, ADR-002, and geometric requirements.
    Does NOT execute Zoo API and does NOT set model status to current.
    """
    # 1. Prerequisite approval check
    if not project.interface_a.approved:
        return KCLCompileResult(
            success=False,
            schema_revision=project.current_schema_revision,
            schema_version=project.schema_version,
            errors=[
                ValidationIssue(
                    id="IF-KCL-003",
                    message="Interface A must be approved before KCL compilation.",
                    field="interface_a",
                    recovery_steps=["Approve Interface A profile in step 1."],
                )
            ],
        )

    if not project.interface_b.approved:
        return KCLCompileResult(
            success=False,
            schema_revision=project.current_schema_revision,
            schema_version=project.schema_version,
            errors=[
                ValidationIssue(
                    id="IF-KCL-003",
                    message="Interface B must be approved before KCL compilation.",
                    field="interface_b",
                    recovery_steps=["Approve Interface B profile in step 2."],
                )
            ],
        )

    # 2. Unsupported profile type check (traced_closed)
    for iface_name, iface in [
        ("Interface A", project.interface_a),
        ("Interface B", project.interface_b),
    ]:
        if iface.profile_type == ProfileType.TRACED_CLOSED:
            return KCLCompileResult(
                success=False,
                schema_revision=project.current_schema_revision,
                schema_version=project.schema_version,
                errors=[
                    ValidationIssue(
                        id="IF-KCL-001",
                        message=(
                            f"{iface_name} profile type 'traced_closed' "
                            "is not supported by KCL compiler."
                        ),
                        field=iface_name.lower().replace(" ", "_"),
                        recovery_steps=[
                            "Re-edit profile to circle, rectangle, or rounded rectangle."
                        ],
                    )
                ],
            )

    # 3. Connection and manufacturing validation check
    conn_val = validate_connection_and_manufacturing(
        project.interface_a, project.interface_b, project.connection, project.manufacturing
    )
    if not conn_val.is_valid:
        return KCLCompileResult(
            success=False,
            schema_revision=project.current_schema_revision,
            schema_version=project.schema_version,
            errors=[
                ValidationIssue(
                    id="IF-KCL-004",
                    message="Connection validation failed before compilation.",
                    field="connection",
                    recovery_steps=[err.message for err in conn_val.blocking_errors],
                )
            ]
            + conn_val.blocking_errors,
            warnings=conn_val.warnings,
        )

    # 4. Finite numbers check
    finite_issues = _validate_finite_numbers(project)
    if finite_issues:
        return KCLCompileResult(
            success=False,
            schema_revision=project.current_schema_revision,
            schema_version=project.schema_version,
            errors=finite_issues,
            warnings=conn_val.warnings,
        )

    # Build KCL code deterministically
    conn = project.connection
    mfg = project.manufacturing
    if_a = project.interface_a
    if_b = project.interface_b

    kcl_lines: List[str] = [
        "// InterfaceForge — Deterministic KCL Adapter Model",
        f"// Compiler Version: {COMPILER_VERSION}",
        f"// Schema Version: {project.schema_version}",
        f"// Schema Revision: {project.current_schema_revision}",
        "// Units: Millimeters (mm)",
        "",
        "@settings(defaultLengthUnit = mm)",
        "",
        "// --- Interface A Parameters ---",
        f'const interface_a_type = "{if_a.profile_type.value}"',
    ]

    if if_a.profile_type == ProfileType.CIRCLE:
        outer_a = _get_dim_val(if_a, "outer_diameter", 50.0)
        kcl_lines.append(f"const interface_a_outer_diameter_mm = {outer_a:.3f}")
    else:
        w_a = _get_dim_val(if_a, "width", 50.0)
        h_a = _get_dim_val(if_a, "height", 50.0)
        kcl_lines.append(f"const interface_a_width_mm = {w_a:.3f}")
        kcl_lines.append(f"const interface_a_height_mm = {h_a:.3f}")
        if if_a.profile_type == ProfileType.ROUNDED_RECTANGLE:
            r_a = _get_dim_val(if_a, "corner_radius", 5.0)
            kcl_lines.append(f"const interface_a_corner_radius_mm = {r_a:.3f}")

    kcl_lines.append(f"const interface_a_clearance_mm = {mfg.clearance_a_mm:.3f}")
    kcl_lines.append("")

    kcl_lines.append("// --- Interface B Parameters ---")
    kcl_lines.append(f'const interface_b_type = "{if_b.profile_type.value}"')

    if if_b.profile_type == ProfileType.CIRCLE:
        outer_b = _get_dim_val(if_b, "outer_diameter", 34.5)
        kcl_lines.append(f"const interface_b_outer_diameter_mm = {outer_b:.3f}")
    else:
        w_b = _get_dim_val(if_b, "width", 50.0)
        h_b = _get_dim_val(if_b, "height", 50.0)
        kcl_lines.append(f"const interface_b_width_mm = {w_b:.3f}")
        kcl_lines.append(f"const interface_b_height_mm = {h_b:.3f}")
        if if_b.profile_type == ProfileType.ROUNDED_RECTANGLE:
            r_b = _get_dim_val(if_b, "corner_radius", 5.0)
            kcl_lines.append(f"const interface_b_corner_radius_mm = {r_b:.3f}")

    kcl_lines.append(f"const interface_b_clearance_mm = {mfg.clearance_b_mm:.3f}")
    kcl_lines.append("")

    kcl_lines.append("// --- Connection & Manufacturing Parameters ---")
    kcl_lines.append(f'const connection_mode = "{conn.mode.value}"')
    kcl_lines.append(f"const transition_length_mm = {conn.length_mm:.3f}")
    kcl_lines.append(f"const wall_thickness_mm = {mfg.wall_thickness_mm:.3f}")
    kcl_lines.append(f"const offset_x_mm = {conn.offset_x_mm:.3f}")
    kcl_lines.append(f"const offset_y_mm = {conn.offset_y_mm:.3f}")
    kcl_lines.append(f"const angle_deg = {conn.angle_deg:.3f}")
    kcl_lines.append("")

    # Construction geometry planes and sketches
    kcl_lines.append("// --- 3D Geometry Construction ---")
    base_plane = "'XY'"

    if conn.mode == ConnectionMode.ANGLED and abs(conn.angle_deg) > 0.0:
        rad = math.radians(conn.angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        top_orig = (
            f"origin = [{conn.offset_x_mm:.3f}, {conn.offset_y_mm:.3f}, {conn.length_mm:.3f}]"
        )
        top_axes = f"xAxis = [1.0, 0.0, 0.0], yAxis = [0.0, {cos_a:.5f}, {sin_a:.5f}]"
        kcl_lines.append(f"const top_plane = plane({top_orig}, {top_axes})")
        top_plane_var = "top_plane"
        top_offset_x = 0.0
        top_offset_y = 0.0
    else:
        kcl_lines.append(f"const top_plane = offsetPlane('XY', offset = {conn.length_mm:.3f})")
        top_plane_var = "top_plane"
        top_offset_x = conn.offset_x_mm
        top_offset_y = conn.offset_y_mm

    kcl_lines.append("")
    kcl_lines.append("// Outer Profiles")
    kcl_lines.append(
        _generate_sketch_kcl(
            if_a, "outer_a", base_plane, 0.0, 0.0, True, mfg.clearance_a_mm, mfg.wall_thickness_mm
        )
    )
    kcl_lines.append(
        _generate_sketch_kcl(
            if_b,
            "outer_b",
            top_plane_var,
            top_offset_x,
            top_offset_y,
            True,
            mfg.clearance_b_mm,
            mfg.wall_thickness_mm,
        )
    )
    kcl_lines.append("")
    kcl_lines.append("const outer_solid = loft([sketch_outer_a, sketch_outer_b])")

    kcl_lines.append("")
    kcl_lines.append("// Inner Profiles")
    kcl_lines.append(
        _generate_sketch_kcl(
            if_a, "inner_a", base_plane, 0.0, 0.0, False, mfg.clearance_a_mm, mfg.wall_thickness_mm
        )
    )
    kcl_lines.append(
        _generate_sketch_kcl(
            if_b,
            "inner_b",
            top_plane_var,
            top_offset_x,
            top_offset_y,
            False,
            mfg.clearance_b_mm,
            mfg.wall_thickness_mm,
        )
    )
    kcl_lines.append("")
    kcl_lines.append("const inner_void = loft([sketch_inner_a, sketch_inner_b])")
    kcl_lines.append("")
    kcl_lines.append("const adapter_model = subtract(outer_solid, tools = [inner_void])")
    kcl_lines.append("")

    kcl_code = "\n".join(kcl_lines)

    # Compute deterministic SHA256 hash
    kcl_bytes = kcl_code.encode("utf-8")
    kcl_hash = hashlib.sha256(kcl_bytes).hexdigest()

    # Save to artifacts directory
    if artifacts_dir is None:
        artifacts_dir = os.path.join(os.getcwd(), "artifacts")

    os.makedirs(artifacts_dir, exist_ok=True)
    filename = (
        f"kcl_{project.project_id[:8]}_rev{project.current_schema_revision}_{kcl_hash[:8]}.kcl"
    )
    filepath = os.path.join(artifacts_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(kcl_code)

    artifact_ref = f"artifacts/{filename}"

    # Preview snippet (first 35 lines)
    preview_lines = kcl_lines[:35]
    preview_snippet = "\n".join(preview_lines)

    return KCLCompileResult(
        success=True,
        kcl_code=kcl_code,
        artifact_ref=artifact_ref,
        compiler_version=COMPILER_VERSION,
        schema_revision=project.current_schema_revision,
        schema_version=project.schema_version,
        kcl_hash=kcl_hash,
        preview_snippet=preview_snippet,
        warnings=conn_val.warnings,
    )
