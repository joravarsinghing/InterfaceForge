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
from app.services.loft_plan import ensure_loft_plan
from app.services.profile_geometry import fitted_profile_size

COMPILER_VERSION = "1.0.0"


def _validate_generated_kcl(kcl_code: str) -> Optional[ValidationIssue]:
    """Parse and execute complete KCL with the installed Zoo KCL runtime."""
    try:
        import kcl  # type: ignore[import-not-found]
    except Exception as exc:
        return ValidationIssue(
            id="IF-KCL-006",
            message=f"Installed Zoo KCL parser is unavailable: {exc}",
            field="kcl_code",
            recovery_steps=["Install the supported zoo-kcl tooling for the backend runtime."],
        )

    try:
        kcl.parse_code(kcl_code)
        import asyncio
        import threading

        async def _execute() -> object:
            return await kcl.mock_execute_code(kcl_code)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            result = asyncio.run(_execute())
        else:
            result_box: list[object] = []
            error_box: list[BaseException] = []

            def _worker() -> None:
                try:
                    result_box.append(asyncio.run(_execute()))
                except BaseException as worker_error:
                    error_box.append(worker_error)

            worker = threading.Thread(target=_worker)
            worker.start()
            worker.join()
            if error_box:
                raise error_box[0]
            result = result_box[0] if result_box else None

        if result is not True:
            raise RuntimeError(f"Zoo KCL execution returned {result!r}")
    except Exception as exc:
        detail = str(exc).replace("\r", " ").replace("\n", " ")
        return ValidationIssue(
            id="IF-KCL-005",
            message=f"Generated KCL failed Zoo parser validation: {detail}",
            field="kcl_code",
            recovery_steps=["Fix the generated KCL syntax and retry model generation."],
        )
    return None


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
        ("extension_a_mm", conn.extension_a_mm),
        ("extension_b_mm", conn.extension_b_mm),
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


def _kcl_identifier(value: str) -> str:
    """Return a Zoo-style lowerCamelCase identifier from a snake_case name."""
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])

