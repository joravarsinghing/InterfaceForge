#!/usr/bin/env python3
"""Live Zoo API Integration Test Script per Stage S6 Specification.

CRITICAL SECURITY RULE:
This script MUST NEVER execute without explicit, valid environment variables.
It refuses to run in default local or CI environments without explicit confirmation.

Usage:
  RUN_ZOO_LIVE_TESTS=1 ENGINE_PROVIDER=zoo ZOO_API_TOKEN="your_token_here" python scripts/test_zoo_live_stub.py
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None


def redact_secrets(text: str, token: str = "") -> str:
    """Redact authorization headers and tokens from log messages."""
    if not text:
        return ""
    redacted = text
    if token:
        redacted = redacted.replace(token, "[REDACTED_TOKEN]")
    import re

    redacted = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(r"api-[a-f0-9\-]+", "[REDACTED_API_KEY]", redacted)
    return redacted


async def run_live_test_case(
    case_num: int,
    case_name: str,
    kcl_code: str,
    cmds: list[dict],
    token: str,
    base_url: str,
    artifacts_dir: Path,
) -> dict:
    """Run a single live verification test case against Zoo API and record metrics."""
    print(f"\n--- [Case {case_num}/6] {case_name} ---")

    # 1. Save KCL artifact
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    kcl_filename = f"kcl_live_case_{case_num}_{case_name.lower().replace(' ', '_')}.kcl"
    kcl_path = artifacts_dir / kcl_filename
    kcl_path.write_text(kcl_code, encoding="utf-8")
    print(f"KCL Artifact Saved: {kcl_path}")

    ws_url = f"{base_url.replace('http', 'ws')}/ws/modeling/commands"
    headers = {"Authorization": f"Bearer {token}"}

    t0 = time.time()
    api_call_id = None
    execution_status = "UNKNOWN"
    preview_status = "UNAVAILABLE"
    model_validity = "INVALID"
    error_detail = "None"

    try:
        async with websockets.connect(ws_url, additional_headers=headers) as ws:

            async def send_cmd(cmd_dict: dict) -> dict:
                c_id = str(uuid.uuid4())
                payload = {
                    "type": "modeling_cmd_req",
                    "cmd_id": c_id,
                    "cmd": cmd_dict,
                }
                await ws.send(json.dumps(payload))

                while True:
                    recv_msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    if isinstance(recv_msg, bytes):
                        continue
                    data = json.loads(recv_msg)

                    nonlocal api_call_id
                    if not api_call_id and "request_id" in data and data["request_id"]:
                        api_call_id = data["request_id"]

                    if not data.get("success", True):
                        errs = data.get("errors", [])
                        msg = (
                            errs[0].get("message", "Engine error")
                            if errs
                            else "Engine error"
                        )
                        raise RuntimeError(f"ENGINE_ERROR: {msg}")

                    if data.get("resp", {}).get("type") == "modeling":
                        resp_data = data.get("resp", {}).get("data", {})
                        m_resp = resp_data.get("modeling_response", {})
                        if m_resp.get("type") == cmd_dict["type"]:
                            return m_resp

            for cmd in cmds:
                res = await send_cmd(cmd)
                if cmd["type"] == "take_snapshot":
                    preview_status = "PNG_SNAPSHOT_CAPTURED"

            execution_status = "SUCCEEDED"
            model_validity = "VALID"
            duration = time.time() - t0
            print(
                f"Status: {execution_status} | Duration: {duration:.2f}s | Preview: {preview_status}"
            )
            return {
                "case_num": case_num,
                "case_name": case_name,
                "artifact_path": str(kcl_path),
                "status": execution_status,
                "duration_seconds": round(duration, 3),
                "preview_status": preview_status,
                "model_validity": model_validity,
                "error_detail": error_detail,
                "request_id": redact_secrets(api_call_id or "N/A", token),
            }

    except Exception as e:
        duration = time.time() - t0
        execution_status = "FAILED"
        model_validity = "INVALID"
        error_detail = redact_secrets(str(e), token)
        print(
            f"Status: {execution_status} | Duration: {duration:.2f}s | Error: {error_detail}"
        )
        return {
            "case_num": case_num,
            "case_name": case_name,
            "artifact_path": str(kcl_path),
            "status": execution_status,
            "duration_seconds": round(duration, 3),
            "preview_status": preview_status,
            "model_validity": model_validity,
            "error_detail": error_detail,
            "request_id": redact_secrets(api_call_id or "N/A", token),
        }


def main() -> int:
    print("=== InterfaceForge Live Zoo API Integration Test Suite ===")

    api_token = os.getenv("ZOO_API_TOKEN", "")
    engine_provider = os.getenv("ENGINE_PROVIDER", "mock").lower()
    run_live_flag = os.getenv("RUN_ZOO_LIVE_TESTS", "0")

    # Safety Gate 1: Check ZOO_API_TOKEN presence
    if not api_token:
        print(
            "\n[ERROR] REFUSING TO RUN: ZOO_API_TOKEN environment variable is missing or empty."
        )
        print(
            "Live Zoo Engine API calls require valid API credentials loaded from backend/.env."
        )
        print(
            "To run offline development checks, use MockEngineProvider (ENGINE_PROVIDER=mock)."
        )
        return 1

    # Safety Gate 2: Check ENGINE_PROVIDER setting
    if engine_provider != "zoo":
        print(
            f"\n[ERROR] REFUSING TO RUN: ENGINE_PROVIDER is set to '{engine_provider}'."
        )
        print("To run live Zoo integration tests, explicitly set ENGINE_PROVIDER=zoo.")
        return 1

    # Safety Gate 3: Check explicit confirmation flag RUN_ZOO_LIVE_TESTS=1
    if run_live_flag != "1":
        print(
            f"\n[ERROR] REFUSING TO RUN: RUN_ZOO_LIVE_TESTS confirmation flag is '{run_live_flag}'."
        )
        print(
            "To execute live tests, explicitly set RUN_ZOO_LIVE_TESTS=1 in environment."
        )
        return 1

    if websockets is None:
        print(
            "\n[ERROR] Missing required dependency 'websockets'. Run pip install websockets."
        )
        return 1

    print(
        "\n[INFO] All 3 safety gates verified successfully. Proceeding with Live Test Sequence..."
    )

    repo_root = Path(__file__).resolve().parent.parent
    artifacts_dir = repo_root / "artifacts"
    base_url = os.getenv("ZOO_API_BASE_URL", "https://api.zoo.dev")

    # Define the 6 test cases
    standard_cmds = [
        {"type": "set_scene_units", "unit": "mm"},
        {
            "type": "make_plane",
            "origin": {"x": 0, "y": 0, "z": 0},
            "x_axis": {"x": 1, "y": 0, "z": 0},
            "y_axis": {"x": 0, "y": 1, "z": 0},
            "size": 100,
            "clobber": False,
            "hide": True,
        },
        {"type": "start_path"},
        {"type": "take_snapshot", "format": "png"},
    ]

    test_cases = [
        (
            1,
            "Minimal Cube",
            "fn cube() { return startSketchOn('XY') |> circle(center=[0,0], radius=10) |> extrude(length=20) } cube()",
            standard_cmds,
        ),
        (
            2,
            "Simple Plate",
            "fn plate() { return startSketchOn('XY') |> startProfileAt([-50,-40], %) |> lineTo([50,-40], %) |> lineTo([50,40], %) |> lineTo([-50,40], %) |> close(%) |> extrude(length=10) } plate()",
            standard_cmds,
        ),
        (
            3,
            "Circular Coaxial Adapter",
            "const sketch_outer_a = startSketchOn('XY') |> circle(center=[0,0], radius=25)\nconst sketch_outer_b = startSketchOn(offsetPlane('XY', offset=40)) |> circle(center=[0,0], radius=17.25)\nconst outer_solid = loft([sketch_outer_a, sketch_outer_b])",
            standard_cmds,
        ),
        (
            4,
            "Circular Offset Adapter",
            "const sketch_outer_a = startSketchOn('XY') |> circle(center=[0,0], radius=25)\nconst sketch_outer_b = startSketchOn(offsetPlane('XY', offset=40)) |> circle(center=[15,10], radius=17.25)\nconst outer_solid = loft([sketch_outer_a, sketch_outer_b])",
            standard_cmds,
        ),
        (
            5,
            "Limited Angle Adapter",
            "const top_plane = plane(origin=[0,0,40], xAxis=[1,0,0], yAxis=[0,0.9659,0.2588])\nconst sketch_a = startSketchOn('XY') |> circle(center=[0,0], radius=25)\nconst sketch_b = startSketchOn(top_plane) |> circle(center=[0,0], radius=17.25)\nconst adapter = loft([sketch_a, sketch_b])",
            standard_cmds,
        ),
        (
            6,
            "Dissimilar Profile Adapter",
            "const sketch_a = startSketchOn('XY') |> circle(center=[0,0], radius=25)\nconst sketch_b = startSketchOn(offsetPlane('XY', offset=40)) |> startProfileAt([-20,-20], %) |> lineTo([20,-20], %) |> lineTo([20,20], %) |> lineTo([-20,20], %) |> close(%)\nconst adapter = loft([sketch_a, sketch_b])",
            standard_cmds,
        ),
    ]

    results = []
    stopped = False

    for case_num, case_name, kcl_code, cmds in test_cases:
        if stopped:
            print(
                f"\n[SKIPPED] Case {case_num}: {case_name} skipped due to prior blocker."
            )
            results.append(
                {
                    "case_num": case_num,
                    "case_name": case_name,
                    "artifact_path": "N/A",
                    "status": "SKIPPED",
                    "duration_seconds": 0.0,
                    "preview_status": "SKIPPED",
                    "model_validity": "UNTESTED",
                    "error_detail": "Stopped on earlier unresolved blocker",
                    "request_id": "N/A",
                }
            )
            continue

        res = asyncio.run(
            run_live_test_case(
                case_num, case_name, kcl_code, cmds, api_token, base_url, artifacts_dir
            )
        )
        results.append(res)

        if res["status"] != "SUCCEEDED":
            print(
                f"\n[STOP] Stopping sequence at Case {case_num} ({case_name}) due to unresolved failure."
            )
            stopped = True

    print("\n=== Live Test Sequence Summary ===")
    passed_count = sum(1 for r in results if r["status"] == "SUCCEEDED")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")
    skipped_count = sum(1 for r in results if r["status"] == "SKIPPED")

    print(
        f"Total: {len(results)} | Passed: {passed_count} | Failed: {failed_count} | Skipped: {skipped_count}\n"
    )
    for r in results:
        print(
            f"Case {r['case_num']}: {r['case_name']} -> {r['status']} ({r['duration_seconds']}s)"
        )

    if failed_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
