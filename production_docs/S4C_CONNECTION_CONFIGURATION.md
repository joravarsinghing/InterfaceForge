# Stage S4C — Connection Configuration and Manufacturing Rules

**Stage Status:** Complete  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Date:** July 23, 2026  
**Primary Author:** Antigravity AI  

> **Historical / Superseded:** This stage report records its historical state and outcomes; it is not the current submission capability contract. Current truth: KCL 2.0 solid-body generation works; supported outputs are STL and KCL; STEP is planned but not implemented; supported connection modes are coaxial and offset; angle-based connections are unsupported; historical surface-shell, `joinSurfaces()`, Boolean-blocker, and deprecated-KCL notes are superseded; live Zoo Agent execution remains unproven unless credential-tested.

---

## 1. Executive Summary

Stage S4C delivers guided connection configuration for approved Interface A and Interface B. It introduces a dedicated backend geometry/manufacturing validation service (`backend/app/services/connection_validation.py`), supporting coaxial, parallel offset, and limited-angle transition modes. It validates prerequisites, positive finite dimensions, clearance bounds, angle limits (<= 45°), offset-to-length ratios (<= 1.5), mode parameter consistency, profile prerequisites, and self-intersection risks, returning stable error IDs, non-blocking warnings, and recommended default values.

On the frontend, S4C provides interactive connection mode selection cards with concise explanations, a mode-specific parameter form with numeric stepper inputs, a live reactive 2D SVG schematic viewer (`frontend/src/components/Connection2DViewer.tsx`), an approved interface summary bar, field-level validation highlights, warning/error summary panels, and navigation routing to Step 4 ("Generate Model"). Updating connection or manufacturing settings increments the canonical schema revision, marks current 3D models stale, and preserves last-known-good model metadata per ADR-005.

---

## 2. Initial Rule Configuration & Engineering Rationale

### 2.1 Configurable Initial Defaults
- **Transition Length (`length_mm`):** `40.0` mm (Provides a gradual transition angle for typical port sizes ~40-60mm).
- **Wall Thickness (`wall_thickness_mm`):** `2.4` mm (Optimum 3-wall shell thickness for 0.8mm extrusion or 6-wall shell for 0.4mm nozzle in FDM printing).
- **Clearance A (`clearance_a_mm`):** `0.3` mm (Standard slip-fit clearance for FDM 3D printed female receiver ports).
- **Clearance B (`clearance_b_mm`):** `0.1` mm (Tighter press-fit clearance for male insertion plugs).
- **Lateral Offsets (`offset_x_mm`, `offset_y_mm`):** `0.0` mm (Aligned default baseline).
- **Inclination Angle (`angle_deg`):** `0.0`° (Straight default baseline).

*Note: Initial defaults are conservative heuristic choices for initial CAD setup and are not certified engineering structural values.*

### 2.2 Hard Blocking Limits & Stable Error IDs

| Parameter | Boundary Condition | Error ID | Rationale |
| :--- | :--- | :--- | :--- |
| **Prerequisites** | `!interface_a.approved \|\| !interface_b.approved` | `IF-CONN-001` | Connection cannot be computed without approved boundary contours. |
| **Mode** | `mode not in {coaxial, offset, angled}` | `IF-CONN-002` | Enforces supported MVP connection modes per ADR-012. |
| **Length** | `length_mm <= 0` or non-finite | `IF-CONN-003` | Non-positive or infinite length produces degenerate 3D loft topology. |
| **Angle Limit** | `abs(angle_deg) > 45.0` | `IF-CONN-004` | Exceeds MVP maximum angle limit per ADR-012. |
| **Mode Angle** | `mode != angled && angle != 0` | `IF-CONN-005` | Angle is invalid for coaxial or offset modes. |
| **Offset Ratio** | $\frac{\text{offset\_dist}}{\text{length}} > 1.5$ | `IF-CONN-006` | Ratio > 1.5 causes extreme lofting skew and print failures. |
| **Mode Offset** | `mode == coaxial && offsets != 0` | `IF-CONN-007` | Offsets are invalid for coaxial mode. |
| **Profile Scope**| `profile_type == traced_closed` | `IF-CONN-008` | Traced profiles are deferred post-MVP. |
| **Self-Intersection**| Total lateral/angular span > $1.8 L + \min(D_A, D_B)$ | `IF-CONN-009` | Conservative check detecting self-colliding loft geometry. |
| **Wall Thickness**| `wall_thickness_mm <= 0` or non-finite | `IF-MFG-001` | Non-positive wall thickness yields zero physical volume. |
| **Min Printable Wall**| `wall_thickness_mm < 0.4` | `IF-MFG-002` | Below 0.4mm nozzle width limit in FDM printers. |
| **Clearance Bounds**| `clearance < 0.0` or `clearance > 5.0` | `IF-MFG-003` | Clearance outside 0-5mm causes fit failure or extreme slop. |
| **Internal Collapse**| `wall_thickness_mm >= min(D_A, D_B) / 2.0` | `IF-MFG-004` | Wall thickness exceeds internal radius, closing internal passage. |

