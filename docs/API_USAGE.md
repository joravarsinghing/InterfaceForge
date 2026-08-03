# InterfaceForge — API Integration Guide

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Internal Project & Workflow Endpoints

### 1.1 `POST /api/projects`
Creates a new project session.

- **Response (201 Created):**
  ```json
  {
    "success": true,
    "data": {
      "project_id": "uuid-v4",
      "project_token": "tok_xyz...",
      "schema_version": "0.1",
      "state": "new"
    }
  }
  ```

### 1.2 `GET /api/projects/{project_id}`
Fetches canonical project schema and workflow state. Optional header `X-Project-Token`.

### 1.3 `POST /api/projects/{project_id}/interfaces/{interface_id}/upload`
Multipart image upload for Interface A or B.
- **Validations:** MIME type (PNG, JPEG, WEBP), max 10MB, corrupt image check, path traversal sanitization.
- **Enforces:** Interface B upload requires Interface A to be approved (`IF-PREREQ-400`).
- **Preferred Input (S10.5H):** The preferred input is a clean cross-section image without dimension annotations. Dimensioned engineering drawings are accepted but classified as **Experimental / manual review required** — the user must review the traced profile before approving. See `docs/GEOMETRY_RULES.md` section 0 for the complete input standard.
- **Known Measurement (S10.5H):** Callers may include an optional `known_measurement` JSON field alongside the file to pre-populate scale calibration. Scale is never applied automatically — user confirmation is required (ADR-004):
  ```json
  {
    "source": "user_known_measurement",
    "reference_dimension": "overall_width",
    "real_distance_mm": 40.0,
    "confirmed": false
  }
  ```

### 1.3b `GET /api/projects/{project_id}/interfaces/{interface_id}/image` (Stage S10.3)
Serves the uploaded source image binary for Interface A or B.
- **Authentication:** Accepts project token via `X-Project-Token` header or `?token=` query parameter (enables direct loading in standard HTML `<img>` tags).
- **Response (200 OK):** Binary image response (`image/png`, `image/jpeg`, `image/webp`).
- **Errors:** Returns `404` if project or uploaded image artifact is missing; returns `401` for invalid token.

### 1.4 `POST /api/projects/{project_id}/interfaces/{interface_id}/analyze`
Triggers profile extraction using configured `AnalysisProvider` interface (`GeminiAnalysisProvider` or `MockAnalysisProvider`). Accepts optional query parameter `provider=gemini` or `provider=mock` to override default provider selection.
- **Model Optimization & Fallback (S7.1/S7.3):** Uses `gemini-3.5-flash-lite` by default (`GEMINI_VISION_MODEL`) to optimize latency and token cost. If primary analysis returns low confidence (< 0.60) without explicit rejection reasons, malformed JSON, or a retryable provider error, automatically executes a single fallback request using `gemini-3.6-flash` (`GEMINI_VISION_FALLBACK_MODEL`). Explicit poor-image rejections with valid explanations do not trigger fallback. Verified against live Google Vision API endpoints.
- **Errors:** Returns `IF-ANALYSIS-400` on low-confidence image quality rejection or malformed provider output.
- **Input Quality (S10.5H):** Analysis responses for dimensioned drawings may include a `quality_status` field of `manual_cleanup_likely`. This does not prevent analysis but warns the user to review the traced profile before approving. The client-side quality badge is a heuristic pre-upload signal; the backend analysis result is authoritative.

### 1.5 `PATCH /api/projects/{project_id}/interfaces/{interface_id}`
Edits interface profile type, dimensions, candidate points, scale calibration, region decisions, or primitive fallback status.
- **Traced Profile Payload Fields (Stage S10.4):**
  - `scale_calibration`: `{"source": "drawing_dimension"|"inferred", "reference_dimension": "overall_width", "pixel_distance": 400.0, "real_distance_mm": 40.0, "confidence": 0.95, "confirmed": true}`
  - `traced_hole_contours`: List of hole objects with updated `decision` (`"include"` | `"ignore"` | `"unsure"`)
  - `primitive_fallback_active`: Boolean (`true` to force primitive bounding envelope)
  - `primitive_fallback_label`: `"Simplified envelope — not the exact cross-section"`
- **Upstream Side Effects:** Clears approval (`approved: false`, `approved_at: null`), increments `current_schema_revision`, and marks current 3D model revision as `stale`.

