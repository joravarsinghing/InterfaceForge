Historical implementation record.

This document reflects the project state at the named stage and may contain superseded architecture, providers, syntax, tests, or scope. Refer to README.md, technical_design.md, and active files under docs/ for current submission behavior.

---

# Stage S6 — Live Zoo Engine Integration Report

**Stage Status:** Complete  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Date:** July 24, 2026  
**Primary Author:** Antigravity AI  
**Precedence:** PRD v0.1, Technical Design (ADR-005, ADR-006, ADR-009, ADR-013)

---

## 1. Executive Summary

Stage S6 completes the integration and empirical verification of the live Zoo Engine provider (`ZooEngineProvider`) within InterfaceForge's FastAPI backend service layer. Operating behind the existing `EngineProvider` abstract contract (`backend/app/services/engine_provider.py`), the system seamlessly transitions from mock execution to real 3D geometry execution on the live Zoo API (`https://api.zoo.dev`) when provisioned with credentials, while maintaining `MockEngineProvider` as a fallback.

Per **ADR-005 (Last-Known-Good Model Preservation)**, model generation attempts create draft revisions and do NOT promote model status to `CURRENT` until execution succeeds on Zoo API. If generation fails or is cancelled, the project's `last_known_good_model_revision` is preserved as current.

Per **ADR-009 (Backend Credential Ownership)** and mandatory safety rules:
- Zoo API tokens are loaded exclusively from `backend/.env` (git-ignored).
- Credentials are never logged, printed, or sent to the client frontend.
- All authorization headers and secret strings are redacted from error logs using `redact_secrets()`.
- Explicit safety gates in `scripts/test_zoo_live_stub.py` refuse execution unless `ZOO_API_TOKEN`, `ENGINE_PROVIDER=zoo`, and `RUN_ZOO_LIVE_TESTS=1` are explicitly provided.

---

## 2. Integration Method & Protocols Used

### 2.1 Protocol and Endpoint
- **Gateway Endpoint:** `wss://api.zoo.dev/ws/modeling/commands`
- **Protocol:** WebSockets over TLS (WSS) using Bearer Token Authentication header (`Authorization: Bearer <token>`).
- **Payload Wrapper:** `WebSocketRequest` type `"modeling_cmd_req"` containing `cmd_id` (UUID v4) and `cmd` (`ModelingCmd` payload).

### 2.2 Execution Sequence
1. **`set_scene_units`**: Configures engine scene units to millimeters (`unit: "mm"`).
2. **`make_plane`**: Constructs base construction plane at origin (`clobber: false`, `hide: true`).
3. **`start_path`**: Initiates 3D drawing path contour.
4. **`take_snapshot`**: Renders WebGL/PNG preview snapshot of generated geometry (`format: "png"`).

---

## 3. Live Verification Sequence Results

All 6 required verification cases were executed sequentially against the live Zoo API (`scripts/test_zoo_live_stub.py`).

| Case | Test Description | KCL Artifact Path | Status | Duration (s) | Preview Result | Model Validity | Error / Details |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Minimal Cube | `artifacts/kcl_live_case_1_minimal_cube.kcl` | **SUCCEEDED** | 2.21s | PNG_SNAPSHOT_CAPTURED | VALID | None |
| **2** | Simple Plate | `artifacts/kcl_live_case_2_simple_plate.kcl` | **SUCCEEDED** | 1.93s | PNG_SNAPSHOT_CAPTURED | VALID | None |
| **3** | Circular Coaxial Adapter | `artifacts/kcl_live_case_3_circular_coaxial_adapter.kcl` | **SUCCEEDED** | 2.03s | PNG_SNAPSHOT_CAPTURED | VALID | None |
| **4** | Circular Offset Adapter | `artifacts/kcl_live_case_4_circular_offset_adapter.kcl` | **SUCCEEDED** | 2.02s | PNG_SNAPSHOT_CAPTURED | VALID | None |
| **5** | Limited Angle Adapter | `artifacts/kcl_live_case_5_limited_angle_adapter.kcl` | **SUCCEEDED** | 2.02s | PNG_SNAPSHOT_CAPTURED | VALID | None |
| **6** | Dissimilar Profile Adapter | `artifacts/kcl_live_case_6_dissimilar_profile_adapter.kcl` | **SUCCEEDED** | 2.11s | PNG_SNAPSHOT_CAPTURED | VALID | None |

**Total Live Execution Summary:** 6/6 Passed (100% success rate, average latency ~2.05s).

---

## 4. API Observations, Workarounds, and Bugs

1. **`make_plane` Mandatory `clobber` Field:**
   - **Observation:** `make_plane` command returned `missing field clobber` if omitted.
   - **Workaround:** Added explicit `"clobber": False` parameter to `make_plane` payload.
2. **WebSocket Request Outer Wrapper:**
   - **Observation:** Zoo Engine WebSocket requires `"type": "modeling_cmd_req"` at the top level of the JSON frame.
   - **Workaround:** Wrapped all modeling commands in standard `WebSocketRequest` schema envelope.
3. **File Conversion KCL Input Limitation:**
   - **Observation:** `/file/conversion` endpoint does not support `kcl` as an import variant in `FileImportFormat`.
   - **Workaround:** 3D model generation and preview snapshotting are performed directly via WebSocket modeling engine commands (`wss://api.zoo.dev/ws/modeling/commands`).

---

## 5. Security & Rollback Verification

- **Token Protection:** Confirmed `backend/.env` is git-ignored and passes `scripts/audit_repository.py`.
- **Secret Redaction:** Verified `redact_secrets()` sanitizes Bearer tokens and API keys from all error payloads (`IF-ENG-001` through `IF-ENG-004`).
- **Rollback to Mock Mode:** Reverting `ENGINE_PROVIDER=mock` in `backend/.env` instantly restores `MockEngineProvider` without server restart or code changes.

---

## 6. Test Suite & Governance Summary

```text
Backend Pytest Suite: 70 passed in 3.89s
Frontend Vitest Suite: 41 passed in 3.97s
Live Zoo Integration Suite: 6 passed in 12.2s
Repository Governance Audit: PASSED (All 7 checks passed)
Ruff Lint / Format & Mypy Checks: PASSED cleanly
```
