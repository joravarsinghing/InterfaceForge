# Zoo Engine Live API Integration Checklist (Stage S5.5 & S6 Transition)

**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Document Status:** Operational Checklist  
**Precedence:** Technical Design & Accepted ADRs (ADR-006, ADR-009)

---

## 1. Executive Overview

This document provides the mandatory step-by-step verification protocol for transitioning InterfaceForge from the `MockEngineProvider` to the live `ZooEngineProvider` when Zoo Engine API access keys are provisioned.

---

## 2. Environment Variables & Credentials Setup

Before running live API tests, verify that the backend environment is configured without hardcoding secrets:

| Variable | Required Value | Notes |
| :--- | :--- | :--- |
| `ENGINE_PROVIDER` | `zoo` | Switches engine factory from `MockEngineProvider` to `ZooEngineProvider`. |
| `ZOO_API_TOKEN` | `<YOUR_ZOO_API_KEY>` | Bearer token provided by Zoo dev platform. **NEVER COMMIT TO GIT.** |
| `ZOO_API_BASE_URL` | `https://api.zoo.dev` | Production API gateway URL. |
| `GENERATION_TIMEOUT_SECONDS` | `30.0` | Execution timeout threshold. |

---

## 3. Pre-Flight Verification Sequence

1. **Verify Environment Token:**
   Run the safety stub script without token to confirm refusal gate:
   ```bash
   python scripts/test_zoo_live_stub.py
   # Expected Output: [ERROR] REFUSING TO RUN: ZOO_API_TOKEN environment variable is missing
   ```
2. **Verify Configuration Fallback:**
   Confirm that if `ENGINE_PROVIDER=zoo` is set without `ZOO_API_TOKEN`, `settings.get_effective_engine_provider()` safely defaults to `mock`.

---

## 4. Live Test Suite Execution Protocol

Execute the tests in strict order. Stop immediately if any test fails.

### Test 1: Reference Cube / Flat Plate Test
- **Purpose:** Confirm API authentication, request formatting, and basic extrusion geometry execution.
- **KCL Payload:** Simple 20mm × 20mm extruded square box.
- **Success Criteria:** HTTP 200 OK from Zoo API, non-empty mesh payload returned.

### Test 2: Circular Coaxial Adapter Test
- **Purpose:** Validate lofting between two circular profiles (Interface A: 50mm OD, Interface B: 34.5mm OD, Length: 40mm).
- **Success Criteria:** Watertight solid generated, wall thickness 2.5mm maintained, preview mesh rendered cleanly.

### Test 3: Offset Adapter Test
- **Purpose:** Validate lofting between offset centers (Interface A at (0,0), Interface B at (15,10), Length: 40mm).
- **Success Criteria:** Asymmetric loft surface interpolated smoothly without self-intersection or non-manifold edges.

### Test 4: Angled Adapter Test
- **Purpose:** Validate inclined top plane construction (`plane(origin = [...], xAxis = [...], yAxis = [...])`) up to 30° angle.
- **Success Criteria:** Inclined profile face matches specified vector normal, boolean void subtraction succeeds.

### Test 5: Timeout & Retry Verification
- **Purpose:** Verify client resilience against network delay or long generation queue.
- **Procedure:** Simulate/test 30s timeout handling; verify retry endpoint creates clean new job without corrupting project state.

### Test 6: Preview Mesh Verification
- **Purpose:** Verify preview rendering pipeline converts Zoo GLB/mesh artifacts into web-ready preview metadata.
- **Success Criteria:** Bounding box calculations (X/Y/Z mm) and estimated volume (cm³) match expected geometric tolerances within ±2%.

---

## 5. API-Minute Monitoring & Resource Management

- **Rate Limits:** Monitor Zoo API dashboard to ensure requests stay within allocated quota.
- **Error Logs:** Log all HTTP status codes (401, 429, 500) with stable error IDs (`IF-ZOO-401`, `IF-ZOO-429`, `IF-ZOO-500`).
- **Telemetry Evidence:** Capture JSON responses, execution duration (ms), and mesh facet counts for stage report.

---

## 6. Immediate Rollback Protocol

If live Zoo API fails unexpectedly or exceeds timeout limits during demo/testing:

1. Revert environment configuration to mock mode:
   ```env
   ENGINE_PROVIDER=mock
   ```
2. Restart backend server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
3. Confirm frontend displays `[MOCK ENGINE MODE]` banner and user operations continue without interruption.
