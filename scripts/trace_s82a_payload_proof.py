import asyncio
import hashlib
import os
import sys
import json
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / "backend" / ".env")

from app.core.config import settings
from app.models.schema import (
    Connection,
    ConnectionMode,
    ModelRevision,
    ModelRevisionStatus,
    ProfileType,
    Project,
)
from app.services.export_provider import (
    ZooExportProvider,
    _serialize_zoo_model_payload,
    parse_and_validate_step,
    parse_and_validate_stl,
)
from app.services.kcl_compiler import compile_project_to_kcl


async def trace_coaxial_export():
    token = settings.zoo_api_token
    print("=== STAGE S8.2A — COAXIAL ADAPTER EXPORT PAYLOAD TRACE ===")
    
    # Create Case 2: Circular Coaxial Adapter
    project = Project(
        project_id="trace_s82a_coaxial",
        project_token="tok_s82a_trace",
        current_schema_revision=1,
        current_model_revision=1,
    )
    project.interface_a.profile_type = ProfileType.CIRCLE
    project.interface_a.approved = True
    project.interface_b.profile_type = ProfileType.CIRCLE
    project.interface_b.approved = True
    project.connection = Connection(
        mode=ConnectionMode.COAXIAL,
        length_mm=40.0,
    )

    # 1. Stored KCL compilation & hash
    compile_res = compile_project_to_kcl(project)
    kcl_code = compile_res.kcl_code
    stored_kcl_hash = hashlib.sha256(kcl_code.encode("utf-8")).hexdigest()
    print(f"1. Stored Approved KCL Code Length: {len(kcl_code)} chars")
    print(f"   Stored KCL SHA-256: {stored_kcl_hash}")

    # 2. Payload generation for Zoo API conversion
    payload_str = _serialize_zoo_model_payload(project, kcl_code)
    payload_bytes = payload_str.encode("utf-8")
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    print(f"2. Geometry Payload Sent to Zoo API: {len(payload_bytes)} bytes")
    print(f"   Payload SHA-256: {payload_sha256}")

    # 3. Direct HTTP call to Zoo REST File Format API -> STL
    stl_url = f"{settings.zoo_api_base_url}/file/conversion/obj/stl"
    req_stl = urllib.request.Request(
        stl_url,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InterfaceForge/1.0",
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    
    resp_stl = urllib.request.urlopen(req_stl, timeout=30)
    resp_stl_bytes = resp_stl.read()
    json_stl = json.loads(resp_stl_bytes.decode("utf-8"))
    req_id_stl = json_stl.get("request_id")
    stl_b64 = json_stl.get("outputs", {}).get("stl") or list(json_stl.get("outputs", {}).values())[0]
    import base64
    raw_stl_bytes = base64.b64decode(stl_b64)
    stl_sha256 = hashlib.sha256(raw_stl_bytes).hexdigest()
    stl_val = parse_and_validate_stl(raw_stl_bytes)

    print(f"3. Zoo API STL Response: HTTP {resp_stl.status} | Request ID: {req_id_stl}")
    print(f"   Returned STL Size: {len(raw_stl_bytes)} bytes | Facets: {stl_val['facet_count']}")
    print(f"   Returned STL SHA-256: {stl_sha256}")

    # 4. Direct HTTP call to Zoo REST File Format API -> STEP
    step_url = f"{settings.zoo_api_base_url}/file/conversion/obj/step"
    req_step = urllib.request.Request(
        step_url,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "InterfaceForge/1.0",
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    
    resp_step = urllib.request.urlopen(req_step, timeout=30)
    resp_step_bytes = resp_step.read()
    json_step = json.loads(resp_step_bytes.decode("utf-8"))
    req_id_step = json_step.get("request_id")
    step_b64 = json_step.get("outputs", {}).get("step") or list(json_step.get("outputs", {}).values())[0]
    import base64
    missing_padding = len(step_b64) % 4
    if missing_padding:
        step_b64 += "=" * (4 - missing_padding)
    raw_step_bytes = base64.b64decode(step_b64)
    step_sha256 = hashlib.sha256(raw_step_bytes).hexdigest()
    step_val = parse_and_validate_step(raw_step_bytes)

    print(f"4. Zoo API STEP Response: HTTP {resp_step.status} | Request ID: {req_id_step}")
    print(f"   Returned STEP Size: {len(raw_step_bytes)} bytes | Entities: {step_val['entity_count']}")
    print(f"   Returned STEP SHA-256: {step_sha256}")

    print("\n=== SUMMARY OF TRACE ===")
    print(f"Stored KCL SHA-256: {stored_kcl_hash}")
    print(f"Payload Bytes Sent SHA-256: {payload_sha256}")
    print(f"Payload Byte Length: {len(payload_bytes)}")
    print(f"Returned STL SHA-256: {stl_sha256}")
    print(f"Returned STEP SHA-256: {step_sha256}")
    print(f"Zoo Request ID (STL): {req_id_stl}")
    print(f"Zoo Request ID (STEP): {req_id_step}")

if __name__ == "__main__":
    asyncio.run(trace_coaxial_export())