### 1.6 `POST /api/projects/{project_id}/interfaces/{interface_id}/approve`
Approves interface profile.
- **Enforces Invariants:** Interface B approval requires Interface A to be approved (`IF-APPROVAL-400`). Structural profile validation must pass. For `traced_closed` profiles, `scale_calibration.confirmed` MUST be `true` (`IF-APPROVAL-400`).

### 1.7 `POST /api/projects/{project_id}/validate-connection`
Validates candidate connection and manufacturing configuration parameters against approved interfaces.
- **Response (200 OK):** Returns `ConnectionValidationResult` (`is_valid`, `blocking_errors`, `warnings`, `recommended_values`).

### 1.8 `PUT /api/projects/{project_id}/connection` & `PUT /api/projects/{project_id}/connection-config`
Updates connection and manufacturing settings.
- **Enforces Invariant:** Both interfaces must be approved first (`IF-PREREQ-400`). All geometric and manufacturing rules must pass (`IF-CONN-400`).
- **Side Effects:** Increments `current_schema_revision`, marks current 3D model revision `stale`, and updates workflow state to `connection_configured`.

### 1.9 `POST /api/projects/{project_id}/model/start`
Starts 3D model generation. Enforces invariant: Connection must be configured and interfaces approved (`IF-PREREQ-400`).

### 1.10 `POST /api/projects/{project_id}/model/succeed`
Registers successful generation. Sets revision status to `current` and updates `last_known_good_model_revision`.

### 1.12 `GET /api/projects/{project_id}/kcl/readiness`
Validates compile readiness prior to generating KCL code. Returns `ConnectionValidationResult`.

### 1.13 `POST /api/projects/{project_id}/kcl/compile`
Compiles canonical design schema into deterministic KCL code.
- **Rules:** Enforces ADR-001 and ADR-002. Saves generated KCL artifact in `artifacts/kcl_<project_id>_rev<rev>_<hash>.kcl`.
- **Invariants:** Appends a new model revision in status `draft` (does NOT mark status `current` because Zoo has not executed it).
- **Response (200 OK):** Returns `KCLCompileResult` (`success`, `kcl_code`, `artifact_ref`, `compiler_version`, `schema_revision`, `kcl_hash`, `preview_snippet`, `errors`, `warnings`).

### 1.14 `POST /api/projects/{project_id}/generation/start`
Starts a 3D model generation job using the active `EngineProvider` (defaults to `MockEngineProvider`).
- **Body:** Optional `{ "mock_scenario": "success" }` (supports `success`, `engine_validation_failure`, `timeout`, `malformed_response`, `cancellation`, `preview_failure`).
- **Response (201 Created):** Returns `GenerationJob` object with job ID, status (`queued`/`running`/`succeeded`/`failed`), current stage (`validating`/`compiling`/`executing`/`rendering`/`finalizing`), and progress percentage.
- **Invariants:** Rejects duplicate active job if a job is already in progress (`IF-JOB-409`).

### 1.15 `GET /api/projects/{project_id}/generation/{job_id}`
Polls status and staged progress for a generation job.

### 1.16 `POST /api/projects/{project_id}/generation/{job_id}/cancel`
Requests cancellation of an active generation job. Reverts model state and preserves last known good.

### 1.17 `POST /api/projects/{project_id}/generation/{job_id}/retry`
Retries a failed or cancelled generation job.

### 1.18 `GET /api/projects/{project_id}/generation/{job_id}/preview`
Retrieves preview metadata (render SVG, volume cm³, bounding box mm, facet count).

### 1.19 `POST /api/projects/{project_id}/exports/generate`
Triggers CAD format export generation for requested format(s) (`stl`, `kcl`).
- **Body:** `{ "formats": ["stl", "kcl"], "mock_scenario": "success" }`
- **Response (200 OK):** Returns `ExportStatusResponse` object containing per-format status, artifact references, file sizes, and revision numbers.
- **Invariants:** Requires project state to be `model_current` and model revision to be `CURRENT`. Rejects stale models (`IF-STALE-400`). Handles partial failure without invalidating successful formats.

### 1.20 `GET /api/projects/{project_id}/exports/status`
Queries per-format export status and artifact metadata.
- **Response (200 OK):** Returns `ExportStatusResponse`.

### 1.21 `POST /api/projects/{project_id}/exports/{format_name}/retry`
Retries export generation for a single failed format.