### 2.3 Non-Blocking Warnings

| Warning ID | Threshold Condition | Rationale & Guidance |
| :--- | :--- | :--- |
| `IF-CONN-W001` | `length_mm < 10.0` | Short transition length (< 10mm) leads to steep loft angles and stress points. |
| `IF-CONN-W002` | `length_mm > 300.0` | Long transition (> 300mm) increases print time and print volume substantially. |
| `IF-CONN-W003` | `abs(angle_deg) > 30.0` | Angle > 30° requires overhang support structures during FDM printing. |
| `IF-CONN-W004` | $\text{ratio} > 1.0$ | High offset-to-length ratio (> 1.0) may result in severe geometry skew. |
| `IF-MFG-W001` | `wall_thickness_mm < 1.2` | Thin wall (< 1.2mm) may be mechanically weak for FDM parts. |
| `IF-MFG-W002` | `wall_thickness_mm > 15.0` | Thick wall (> 15mm) increases thermal warping and material consumption. |
| `IF-MFG-W003` | `clearance < 0.1` | Clearance < 0.1mm may cause tight press-fit binding. |

### 2.4 Unresolved Physical Parameters
1. **Material Contraction & Printer Shrinkage:** Requires empirical test-print calibration per filament brand.
2. **Fluid Pressure Rating & Hermetic Sealing:** Wall thickness heuristic does not certify pressure containment.
3. **Structural Load Capacity:** Bending moment, tensile strength, and fatigue limits require post-MVP FEA analysis.

---

## 3. Implemented Components

### 3.1 Backend Connection Validation Service (`backend/app/services/connection_validation.py`)
- Independent validation function `validate_connection_and_manufacturing`.
- Enforces prerequisite approvals, mode rules, finite bounds, angle limits, offset ratio limits, wall thickness limits, clearance bounds, and self-intersection risks.
- Returns structured `ConnectionValidationResult` (`is_valid`, `blocking_errors`, `warnings`, `recommended_values`).

### 3.2 Backend Service & API Enhancements (`backend/app/services/project_service.py` & `projects.py`)
- `validate_connection_config`: Validates connection parameters against project interfaces.
- `update_connection` & `update_manufacturing`: Enforces structural validation, updates project schema, increments `current_schema_revision`, marks current model `stale`, and updates workflow state to `connection_configured`.
- `update_connection_config`: Atomically updates both connection and manufacturing parameters in a single API request.
- `POST /api/projects/{project_id}/validate-connection`: Endpoint returning live validation feedback.
- `PUT /api/projects/{project_id}/connection-config`: Endpoint persisting valid connection settings.

### 3.3 Frontend Live 2D Schematic Viewer (`frontend/src/components/Connection2DViewer.tsx`)
- SVG vector schematic rendering XZ cross-sectional elevation.
- Visualizes Interface A base bar, Interface B top bar (inclined and offset), central ray line, outer shell loft, inner flow passage, transition length callout, offset vector, angle callouts, wall thickness, and clearance annotations.
- Fully accessible with `<svg role="img" aria-label="...">`, `<title>`, and `<desc>`.

