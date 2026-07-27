"""Safety-Gated Live Verification Script for Zoo File Format API Exports per Stage S8.2."""

import asyncio
import hashlib
import os
import sys
import time
import uuid
from pathlib import Path

# Add backend directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "backend" / ".env")

from app.core.config import settings  # noqa: E402
from app.models.schema import (  # noqa: E402
    Connection,
    ConnectionMode,
    ModelRevision,
    ModelRevisionStatus,
    ProfileType,
    Project,
)
from app.services.export_provider import (  # noqa: E402
    ZooExportProvider,
    parse_and_validate_step,
    parse_and_validate_stl,
)
from app.services.geometry_generator import (  # noqa: E402
    get_local_obj_call_count,
    reset_local_obj_call_count,
)
from app.services.kcl_compiler import compile_project_to_kcl  # noqa: E402


def check_safety_gates() -> None:
    """Verify mandatory safety environment variables per ADR-009 & Stage S8.2 rules."""
    token = os.getenv("ZOO_API_TOKEN") or settings.zoo_api_token
    run_live = os.getenv("RUN_ZOO_LIVE_EXPORTS") == "1"
    engine_provider = os.getenv("ENGINE_PROVIDER", settings.engine_provider).lower()
    export_provider = os.getenv("EXPORT_PROVIDER", settings.export_provider).lower()

    print("=== Checking Stage S8.2 Live Verification Safety Gates ===")
    print(f"ZOO_API_TOKEN set: {bool(token)}")
    print(f"RUN_ZOO_LIVE_EXPORTS == '1': {run_live}")
    print(
        f"ENGINE_PROVIDER / EXPORT_PROVIDER: engine={engine_provider}, export={export_provider}"
    )

    if not token:
        print("ERROR: ZOO_API_TOKEN is missing in environment or backend/.env.")
        sys.exit(1)

    if not run_live:
        print(
            "ERROR: RUN_ZOO_LIVE_EXPORTS=1 must be set to execute live API export verification."
        )
        sys.exit(1)

    if engine_provider != "zoo" and export_provider != "zoo":
        print("ERROR: ENGINE_PROVIDER=zoo or EXPORT_PROVIDER=zoo must be set.")
        sys.exit(1)

    print("[OK] All safety gates passed cleanly.\n")


def create_live_project(
    case_num: int,
    name: str,
    mode: ConnectionMode = ConnectionMode.COAXIAL,
    if_a_type: ProfileType = ProfileType.CIRCLE,
    if_b_type: ProfileType = ProfileType.CIRCLE,
    offset_x: float = 0.0,
    angle_deg: float = 0.0,
) -> Project:
    """Helper to generate a project container for live export tests."""
    zoo_model_id = f"zoo_live_sess_case_{case_num}_{uuid.uuid4().hex[:6]}"
    project = Project(
        project_id=f"live_s82_case_{case_num}_{name.lower().replace(' ', '_')}",
        project_token="tok_live_s82_verification",
        current_schema_revision=1,
        current_model_revision=1,
    )
    project.interface_a.profile_type = if_a_type
    project.interface_a.approved = True
    project.interface_b.profile_type = if_b_type
    project.interface_b.approved = True
    project.connection = Connection(
        mode=mode,
        length_mm=40.0,
        offset_x_mm=offset_x,
        angle_deg=angle_deg,
    )

    compile_res = compile_project_to_kcl(project)
    project.model_revisions = [
        ModelRevision(
            model_revision=1,
            schema_revision=1,
            status=ModelRevisionStatus.CURRENT,
            zoo_model_id=zoo_model_id,
            kcl_hash=compile_res.kcl_hash,
            kcl_artifact_ref=compile_res.artifact_ref,
        )
    ]
    return project


