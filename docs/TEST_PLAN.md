# InterfaceForge — Test Plan & Execution Strategy

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
- `test_validate_all_three_valid_modes`: Verifies coaxial, offset, and angled modes pass validation when parameters are within bounds.
- `test_prerequisite_approval_failure`: Verifies validation fails if either Interface A or B is not approved (`IF-CONN-001`).
- `test_invalid_negative_or_non_finite_length_and_wall`: Negative or non-finite length or wall thickness returns blocking errors (`IF-CONN-003`, `IF-MFG-001`).
- `test_excessive_angle_limit`: Angle > 45° returns blocking error (`IF-CONN-004`).
- `test_excessive_offset_to_length_ratio`: Offset-to-length ratio > 1.5 returns blocking error (`IF-CONN-006`).
- `test_wall_thickness_warnings_and_errors`: Wall thickness < 0.4 mm returns error (`IF-MFG-002`), < 1.2 mm returns FDM warning (`IF-MFG-W001`).
- `test_clearance_bounds`: Clearances outside [0.0, 5.0] mm produce blocking errors (`IF-MFG-003`).
- `test_mode_parameter_mismatch_rules`: Non-zero offsets or angle in coaxial mode returns errors (`IF-CONN-005`, `IF-CONN-007`).
- `test_project_service_connection_update_and_stale_model_behavior`: Service updates connection, increments schema revision, marks model stale, and preserves last-known-good model.

### 2.5 Backend KCL Compiler Suite (`backend/tests/test_kcl_compiler.py`)
- `test_circular_coaxial_compilation`: Validates circular coaxial adapter emits explicit mm units, required variables, loft/subtract calls, and artifact reference.
- `test_rectangular_coaxial_compilation`: Validates rectangle to rounded rectangle transition emits correct width, height, corner radius, and tangential arcs.
- `test_circular_offset_compilation`: Validates offset mode emits lateral translation parameters.
- `test_angled_compilation`: Validates angled mode emits inclined top plane construction.
- `test_invalid_unsupported_profile`: Profile type `traced_closed` fails pre-flight compilation with `IF-KCL-001`.
- `test_non_finite_input`: Non-finite numbers fail compilation with `IF-KCL-002`.
- `test_unapproved_prerequisites_fail`: Unapproved interfaces fail compilation with `IF-KCL-003`.
- `test_repeated_identical_compilation_is_deterministic`: Repeated compilation of identical schema produces byte-for-byte identical KCL output and hash.
- `test_project_service_kcl_compilation_does_not_mark_current`: KCL compilation creates a draft model revision but does not set status to `current` and executes zero Zoo API calls.

### 2.6 Frontend UI & Component Tests (`frontend/src/test/`)
- TypeScript schema contract parsing and type checking (`schema.test.ts`).
- App shell navigation and health status rendering (`App.test.tsx`).
- UploadPage dropzone, file selection, preview, guidance panel, and cancel actions (`UploadPage.test.tsx`).
- ProfileReviewPage side-by-side view, profile selector, provenance text/icons, validation summary, and approval flow (`ProfileReviewPage.test.tsx`).
- ConnectionConfigPage mode selection cards (coaxial, offset, angled), mode switching, numeric input form controls, live 2D SVG schematic rendering, field-level validation errors, warning summary, blocking error summary, and save/proceed navigation (`ConnectionConfigPage.test.tsx`).
- ModelGenerationPage pre-flight readiness check, compile trigger button, metadata panel (compiler version, revision, SHA-256 hash, artifact path), execution status badge, read-only source preview snippet, and navigation routing (`ModelGenerationPage.test.tsx`).