### 3.4 Connection Configuration Page (`frontend/src/pages/ConnectionConfigPage.tsx`)
- **Interface Summary Bar:** Displays approved status for Interface A and B with profile type and re-edit link.
- **Connection Mode Cards:** Selectable cards for Coaxial, Parallel Offset, and Limited Angle modes with concise explanations.
- **Parameter Form:** Numeric inputs for transition length, wall thickness, clearance A, clearance B, X/Y offsets, angle, process (FDM/SLA/CNC), and material.
- **Validation Summary Panel:** Live validation status badge, field-level inline error messages, non-blocking warning summary, blocking-error summary, and "Apply Recommended Values" action.
- **Navigation Controls:** "Back to Profile Review" and "Save Connection & Continue to Model Generation" (enabled only when configuration is valid).

---

## 4. Test Evidence

### 4.1 Backend Pytest Test Suite (`backend/tests/test_connection_validation.py`)
- `test_validate_all_three_valid_modes`: Validates coaxial, offset, and angled modes pass cleanly.
- `test_prerequisite_approval_failure`: Verifies validation fails if either interface is unapproved (`IF-CONN-001`).
- `test_invalid_negative_or_non_finite_length_and_wall`: Verifies negative/non-finite length and wall thickness fail (`IF-CONN-003`, `IF-MFG-001`).
- `test_excessive_angle_limit`: Verifies angle > 45° returns `IF-CONN-004`.
- `test_excessive_offset_to_length_ratio`: Verifies ratio > 1.5 returns `IF-CONN-006`.
- `test_wall_thickness_warnings_and_errors`: Verifies wall < 0.4mm yields error `IF-MFG-002`, < 1.2mm yields FDM warning `IF-MFG-W001`.
- `test_clearance_bounds`: Verifies clearance outside [0, 5]mm yields `IF-MFG-003`.
- `test_mode_parameter_mismatch_rules`: Verifies coaxial mode with offsets/angle returns `IF-CONN-005` and `IF-CONN-007`.
- `test_project_service_connection_update_and_stale_model_behavior`: Verifies schema revision increment, stale model status, and preservation of last-known-good model.

### 4.2 Frontend Vitest Test Suite (`frontend/src/test/ConnectionConfigPage.test.tsx`)
- Renders interface summary bar and coaxial/offset/angled mode cards.
- Mode switching activates X/Y offset and angle fields cleanly.
- Displays field-level errors and blocks proceed button when validation fails.
- Saves valid connection settings via API and navigates to Step 4.

### 4.3 Automated Verification Results
Executed via `venv\Scripts\python.exe -m pytest backend/tests`, `npm run test`, `npx tsc --noEmit`, and `npm run lint`:

```text
Backend Pytest Suite: 38 passed in 2.28s
Frontend Vitest Suite: 21 passed in 1.96s
Frontend TypeScript Check (tsc): Passed cleanly (0 errors)
Frontend ESLint Check: Passed cleanly (0 errors / max 0 warnings)
```

---

## 5. Scope & ADR Compliance

- **No KCL Generation / No Zoo API:** Deferred strictly to Stage S5 per ADR-002, ADR-006.
- **No Draggable 3D Manipulators:** Form numeric inputs provided for all values per ADR-008.
- **Non-Color Validation:** Validation status, errors, and warnings rely on explicit icons (`✓`, `⛔`, `⚠️`), text headers (`[VALID]`, `[ERROR]`), and ARIA live regions.
- **Schema Revision & Staleness:** ADR-001 and ADR-005 rules strictly enforced.

---

## 6. Exit Checklist

- [x] Backend connection validation service implemented and tested.
- [x] Backend update and validation endpoints updated and tested.
- [x] Connection2DViewer built and tested for live SVG rendering.
- [x] ConnectionConfigPage implemented with mode cards, numeric forms, live 2D guide, field validation, warnings, errors, and navigation.
- [x] All 38 backend pytest tests and 21 frontend vitest tests pass.
- [x] Documentation updated (`docs/GEOMETRY_RULES.md`, `docs/DESIGN_SCHEMA.md`, `docs/API_USAGE.md`, `docs/TEST_PLAN.md`, `docs/BUGS_AND_LIMITATIONS.md`).
- Stage S4C is complete and ready to close.
