# InterfaceForge â€” Test Plan & Execution Strategy

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Test Architecture & Tooling

- **Backend:** `pytest`, `pytest-asyncio`, `httpx` / `TestClient`
- **Frontend:** `vitest`, `@testing-library/react`, `jsdom`
- **Master Verification Script:** `python scripts/run_all_checks.py`

---

## 2. Test Coverage Matrix

### 2.1 Backend Project Schema & Invariants (`backend/tests/test_projects.py`)
- `test_project_creation`: Project creation endpoint returns 201 with unguessable token and initial state.
- `test_persistence_across_repository_reload`: Reloading repository from same SQLite DB preserves project data.
- `test_serialization_round_trip`: Pydantic JSON round-trip serialization integrity.
- `test_valid_workflow_transitions`: Complete happy-path sequence across all workflow states.
- `test_invalid_prerequisites`: Server-side rejection of invalid state transitions (Prerequisites, Interface B before A, etc.).
- `test_schema_revision_increments_and_stale_behavior`: Editing approved interface or parameters increments schema revision and marks model stale.
- `test_last_known_good_preservation`: Failed generation preserves last-known-good model revision.
- `test_project_not_found`: `IF-PROJ-404` error response.
- `test_invalid_project_token`: `IF-AUTH-401` error response.
- `test_schema_version_rejection`: `IF-SCHEMA-400` error response.

### 2.2 Backend Upload & Mock Analysis (`backend/tests/test_upload_and_analysis.py`)
- `test_valid_image_upload`: Valid image upload updates state and saves file artifact.
- `test_unsupported_file_type`: Uploading unsupported MIME type or extension returns `IF-FILE-400`.
- `test_oversized_file_upload`: Uploading file exceeding 10MB limit returns `IF-FILE-400`.
- `test_corrupt_file_upload`: Uploading corrupt image byte stream returns `IF-FILE-400`.
- `test_path_traversal_sanitization`: Malicious filenames with directory traversal (`../`) are safely sanitized.
- `test_interface_b_upload_prerequisite`: Uploading Interface B before Interface A approval returns `IF-PREREQ-400`.
- `test_mock_analysis_success_and_state_updates`: Upload & mock analysis advances state to `interface_a_review_required`.
- `test_mock_analysis_rectangle_and_rounded`: Mock analysis detects rectangle and rounded rectangle profiles from filename.
- `test_mock_analysis_rejection`: Poor image quality triggers analysis rejection with `IF-ANALYSIS-400`.
- `test_malformed_provider_response`: Malformed provider payload raises `IF-ANALYSIS-400`.

### 2.3 Backend Profile Review & Structural Validation (`backend/tests/test_profile_review_and_approval.py`)
- `test_supported_profiles_validation_and_approval`: Verifies circle, rectangle, and rounded_rectangle profiles pass structural validation and approval.
- `test_fewer_than_two_known_dimensions_rejection`: Interface with fewer than 2 known dimensions fails validation and approval (`IF-APPROVAL-400`).
- `test_zero_or_negative_values_rejection`: Non-positive or non-finite dimension values fail validation and approval (`IF-APPROVAL-400`).
- `test_unresolved_critical_dimension_rejection`: Unresolved critical dimension blocks interface approval (`IF-APPROVAL-400`).
- `test_re_edit_clears_approval_increments_revision_marks_stale`: Re-editing an approved interface clears approval, increments schema revision, and marks model stale.

### 2.4 Backend Connection Configuration & Manufacturing Validation (`backend/tests/test_connection_validation.py`)
- `test_validate_supported_modes`: Verifies coaxial and offset modes pass validation when parameters are within bounds.
- `test_prerequisite_approval_failure`: Verifies validation fails if either Interface A or B is not approved (`IF-CONN-001`).
- `test_invalid_negative_or_non_finite_length_and_wall`: Negative or non-finite length or wall thickness returns blocking errors (`IF-CONN-003`, `IF-MFG-001`).
- Compatibility-only angle-field rejection is covered indirectly; angle mode is not an active submission test target.\n- `test_excessive_offset_to_length_ratio`: Offset-to-length ratio > 1.5 returns blocking error (`IF-CONN-006`).
- `test_wall_thickness_warnings_and_errors`: Wall thickness < 0.4 mm returns error (`IF-MFG-002`), < 1.2 mm returns FDM warning (`IF-MFG-W001`).
- `test_clearance_bounds`: Clearances outside [0.0, 5.0] mm produce blocking errors (`IF-MFG-003`).
- `test_mode_parameter_mismatch_rules`: Non-zero offsets or angle in coaxial mode returns errors (`IF-CONN-005`, `IF-CONN-007`).
- `test_project_service_connection_update_and_stale_model_behavior`: Service updates connection, increments schema revision, marks model stale, and preserves last-known-good model.