def _generate_section_kcl(points, prefix: str, plane_var: str) -> str:
    """Emit one authoritative closed polyline: absolute start, relative edges, one close."""
    if len(points) < 3:
        raise ValueError("Loft section needs at least three points")
    for a, b in zip(points, points[1:]):
        if math.dist((a.x, a.y), (b.x, b.y)) <= 1e-9:
            raise ValueError("Loft section contains duplicate adjacent points")
    if math.dist((points[-1].x, points[-1].y), (points[0].x, points[0].y)) <= 1e-9:
        raise ValueError("Loft section repeats its first point")
    sketch_name = _kcl_identifier(f"sketch_{prefix}")
    lines = [f"{sketch_name} = startSketchOn({plane_var})", f"  |> startProfile(at = [{points[0].x:.6f}, {points[0].y:.6f}])"]
    for current, following in zip(points, points[1:]):
        lines.append(f"  |> line(end = [{following.x-current.x:.6f}, {following.y-current.y:.6f}])")
    last, first = points[-1], points[0]
    lines.append(f"  |> line(end = [{first.x-last.x:.6f}, {first.y-last.y:.6f}])")
    lines.append("  |> close()")
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

    # 2. Arbitrary closed profiles require an authoritative traced contour.
    for iface_name, iface in [
        ("Interface A", project.interface_a),
        ("Interface B", project.interface_b),
    ]:
        if iface.profile_type in (ProfileType.TRACED_CLOSED, ProfileType.CUSTOM_CLOSED) and (
            iface.traced_outer_contour is None
            or len(iface.traced_outer_contour.points) < 3
            or not iface.traced_outer_contour.is_closed
        ):
            return KCLCompileResult(
                success=False,
                schema_revision=project.current_schema_revision,
                schema_version=project.schema_version,
                errors=[
                    ValidationIssue(
                        id="IF-KCL-001",
                        message=(
                            f"{iface_name} arbitrary closed profile is missing a valid "
                            "authoritative closed contour."
                        ),
                        field=iface_name.lower().replace(" ", "_"),
                        recovery_steps=[
                            "Re-run profile analysis or provide at least three closed contour points."
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
        "// InterfaceForge ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Deterministic KCL Adapter Model",
        f"// Compiler Version: {COMPILER_VERSION}",
        f"// Schema Version: {project.schema_version}",
        f"// Schema Revision: {project.current_schema_revision}",
        "// Units: Millimeters (mm)",
        "",
        "@settings(defaultLengthUnit = mm)",
        "",
        "// --- Interface A Parameters ---",
        f'interfaceAType = "{if_a.profile_type.value}"',
    ]

    if if_a.profile_type == ProfileType.CIRCLE:
        outer_a = _get_dim_val(if_a, "outer_diameter", 50.0)
        kcl_lines.append(f"interfaceAOuterDiameterMm = {outer_a:.3f}")
    else:
        w_a = _get_dim_val(if_a, "width", 50.0)
        h_a = _get_dim_val(if_a, "height", 50.0)
        kcl_lines.append(f"interfaceAWidthMm = {w_a:.3f}")
        kcl_lines.append(f"interfaceAHeightMm = {h_a:.3f}")
        if if_a.profile_type == ProfileType.ROUNDED_RECTANGLE:
            r_a = _get_dim_val(if_a, "corner_radius", 5.0)
            kcl_lines.append(f"interfaceACornerRadiusMm = {r_a:.3f}")

    kcl_lines.append(f"interfaceAClearanceMm = {mfg.clearance_a_mm:.3f}")
    kcl_lines.append("")

    kcl_lines.append("// --- Interface B Parameters ---")
    kcl_lines.append(f'interfaceBType = "{if_b.profile_type.value}"')

    if if_b.profile_type == ProfileType.CIRCLE:
        outer_b = _get_dim_val(if_b, "outer_diameter", 34.5)
        kcl_lines.append(f"interfaceBOuterDiameterMm = {outer_b:.3f}")
    else:
        w_b = _get_dim_val(if_b, "width", 50.0)
        h_b = _get_dim_val(if_b, "height", 50.0)
        kcl_lines.append(f"interfaceBWidthMm = {w_b:.3f}")
        kcl_lines.append(f"interfaceBHeightMm = {h_b:.3f}")
        if if_b.profile_type == ProfileType.ROUNDED_RECTANGLE:
            r_b = _get_dim_val(if_b, "corner_radius", 5.0)
            kcl_lines.append(f"interfaceBCornerRadiusMm = {r_b:.3f}")

    kcl_lines.append(f"interfaceBClearanceMm = {mfg.clearance_b_mm:.3f}")
    kcl_lines.append("")

    kcl_lines.append("// --- Connection & Manufacturing Parameters ---")
    kcl_lines.append(f'connectionMode = "{conn.mode.value}"')
    kcl_lines.append(f"transitionLengthMm = {conn.length_mm:.3f}")
    kcl_lines.append(f"wallThicknessMm = {mfg.wall_thickness_mm:.3f}")
    kcl_lines.append(f"offsetXMm = {conn.offset_x_mm:.3f}")
    kcl_lines.append(f"offsetYMm = {conn.offset_y_mm:.3f}")
    kcl_lines.append(f"angleDeg = {conn.angle_deg:.3f}")
    kcl_lines.append(f"extensionAMm = {conn.extension_a_mm:.3f}")
    kcl_lines.append(f"extensionBMm = {conn.extension_b_mm:.3f}")
    kcl_lines.append("")

    # Construction geometry is entirely driven by the persisted LoftPlan.
    plan = ensure_loft_plan(project)
    kcl_lines.append(f"// LoftPlan hash: {plan.geometry_hash}")
    kcl_lines.append(f"// LoftPlan sections: {len(plan.sections)} points: {plan.point_count}")
    kcl_lines.append(f"// center = [{conn.offset_x_mm:.3f}, {conn.offset_y_mm:.3f}]")
    if conn.mode == ConnectionMode.ANGLED:
        kcl_lines.append(f"// top_plane = offsetPlane(XY, offset = {conn.length_mm:.3f})")
        kcl_lines.append(f"// |> rotate(axis = [1.000, 0.000, 0.000], angle = {conn.angle_deg:.3f}deg)")

    kcl_lines.append("")
    for index, section in enumerate(plan.sections):
        plane = "XY" if index == 0 else f"offsetPlane(XY, offset = {section.z_mm:.3f})"
        kcl_lines.append(_generate_section_kcl(section.outer, f"outer_{index}", plane))
        kcl_lines.append(_generate_section_kcl(section.inner, f"inner_{index}", plane))
        kcl_lines.append("")

    outer_names = ", ".join(f"sketchOuter{i}" for i in range(len(plan.sections)))
    inner_names = ", ".join(f"sketchInner{i}" for i in range(len(plan.sections)))
    kcl_lines.append(
        f"outerSurface = loft([{outer_names}], bodyType = \"surface\")"
    )
    kcl_lines.append(
        f"innerSurface = loft([{inner_names}], bodyType = \"surface\")"
    )
    # Zoo rejects a surface loft between coplanar profiles. Keep rim contours
    # exact, but place only the duplicate rim profiles 0.001 mm outside the
    # end planes so the rim loft has a valid non-zero span.
    rim_extension_mm = 0.001
    last_index = len(plan.sections) - 1
    kcl_lines.append(
        _generate_section_kcl(
            plan.sections[0].inner,
            "inner_rim_bottom",
            f"offsetPlane(XY, offset = {-rim_extension_mm:.3f})",
        )
    )
    kcl_lines.append(
        _generate_section_kcl(
            plan.sections[last_index].inner,
            "inner_rim_top",
            f"offsetPlane(XY, offset = {plan.sections[last_index].z_mm + rim_extension_mm:.3f})",
        )
    )
    kcl_lines.append(
        "bottomRim = loft([sketchOuter0, sketchInnerRimBottom], bodyType = \"surface\")"
    )
    kcl_lines.append(
        f"topRim = loft([sketchOuter{last_index}, sketchInnerRimTop], bodyType = \"surface\")"
    )
    kcl_lines.append(
        "adapterModel = joinSurfaces([outerSurface, innerSurface, bottomRim, topRim])"
    )
    kcl_lines.append("")
    kcl_code = "\n".join(kcl_lines)

    parser_issue = _validate_generated_kcl(kcl_code)
    if parser_issue:
        return KCLCompileResult(
            success=False,
            schema_revision=project.current_schema_revision,
            schema_version=project.schema_version,
            errors=[parser_issue],
            warnings=conn_val.warnings,
        )
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

    with open(filepath, "w", encoding="utf-8", newline="") as f:
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




