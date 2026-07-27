"""Live End-to-End Proof Suite for Stage S8.3 — Zoo-Native KCL Export.

Tests live Zoo-native STL & STEP export for 4 required test cases:
1. Simple Plate (circular-to-circular coaxial, identical dimensions)
2. Circular Coaxial Adapter (circular-to-circular coaxial, different dimensions)
3. Circular Offset Adapter (circular-to-circular with offset X/Y)
4. Limited-Angle Adapter (angled connection mode)
"""

import asyncio
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.models.schema import (
    Connection,
    ConnectionMode,
    Dimension,
    Interface,
    Manufacturing,
    ProfileType,
    Project,
)
from app.services.export_provider import (
    ZooExportProvider,
    parse_and_validate_stl,
    parse_and_validate_step,
)
from app.services.kcl_compiler import compile_project_to_kcl


def pprint(msg: str = ""):
    print(msg, flush=True)


def create_test_project(proj_id: str, mode: ConnectionMode, dims_a: list, dims_b: list, offset_x: float = 0.0, offset_y: float = 0.0, angle_deg: float = 0.0) -> Project:
    p = Project(
        project_id=proj_id,
        project_token=f"tok_{proj_id}",
        current_schema_revision=1,
        current_model_revision=1,
        interface_a=Interface(
            id="interface_a",
            profile_type=ProfileType.CIRCLE,
            approved=True,
            dimensions=[Dimension(id=k, label=k, value=v, unit="mm") for k, v in dims_a]
        ),
        interface_b=Interface(
            id="interface_b",
            profile_type=ProfileType.CIRCLE,
            approved=True,
            dimensions=[Dimension(id=k, label=k, value=v, unit="mm") for k, v in dims_b]
        ),
        connection=Connection(
            mode=mode,
            length_mm=40.0,
            offset_x_mm=offset_x,
            offset_y_mm=offset_y,
            angle_deg=angle_deg,
        ),
        manufacturing=Manufacturing(
            wall_thickness_mm=2.4,
            clearance_a_mm=0.2,
            clearance_b_mm=0.2,
        ),
    )
    return p


async def run_live_case_proof(case_num: int, title: str, project: Project):
    pprint(f"\n==================================================")
    pprint(f"CASE {case_num}: {title}")
    pprint(f"==================================================")

    kcl_res = compile_project_to_kcl(project)
    assert kcl_res.success, f"Compilation failed for case {case_num}: {kcl_res.errors}"
    kcl_code = kcl_res.kcl_code
    stored_hash = kcl_res.kcl_hash
    executed_hash = hashlib.sha256(kcl_code.encode("utf-8")).hexdigest()

    pprint(f"Project ID:          {project.project_id}")
    pprint(f"Stored KCL SHA256:   {stored_hash}")
    pprint(f"Executed KCL SHA256: {executed_hash}")
    pprint(f"Hash Equality:       {stored_hash == executed_hash}")
    assert stored_hash == executed_hash, "Hash mismatch!"

    provider = ZooExportProvider()
    zoo_sess_id = f"zoo_live_sess_case_{case_num}_{stored_hash[:8]}"

    # Live Zoo-native STL export
    pprint("Initiating Live Zoo-native STL Export...")
    stl_res = await provider.export_format(
        project_id=project.project_id,
        model_revision=1,
        format_name="stl",
        kcl_code=kcl_code,
        project=project,
        zoo_model_id=zoo_sess_id,
        kcl_hash=stored_hash,
    )

    pprint(f"\n--- Live STL Export Result ---")
    pprint(f"Success:      {stl_res.success}")
    pprint(f"Artifact Ref: {stl_res.artifact_ref}")
    pprint(f"Size Bytes:   {stl_res.size_bytes}")
    pprint(f"Facet Count:  {stl_res.facet_count}")
    pprint(f"Bounding Box: {stl_res.bounding_box}")
    pprint(f"Dimensions:   {stl_res.dimensions_mm}")
    assert stl_res.success, f"STL export failed for {title}: {stl_res.error_message}"

    # Live Zoo-native STEP export
    pprint("Initiating Live Zoo-native STEP Export...")
    step_res = await provider.export_format(
        project_id=project.project_id,
        model_revision=1,
        format_name="step",
        kcl_code=kcl_code,
        project=project,
        zoo_model_id=zoo_sess_id,
        kcl_hash=stored_hash,
    )

    pprint(f"\n--- Live STEP Export Result ---")
    pprint(f"Success:      {step_res.success}")
    pprint(f"Artifact Ref: {step_res.artifact_ref}")
    pprint(f"Size Bytes:   {step_res.size_bytes}")
    pprint(f"Entity Count: {step_res.entity_count}")
    assert step_res.success, f"STEP export failed for {title}: {step_res.error_message}"

    return {
        "case_num": case_num,
        "title": title,
        "project_id": project.project_id,
        "stored_kcl_hash": stored_hash,
        "executed_kcl_hash": executed_hash,
        "kcl_equal": stored_hash == executed_hash,
        "stl_artifact": stl_res.artifact_ref,
        "stl_size": stl_res.size_bytes,
        "stl_facets": stl_res.facet_count,
        "stl_dims": stl_res.dimensions_mm,
        "step_artifact": step_res.artifact_ref,
        "step_size": step_res.size_bytes,
        "step_entities": step_res.entity_count,
    }


async def main():
    cases = [
        (1, "Simple Plate (Circular Coaxial, Identical Dims)", create_test_project("proj_case1_simple_plate", ConnectionMode.COAXIAL, [("outer_diameter", 50.0)], [("outer_diameter", 50.0)])),
        (2, "Circular Coaxial Adapter (Different Dims)", create_test_project("proj_case2_circular_coaxial", ConnectionMode.COAXIAL, [("outer_diameter", 60.0)], [("outer_diameter", 40.0)])),
        (3, "Circular Offset Adapter (Offset X=15.0, Y=10.0)", create_test_project("proj_case3_circular_offset", ConnectionMode.OFFSET, [("outer_diameter", 50.0)], [("outer_diameter", 35.0)], offset_x=15.0, offset_y=10.0)),
        (4, "Limited-Angle Adapter (Angle=15.0 deg)", create_test_project("proj_case4_angled_adapter", ConnectionMode.ANGLED, [("outer_diameter", 50.0)], [("outer_diameter", 35.0)], angle_deg=15.0)),
    ]

    results = []
    for case_num, title, proj in cases:
        res = await run_live_case_proof(case_num, title, proj)
        results.append(res)

    pprint("\n\n==================================================")
    pprint("ALL 4 LIVE ZOO-NATIVE EXPORT CASES PASSED PROOF!")
    pprint("==================================================")
    for r in results:
        pprint(f"Case {r['case_num']} ({r['title']}):")
        pprint(f"  STL:  {r['stl_size']} bytes, {r['stl_facets']} facets, Dims: {r['stl_dims']}")
        pprint(f"  STEP: {r['step_size']} bytes, {r['step_entities']} entities")
        pprint(f"  Hash Match: {r['kcl_equal']} ({r['stored_kcl_hash'][:8]})\n")


if __name__ == "__main__":
    asyncio.run(main())
