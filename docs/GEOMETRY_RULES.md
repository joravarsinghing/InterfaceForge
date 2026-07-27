# InterfaceForge — Geometry Rules & Manufacturing Validation Specifications

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Schema Version:** `0.1`  
**Stage:** S4C — Connection Configuration and Manufacturing Rules  

---

## 1. Overview

Per **ADR-001** and **ADR-012**, connection parameters (transition length, lateral offsets, angle inclination) and manufacturing parameters (wall thickness, clearances) define the 3D transition geometry linking Interface A to Interface B. This document defines all mathematical formulas, validation rules, stable error IDs, non-blocking warnings, conservative initial defaults, and engineering limitations.

---

## 2. Connection Parameters & Modes

### 2.1 Alignment Modes
1. **`coaxial` (Coaxial Alignment):**
   - Interfaces A and B share a single straight central axis.
   - Requirements: `offset_x_mm = 0`, `offset_y_mm = 0`, `angle_deg = 0`.
2. **`offset` (Parallel Offset Alignment):**
   - Interfaces A and B remain parallel (z-planes parallel) with lateral translation.
   - Parameters: `offset_x_mm`, `offset_y_mm`.
   - Requirements: `angle_deg = 0`.
3. **`angled` (Limited-Angle Transition):**
   - Interface B is inclined relative to Interface A by an angle up to 45°.
   - Parameters: `length_mm`, `offset_x_mm`, `offset_y_mm`, `angle_deg`.

---

## 3. Parametric Validation Rules & Conservative Limits

### 3.1 Initial Configurable Defaults
- **Default Transition Length (`length_mm`):** `40.0` mm
- **Default Wall Thickness (`wall_thickness_mm`):** `2.4` mm
- **Default Clearance A (`clearance_a_mm`):** `0.3` mm
- **Default Clearance B (`clearance_b_mm`):** `0.1` mm
- **Default Lateral Offsets (`offset_x_mm`, `offset_y_mm`):** `0.0` mm
- **Default Angle (`angle_deg`):** `0.0`°

*Note: Initial defaults are conservative heuristic choices for standard FDM 3D printing and are not certified engineering structural calculations.*

### 3.2 Hard Blocking Limits & Error IDs

| Parameter | Condition / Boundary | Error ID | Description |
| :--- | :--- | :--- | :--- |
| **Prerequisites** | `!interface_a.approved \|\| !interface_b.approved` | **`IF-CONN-001`** | Both Interface A and Interface B must be approved first. |
| **Mode** | `mode not in {coaxial, offset, angled}` | **`IF-CONN-002`** | Connection mode must be coaxial, offset, or angled. |
| **Length** | `length_mm <= 0` or non-finite | **`IF-CONN-003`** | Transition length must be positive and finite (> 0 mm). |
| **Angle** | `abs(angle_deg) > 45.0` | **`IF-CONN-004`** | Angle exceeds maximum MVP limit of 45.0°. |
| **Mode Angle** | `mode in {coaxial, offset} && angle_deg != 0` | **`IF-CONN-005`** | Angle must be 0° for coaxial and offset modes. |
| **Offset Ratio** | $\frac{\sqrt{\text{offset\_x}^2 + \text{offset\_y}^2}}{\text{length\_mm}} > 1.5$ | **`IF-CONN-006`** | Lateral offset relative to length exceeds 1.5 ratio limit. |
| **Mode Offset** | `mode == coaxial && (offset_x != 0 \|\| offset_y != 0)` | **`IF-CONN-007`** | X/Y offsets must be 0 mm for coaxial mode. |
| **Profile Scope**| `profile_type == traced_closed` | **`IF-CONN-008`** | Unsupported profile geometry combination. |
| **Self-Intersection**| $\text{total\_span} > 1.8 \cdot \text{length\_mm} + \min(D_A, D_B)$ | **`IF-CONN-009`** | Loft self-intersection risk due to excessive angle/offset. |
| **Wall Thickness**| `wall_thickness_mm <= 0` or non-finite | **`IF-MFG-001`** | Wall thickness must be positive and finite (> 0 mm). |
| **Min Printable Wall**| `wall_thickness_mm < 0.4` | **`IF-MFG-002`** | Wall thickness below absolute printable limit (0.4 mm). |
| **Clearance Bounds**| `clearance < 0.0` or `clearance > 5.0` | **`IF-MFG-003`** | Clearance must be between 0.0 mm and 5.0 mm. |
| **Internal Collapse**| `wall_thickness_mm >= min(D_A, D_B) / 2.0` | **`IF-MFG-004`** | Wall thickness collapses internal flow passage. |

