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

### 1.4 `POST /api/projects/{project_id}/interfaces/{interface_id}/analyze`
Triggers profile extraction using configured `AnalysisProvider` interface (defaults to `MockAnalysisProvider`).

### 1.5 `PATCH /api/projects/{project_id}/interfaces/{interface_id}`
Edits interface profile type, dimensions, or candidate points.
- **Upstream Side Effects:** Clears approval (`approved: false`, `approved_at: null`), increments `current_schema_revision`, and marks current 3D model revision as `stale`.

### 1.6 `POST /api/projects/{project_id}/interfaces/{interface_id}/approve`
Approves interface profile.
- **Enforces Invariants:** Interface B approval requires Interface A to be approved (`IF-APPROVAL-400`). Structural profile validation must pass.

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

---

## 2. Stable Error Codes

| Error ID | HTTP Status | Description | Recovery Action |
| :--- | :--- | :--- | :--- |
| **`IF-PROJ-404`** | 404 | Project ID not found | Verify project ID or create a new project |
| **`IF-AUTH-401`** | 401 | Invalid or missing project token | Provide valid `X-Project-Token` header |
| **`IF-STATE-400`** | 400 | Invalid state transition | Complete prerequisite workflow steps |
| **`IF-PREREQ-400`** | 400 | Missing prerequisite data/step | Fulfill required prerequisite state |
| **`IF-APPROVAL-400`** | 400 | Invalid interface approval sequence | Approve Interface A before Interface B |
| **`IF-CONN-400`** | 400 | Invalid connection or manufacturing config | Adjust parameters to satisfy geometric limits |
| **`IF-CONN-001`** | 400 | Prerequisites unapproved | Approve Interface A and Interface B first |
| **`IF-CONN-002`** | 400 | Unsupported connection mode | Choose coaxial, offset, or angled mode |
| **`IF-CONN-003`** | 400 | Non-positive or non-finite transition length | Set transition length > 0 mm |
| **`IF-CONN-004`** | 400 | Connection angle exceeds 45° limit | Reduce angle to 45° or less |
| **`IF-CONN-005`** | 400 | Non-zero angle in coaxial or offset mode | Set angle to 0° or select angled mode |
| **`IF-CONN-006`** | 400 | Offset-to-length ratio exceeds 1.5 | Increase length or decrease X/Y offset |
| **`IF-CONN-007`** | 400 | Non-zero offsets in coaxial mode | Set X/Y offsets to 0 mm or select offset mode |
| **`IF-CONN-008`** | 400 | Unsupported profile type for connection | Edit profile to circle/rectangle/rounded |
| **`IF-CONN-009`** | 400 | Self-intersection risk detected | Reduce angle/offset or increase length |
| **`IF-MFG-001`** | 400 | Non-positive or non-finite wall thickness | Set wall thickness > 0 mm |
| **`IF-MFG-002`** | 400 | Wall thickness below 0.4 mm minimum | Set wall thickness >= 0.8 mm |
| **`IF-MFG-003`** | 400 | Clearance outside 0.0 - 5.0 mm bounds | Set clearance between 0.0 and 5.0 mm |
| **`IF-MFG-004`** | 400 | Internal passage collapsed by wall thickness | Reduce wall thickness relative to interface size |
| **`IF-KCL-001`** | 400 | Unsupported profile type for KCL compilation | Edit profile to circle, rectangle, or rounded rectangle |
| **`IF-KCL-002`** | 400 | Non-finite parameter value in compilation | Provide valid finite numeric parameters |
| **`IF-KCL-003`** | 400 | Unapproved interface prerequisites for KCL | Approve Interface A and Interface B before compilation |
| **`IF-KCL-004`** | 400 | Connection validation failure prior to KCL | Resolve blocking connection/mfg errors first |
| **`IF-KCL-006`** | 400 | Schema revision mismatch during KCL emit | Re-synchronize canonical schema parameters |
| **`IF-FILE-400`** | 400 | Invalid file upload | Upload valid PNG/JPEG/WEBP under 10MB |
| **`IF-ANALYSIS-400`** | 400 | Image quality rejected | Upload clearer image facing interface directly |
| **`IF-STALE-400`** | 400 | Operation attempted on stale model | Re-generate 3D model with updated params |
| **`IF-SCHEMA-400`** | 400 | Schema version mismatch | Use supported schema version `0.1` |