async def run_live_export_verifications():
    """Execute required 4 live export cases sequentially against Zoo API per S8.2."""
    check_safety_gates()

    provider = ZooExportProvider()

    cases = [
        (
            1,
            "Simple Plate",
            ProfileType.RECTANGLE,
            ProfileType.RECTANGLE,
            ConnectionMode.COAXIAL,
            0.0,
            0.0,
        ),
        (
            2,
            "Circular Coaxial Adapter",
            ProfileType.CIRCLE,
            ProfileType.CIRCLE,
            ConnectionMode.COAXIAL,
            0.0,
            0.0,
        ),
        (
            3,
            "Circular Offset Adapter",
            ProfileType.CIRCLE,
            ProfileType.CIRCLE,
            ConnectionMode.OFFSET,
            15.0,
            0.0,
        ),
        (
            4,
            "Limited-Angle Adapter",
            ProfileType.CIRCLE,
            ProfileType.CIRCLE,
            ConnectionMode.ANGLED,
            0.0,
            10.0,
        ),
    ]

    print("=" * 105)
    print("STAGE S8.2 — ZOO MODEL EXPORT ALIGNMENT LIVE VERIFICATION SUITE")
    print("=" * 105)

    audit_records = []
    stl_hashes = []
    step_hashes = []

    for (
        case_num,
        name,
        if_a_type,
        if_b_type,
        mode,
        offset_x,
        angle_deg,
    ) in cases:
        print(f"\n--- [Auditing Case {case_num}: {name}] ---")
        project = create_live_project(
            case_num, name, mode, if_a_type, if_b_type, offset_x, angle_deg
        )
        current_rev = project.model_revisions[0]

        compile_res = compile_project_to_kcl(project)
        kcl_code = compile_res.kcl_code or ""
        kcl_hash = compile_res.kcl_hash or ""

        print(f"  Canonical Schema Revision: {project.current_schema_revision}")
        print(f"  Model Revision: {project.current_model_revision}")
        print(f"  Zoo Model Identifier: {current_rev.zoo_model_id}")
        print(f"  Deterministic KCL Hash: {kcl_hash[:12]}")

        record = {
            "case_num": case_num,
            "name": name,
            "project_id": project.project_id,
            "schema_revision": project.current_schema_revision,
            "model_revision": project.current_model_revision,
            "kcl_hash": kcl_hash,
            "zoo_model_id": current_rev.zoo_model_id,
            "local_obj_calls": 0,
        }

        reset_local_obj_call_count()

        # Export STL via Zoo API
        print("  Executing Zoo API Export -> STL ...")
        t0 = time.time()
        stl_res = await provider.export_format(
            project_id=project.project_id,
            model_revision=1,
            format_name="stl",
            kcl_code=kcl_code,
            project=project,
            zoo_model_id=current_rev.zoo_model_id,
            kcl_hash=kcl_hash,
        )
        stl_duration = time.time() - t0

        if not stl_res.success or not stl_res.artifact_ref:
            print(f"  [FAIL] STL export failed: {stl_res.error_message}")
            sys.exit(1)

        with open(stl_res.artifact_ref, "rb") as f:
            stl_bytes = f.read()

        stl_hash = hashlib.sha256(stl_bytes).hexdigest()
        stl_hashes.append(stl_hash)
        stl_val = parse_and_validate_stl(stl_bytes)

        if not stl_val["is_valid"]:
            print(f"  [FAIL] STL geometry validation failed: {stl_val['error']}")
            sys.exit(1)

        print(
            f"  [OK] STL: {len(stl_bytes)} B in {stl_duration:.2f}s | Facets: {stl_val['facet_count']} | "
            f"BBox: {stl_val['dimensions_mm']} mm | Hash: {stl_hash[:12]}"
        )

        record["stl_size"] = len(stl_bytes)
        record["stl_hash"] = stl_hash
        record["stl_facets"] = stl_val["facet_count"]
        record["stl_bbox"] = stl_val["dimensions_mm"]

        # Export STEP via Zoo API
        print("  Executing Zoo API Export -> STEP ...")
        t0 = time.time()
        step_res = await provider.export_format(
            project_id=project.project_id,
            model_revision=1,
            format_name="step",
            kcl_code=kcl_code,
            project=project,
            zoo_model_id=current_rev.zoo_model_id,
            kcl_hash=kcl_hash,
        )
        step_duration = time.time() - t0

        if not step_res.success or not step_res.artifact_ref:
            print(f"  [FAIL] STEP export failed: {step_res.error_message}")
            sys.exit(1)

        with open(step_res.artifact_ref, "rb") as f:
            step_bytes = f.read()

        step_hash = hashlib.sha256(step_bytes).hexdigest()
        step_hashes.append(step_hash)
        step_val = parse_and_validate_step(step_bytes)

        if not step_val["is_valid"]:
            print(f"  [FAIL] STEP geometry validation failed: {step_val['error']}")
            sys.exit(1)

        print(
            f"  [OK] STEP: {len(step_bytes)} B in {step_duration:.2f}s | Entities: {step_val['entity_count']} | "
            f"Solids: {len(step_val['solid_entities'])} | Hash: {step_hash[:12]}"
        )

        record["step_size"] = len(step_bytes)
        record["step_hash"] = step_hash
        record["step_entities"] = step_val["entity_count"]
        record["local_obj_calls"] = get_local_obj_call_count()
        print(f"  [OK] Local OBJ Generator Call Count: {record['local_obj_calls']}")

        audit_records.append(record)

    # Cross-model uniqueness & cross-verification
    print("\n" + "=" * 105)
    print("CROSS-MODEL VERIFICATION & AUDIT ANALYSIS")
    print("=" * 105)

    unique_stl_hashes = set(stl_hashes)
    unique_step_hashes = set(step_hashes)

    print(f"Total Cases Audited: {len(cases)}")
    print(f"Unique STL Hashes: {len(unique_stl_hashes)} / {len(cases)}")
    print(f"Unique STEP Hashes: {len(unique_step_hashes)} / {len(cases)}")

    if len(unique_stl_hashes) != len(cases):
        print("CRITICAL AUDIT FAILURE: Repeated STL hashes detected across distinct models!")
        sys.exit(1)

    if len(unique_step_hashes) != len(cases):
        print("CRITICAL AUDIT FAILURE: Repeated STEP hashes detected across distinct models!")
        sys.exit(1)

    print("[SUCCESS] All 4 live export cases produced unique, valid STL and STEP geometry!")

    print("=" * 105)
    print("STAGE S8.2 AUDIT EVIDENCE SUMMARY TABLE")
    print("=" * 105)
    print(
        f"{'Case':<5}{'Name':<26}{'Zoo Model ID':<22}{'STL Size':<10}{'STL Facets':<12}{'STEP Size':<11}{'STEP Entities':<15}{'Local OBJ Calls':<15}"
    )
    print("-" * 105)
    for r in audit_records:
        print(
            f"{r['case_num']:<5}{r['name'][:24]:<26}{r['zoo_model_id'][:20]:<22}{r['stl_size']:<10}{r['stl_facets']:<12}{r['step_size']:<11}{r['step_entities']:<15}{r['local_obj_calls']:<15}"
        )
    print("=" * 105)

    return audit_records


if __name__ == "__main__":
    asyncio.run(run_live_export_verifications())