### 3.3 Non-Blocking Warnings

| Warning ID | Parameter Threshold | Description & Recommendation |
| :--- | :--- | :--- |
| **`IF-CONN-W001`** | `length_mm < 10.0` | Transition length is very short (< 10 mm), leading to steep loft angles. Recommend >= 20 mm. |
| **`IF-CONN-W002`** | `length_mm > 300.0` | Transition length is unusually long (> 300 mm), increasing print volume. |
| **`IF-CONN-W003`** | `abs(angle_deg) > 30.0` | Angle > 30° requires overhang support structures during 3D printing. |
| **`IF-CONN-W004`** | $\text{ratio} > 1.0$ | High offset-to-length ratio (> 1.0) may cause geometry skew. |
| **`IF-MFG-W001`** | `wall_thickness_mm < 1.2` | Wall thickness below FDM recommended minimum (1.2 mm). |
| **`IF-MFG-W002`** | `wall_thickness_mm > 15.0` | Wall thickness unusually thick (> 15 mm), increasing print time and thermal warping risk. |
| **`IF-MFG-W003`** | `clearance < 0.1` | Clearance below 0.1 mm may cause tight press-fit interference. |

---

---

## 5. KCL Emission Rules & Unverified Zoo Assumptions (Stage S5A)

### 5.1 KCL Emitter Determinism
1. **Deterministic String Emission:** Identical canonical JSON schema and compiler version (`v1.0.0`) produce byte-for-byte identical KCL output.
2. **Explicit Units:** `@settings(defaultLengthUnit = mm)` is declared at the top of every emitted KCL file.
3. **Stable Identifiers:** Constant variable names follow predictable identifiers (`interface_a_outer_diameter_mm`, `wall_thickness_mm`, `transition_length_mm`, `sketch_outer_a`, `sketch_outer_b`, `outer_solid`, `inner_void`, `adapter_model`).

### 5.2 Geometry Scope & Supported Families (in Order of Evaluation)
1. **Circular Coaxial Hollow Adapter:** Circle to circle, `offset_x = 0`, `offset_y = 0`, `angle = 0`.
2. **Rectangular / Rounded-Rectangle Coaxial Transition:** Rectangle/rounded-rectangle to rectangle/rounded-rectangle or circle, `offset_x = 0`, `offset_y = 0`, `angle = 0`.
3. **Circular Offset Adapter:** Circle to circle, parallel z-planes with non-zero lateral offset (`offset_x`, `offset_y`), `angle = 0`.
4. **Limited-Angle Adapter:** Inclined top plane (up to 45°) with `angle_deg != 0`.

### 5.3 KCL Assumptions Requiring Zoo Verification (Stage S5B)
1. **Loft Interpolation Across Dissimilar Profiles:** Lofting a circle to a rounded rectangle via `loft([sketch_a, sketch_b])` is syntactically valid in KCL, but exact surface curvature and tangent continuity require Zoo Engine execution verification.
2. **Angled Plane Sketch Alignment:** Constructing an inclined top plane via `plane(origin = [...], xAxis = [...], yAxis = [...])` requires Zoo Engine execution to confirm plane normal direction and winding.
3. **Void Subtraction Robustness:** Subtracting an inner lofted void solid from an outer lofted solid via `subtract(outer_solid, tools = [inner_void])` requires Zoo Engine execution to verify manifold solid output without non-manifold geometry edge errors.

---

## 6. Geometry Fidelity Verification & Tolerance Standards (Stage S8.4)

Per **ADR-001** and **ADR-003**, exported CAD models must be verified for geometric fidelity against requested canonical parameters:

1. **Linear Dimension Tolerance:** Measured STL/STEP bounding box and profile dimensions must match requested schema values within **±0.2 mm**.
2. **Angle Inclination Tolerance:** Measured top plane orientation must match requested inclination angle within **±0.5°**.
3. **Lateral Offset Tolerance:** Measured bounding box span must reflect requested `offset_x` and `offset_y` translation within **±0.2 mm**.
4. **Hollow Passage Verification:** Every exported adapter solid must contain a hollow passage created via inner void subtraction (`boolean_subtract`), producing non-box facet topologies (> 12 facets for STL).
5. **Non-Box Topology Requirement:** Uniform 12-facet / 684-byte solid boxes are rejected as unproven fallback geometry.