### 1.22 `GET /api/projects/{project_id}/exports/{format_name}/download`
Downloads verified export artifact file (`\.stl`, `.kcl`).
- **Headers:** Requires `X-Project-Token`.
- **Validations:** Token ownership, non-zero file size, binary/text format signature, and path traversal sanitization. Returns `FileResponse` with safe filename and content-type header.

### 1.23 `POST /api/projects/{project_id}/revision/propose`
Proposes structured parameter changes from natural language prompt using Zoo Agent API per S9.
- **Body:** `{ "prompt": "Make it 20 mm longer.", "provider": "zoo" }`
- **Enforces:** Allowlist gate (7 fields ONLY), numeric finiteness, unit normalization, geometric range validation. Does NOT mutate project state.
- **Response (200 OK):** Returns `AgentProposalResult`.

### 1.24 `POST /api/projects/{project_id}/revision/confirm`
Confirms approved parameter changes, updates canonical schema, recompiles KCL, and triggers 3D model generation.
- **Body:** `{ "changes": [...] }`
- **Invariants:** Confirmation gate required. Preserves last-known-good model revision if 3D generation fails (ADR-005).

---

## 2. Stable Error Codes

| Error ID | HTTP Status | Description | Recovery Action |
| :--- | :--- | :--- | :--- |
| **`IF-PROJ-404`** | 404 | Project ID not found | Verify project ID or create a new project |
| **`IF-AUTH-401`** | 401 | Invalid or missing project token | Provide valid `X-Project-Token` header |
| **`IF-ZOO-401`** | 401 | Missing or invalid Zoo API token | Configure `ZOO_API_TOKEN` in `backend/.env` |
| **`IF-STATE-400`** | 400 | Invalid state transition | Complete prerequisite workflow steps |
| **`IF-PREREQ-400`** | 400 | Missing prerequisite data/step | Fulfill required prerequisite state |
| **`IF-APPROVAL-400`** | 400 | Invalid interface approval sequence | Approve Interface A before Interface B |
| **`IF-CONN-400`** | 400 | Invalid connection or manufacturing config | Adjust parameters to satisfy geometric limits |
| **`IF-AGENT-400`** | 400 | Agent revision validation or allowlist error | Provide parameter adjustment within allowed 7 fields |
| **`IF-AGENT-500`** | 500 | Agent API connection or timeout error | Retry revision proposal or check network connectivity |
| **`IF-JOB-409`** | 409 | Active generation job already in progress | Wait for active job or cancel it before starting new job |

| **`IF-ENG-001`** | 400 | Zoo Engine validation failure | Adjust adapter thickness or connection mode |
| **`IF-ENG-002`** | 400 | Zoo Engine execution timeout | Retry generation or simplify geometry |
| **`IF-ENG-003`** | 400 | Zoo Engine malformed response | Retry request or check API payload structure |
| **`IF-ENG-004`** | 400 | Zoo Engine preview rendering failure | Retry model generation and check mesh topology |
| **`IF-JOB-002`** | 400 | Generation job cancelled by user | Start new generation job when ready |
| **`IF-KCL-001`** | 400 | Unsupported profile type for KCL compilation | Edit profile to circle, rectangle, or rounded rectangle |
| **`IF-KCL-002`** | 400 | Non-finite parameter value in compilation | Provide valid finite numeric parameters |
| **`IF-KCL-003`** | 400 | Unapproved interface prerequisites for KCL | Approve Interface A and Interface B before compilation |
| **`IF-KCL-004`** | 400 | Connection validation failure prior to KCL | Resolve blocking connection/mfg errors first |
| **`IF-KCL-006`** | 400 | Schema revision mismatch during KCL emit | Re-synchronize canonical schema parameters |
| **`IF-EXPORT-001`** | 400 | Export generation failed | Retry format export or check provider status |
| **`IF-EXPORT-002`** | 400 | Unsupported export format requested | Select a supported format (stl, kcl) |
| **`IF-EXPORT-004`** | 404 | Export artifact missing or zero-byte | Re-trigger export generation for format |
| **`IF-FILE-400`** | 400 | Invalid file upload | Upload valid PNG/JPEG/WEBP under 10MB |
| **`IF-ANALYSIS-400`** | 400 | Image quality rejected | Upload clearer image facing interface directly |
| **`IF-STALE-400`** | 400 | Operation attempted on stale model | Re-generate 3D model with updated params |
| **`IF-SCHEMA-400`** | 400 | Schema version mismatch | Use supported schema version `0.1` |