### 2.5 Backend KCL Compiler Suite (`backend/tests/test_kcl_compiler.py`)
- `test_circular_coaxial_compilation`: Validates circular coaxial adapter emits explicit mm units, required variables, loft/subtract calls, and artifact reference.
- `test_rectangular_coaxial_compilation`: Validates rectangle to rounded rectangle transition emits correct width, height, corner radius, and tangential arcs.
- `test_circular_offset_compilation`: Validates offset mode emits lateral translation parameters.
- Compatibility-only angle schema handling is not a final-generation test target.\n- `test_arbitrary_closed_profiles_compile_to_polyline_sketches`: Approved `traced_closed` profiles compile for final generation through the deterministic KCL path.
- `test_non_finite_input`: Non-finite numbers fail compilation with `IF-KCL-002`.
- `test_unapproved_prerequisites_fail`: Unapproved interfaces fail compilation with `IF-KCL-003`.
- `test_repeated_identical_compilation_is_deterministic`: Repeated compilation of identical schema produces byte-for-byte identical KCL output and hash.
- `test_project_service_kcl_compilation_does_not_mark_current`: KCL compilation creates a draft model revision but does not set status to `current` and executes zero Zoo API calls.

### 2.6 Backend 3D Generation & Mock Engine Suite (`backend/tests/test_generation.py`)
- `test_successful_mock_execution`: Verifies full success generation lifecycle and status promotion to `model_current`.
- `test_duplicate_job_rejection`: Verifies duplicate active job rejection (`IF-JOB-409`).
- `test_engine_validation_failure`: Verifies `IF-ENG-001` engine validation failure.
- `test_timeout_scenario`: Verifies `IF-ENG-002` engine execution timeout.
- `test_malformed_response_scenario`: Verifies `IF-ENG-003` malformed engine response payload.
- `test_preview_failure_scenario`: Verifies `IF-ENG-004` preview rendering failure.
- `test_cancellation_and_retry`: Verifies job cancellation and subsequent retry.
- `test_last_known_good_model_preservation`: Verifies last-known-good model (Rev 1) is preserved when a subsequent generation attempt (Rev 2) fails.
- `test_preview_metadata_endpoint`: Verifies GET /preview metadata endpoint response.

### 2.7 Full Workflow Integration Suite (`backend/tests/test_full_workflow_integration.py` & `frontend/src/test/WorkflowIntegration.test.tsx`)
- Scenario 1: Complete happy path workflow.
- Scenario 2: Interface B cannot be reached before Interface A approval.
- Scenario 3: Invalid direct route access redirects to earliest incomplete step.
- Scenario 4: Poor image rejection and retry.
- Scenario 5: Connection validation failure handling.
- Scenario 6: Mock generation failure scenario and retry trigger.
- Scenario 7: Job cancellation handling.
- Scenario 8: Parameter revision and model status STALE setting.
- Scenario 9: Failed revision preserving last-known-good model (ADR-005).
- Scenario 10: Editing Interface A setting model STALE and clearing approval.
- Scenario 11: Backend restart / page reload session hydration from `sessionStorage`.
- Scenario 12: Exit / restart confirmation modal and session reset.
- Scenario 13: Keyboard-only primary flow navigation accessibility.

### 2.8 Backend Gemini Vision Provider Suite (`backend/tests/test_gemini_vision_provider.py`)
- `test_gemini_provider_valid_response`: Parsing valid JSON profile payload from Gemini vision model.
- `test_gemini_provider_malformed_json`: Malformed JSON structure raises `MalformedProviderResponseError`.
- `test_gemini_provider_unsupported_profile_type`: Unrecognized shape string raises `MalformedProviderResponseError`.
- `test_gemini_provider_invalid_confidence`: Confidence out of bounds `[0.0, 1.0]` raises `MalformedProviderResponseError`.
- `test_gemini_provider_non_finite_values`: `NaN` or `Inf` coordinates/values raise `MalformedProviderResponseError`.
- `test_gemini_provider_timeout`: Request timeout raises `MalformedProviderResponseError`.
- `test_gemini_provider_auth_failure`: 401 unauthenticated response raises error with redacted API key.
- `test_gemini_provider_prompt_injection_defense`: Prompt injection text in image is safely ignored.
- `test_gemini_provider_low_confidence_rejection`: Confidence `< 0.60` raises honest `AnalysisRejectedError`.
- `test_mock_fallback_selection`: Missing key or `ANALYSIS_PROVIDER=mock` falls back to `MockAnalysisProvider`.
- `test_secret_redaction_utility`: `sanitize_error_message` scrubs API key patterns.


## Current submission coverage additions

The active plan must retain coverage for OpenCV one-closed-profile extraction, two-point calibration with one known distance, Interface A/B approval ordering, fit-over/fit-inside clearance formulas, X/Y offset and extension sections, LoftPlan authority, KCL 2.0 determinism, six-field Agent allowlisting and confirmation, stale exports, last-known-good recovery, STL/KCL lineage, exact API contracts, frontend route guards, and deployment smoke checks. STEP and angle generation are compatibility/historical scope only.

## Deployment smoke checks

With the frontend and backend deployed, verify health/readiness, `VITE_BACKEND_URL`, CORS, project-token authorization, image/artifact authorization, Mock project creation, and truthful live-provider capability status. Do not call a smoke check live Zoo PASS unless credentials and the provider request actually execute.
