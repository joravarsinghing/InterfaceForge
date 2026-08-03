# InterfaceForge — Geometry Rules & Manufacturing Validation Specifications

**Document Status:** Active Specification  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  
**Schema Version:** `0.1`  
**Stage:** S10.5H — Input Requirements and Honest Upload Guidance  

---

## 0. Input Requirements & Preferred Image Standard (S10.5H)

Per **FR-001** (Image guidance), the upload screens must communicate the supported input standard clearly and honestly.

### 0.1 Preferred Input

The most reliable input for profile extraction is a **clean cross-section image** meeting all of the following criteria:

| Criterion | Requirement |
|:---|:---|
| View angle | Front-facing / orthographic (no perspective) |
| Profile count | One cross-section only |
| Background | Plain, high-contrast background |
| Fill | Solid or clearly shaded material region |
| Annotations | No dimension lines, no text, no arrows, no leaders |
| Center marks | None |
| Overlapping elements | None |
| Completeness | Full profile visible and uncropped |
| Scale | At least one real dimension supplied separately by the user |

### 0.2 Input Quality Classification

The upload screen classifies images into four statuses before analysis begins:

| Status | Signal | Implication |
|:---|:---|:---|
| **Recommended input** | Clean shaded profile, no annotation noise | Best trace fidelity; proceed normally |
| **Usable with review** | Limited text outside profile, profile fully visible | Review SVG trace carefully before approving |
| **Manual cleanup likely** | Leaders/extension lines/center marks touching geometry | Expect false edges; manual SVG correction required |
| **Unsupported** | Cropped, perspective-distorted, severely blurred, or incomplete | Do not attempt to trace; upload a clean image |

**Note:** The client-side classification is a heuristic pre-analysis signal. The authoritative quality assessment comes from the backend GeminiAnalysisProvider after upload.

### 0.3 Why Dimensioned Drawings Are Unreliable

Dimension lines, leaders, extension lines, and center marks are **indistinguishable from profile edges** by OpenCV contour detection. They create:

- False cuts into the outer profile boundary
- False boundary extensions toward annotation endpoints
- Circle-wedge artefacts from crosshair center marks
- Leader line intrusions into internal cavities

**Annotation masking (S10.5G) is Experimental / manual review required.** It reduces annotation noise but does not guarantee zero residual false edges at junction points.

### 0.4 One-Dimension Scale Workflow

Dimensions do not need to be inside the drawing image. The user provides one known real-world measurement separately:

- Overall width
- Overall height
- Hole diameter
- Reference distance

After the trace is generated, the user confirms the measurement. **Scale is never applied automatically.** This is a mandatory approval gate (ADR-004).

### 0.5 Product Truthfulness Rules (S10.5H)

The following claims must **not** appear anywhere in the product UI or documentation:

- "Arbitrary technical drawings are always supported"
- "Annotation masking is production-ready"
- "Gemini cleanup preserves CAD geometry perfectly"
- "Heavily dimensioned drawings are the recommended path"
- "Manufacturing-ready" (before scale confirmation gate)

The following claim must **always be accurate**:

> Dimensioned drawings may introduce false edges and require manual cleanup.

---

## 1. Overview

Per **ADR-001** and **ADR-012**, connection parameters (transition length, lateral offsets, connection parameters) and manufacturing parameters (wall thickness, clearances) define the 3D transition geometry linking Interface A to Interface B. This document defines all mathematical formulas, validation rules, stable error IDs, non-blocking warnings, conservative initial defaults, and engineering limitations.

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
3. **`angled` transition:** Not supported in the submission build.
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
| **Mode** | `mode not in {coaxial, offset}` | **`IF-CONN-002`** | Connection mode must be coaxial or offset. |
| **Length** | `length_mm <= 0` or non-finite | **`IF-CONN-003`** | Transition length must be positive and finite (> 0 mm). |
| **Angle** | `abs(angle_deg) > 45.0` | **`IF-CONN-004`** | Angle exceeds maximum MVP limit of 45.0°. |
| **Mode Angle** | `mode in {coaxial, offset} && angle_deg != 0` | **`IF-CONN-005`** | Angle must be 0° for coaxial and offset modes. |
| **Offset Ratio** | $\frac{\sqrt{\text{offset\_x}^2 + \text{offset\_y}^2}}{\text{length\_mm}} > 1.5$ | **`IF-CONN-006`** | Lateral offset relative to length exceeds 1.5 ratio limit. |
| **Mode Offset** | `mode == coaxial && (offset_x != 0 \|\| offset_y != 0)` | **`IF-CONN-007`** | X/Y offsets must be 0 mm for coaxial mode. |
| **Profile Scope**| `profile_type == traced_closed` | **`IF-CONN-008`** | Approved traced closed profiles are supported for final generation after validation and approval. |
| **Self-Intersection**| $\text{total\_span} > 1.8 \cdot \text{length\_mm} + \min(D_A, D_B)$ | **`IF-CONN-009`** | Loft self-intersection risk due to excessive angle/offset. |
| **Wall Thickness**| `wall_thickness_mm <= 0` or non-finite | **`IF-MFG-001`** | Wall thickness must be positive and finite (> 0 mm). |
| **Min Printable Wall**| `wall_thickness_mm < 0.4` | **`IF-MFG-002`** | Wall thickness below absolute printable limit (0.4 mm). |
| **Clearance B** | `clearance_b_mm < 0 \|\| > 5.0` | **`IF-CONN-008`** | Interface B clearance must be between 0.0 mm and 5.0 mm. |

---

## 4. Complex Profile Tracing & Scale Validation Rules (Stage S10.4)

### 4.1 Contour Geometry Rules
1. **Outer Boundary Closure:** Traced outer contour must be closed (`is_closed == true`) with at least 4 ordered 2D vertices.
2. **Self-Intersection Check:** No 2D line segment of the outer or inner contour may cross another non-adjacent segment ($\text{segment}_i \cap \text{segment}_j = \emptyset$).
3. **Negative Region Classification:** Internal cavities are categorized as `hole` (circular/oval bore), `cavity` (arbitrary enclosed pocket), or `slot` (long recess).
4. **User Region Decisions:** Each negative contour supports explicit user decision state:
   - `include`: Preserved as open interior opening in adapter model.
   - `ignore`: Filled/treated as solid material.
   - `unsure`: Flagged for review; user approval required.

### 4.2 Scale Calibration & Approval Gate
1. **Scale Confirmation Mandatory Gate:** Profile approval (`/approve`) is strictly blocked if `scale_calibration.confirmed == false` for `traced_closed` profiles.
2. **Real Distance Validation:** `scale_calibration.real_distance_mm` must be a positive finite float ($> 0.0$ mm).
3. **Primitive Fallback Labeling:** When user toggles primitive envelope fallback, system forces `primitive_fallback_active = true` and attaches mandatory text: `"Simplified envelope — not the exact cross-section"`.
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
3. **Stable Identifiers:** Constant variable names follow predictable identifiers (`interfaceAOuterDiameterMm`, `wallThicknessMm`, `transitionLengthMm`, `sketchOuter0`, `sketchOuter1`, `outerSolid`, `adapterModel`).

### 5.2 Geometry Scope & Supported Families (in Order of Evaluation)
1. **Circular Coaxial Hollow Adapter:** Circle to circle, `offset_x = 0`, `offset_y = 0`, `angle = 0`.
2. **Rectangular / Rounded-Rectangle Coaxial Transition:** Rectangle/rounded-rectangle to rectangle/rounded-rectangle or circle, `offset_x = 0`, `offset_y = 0`, `angle = 0`.
3. **Circular Offset Adapter:** Circle to circle, parallel z-planes with non-zero lateral offset (`offset_x`, `offset_y`), `angle = 0`.
4. **Angle-based adapters:** Not supported in the submission build.

### 5.3 KCL Assumptions Requiring Zoo Verification (Stage S5B)
1. **Loft Interpolation Across Dissimilar Profiles:** Lofting a circle to a rounded rectangle via `loft([sketch_a, sketch_b])` is syntactically valid in KCL, but exact surface curvature and tangent continuity require Zoo Engine execution verification.
2. **Angled Plane Sketch Alignment:** Constructing an inclined top plane via `plane(origin = [...], xAxis = [...], yAxis = [...])` requires Zoo Engine execution to confirm plane normal direction and winding.
3. **Solid-body generation:** Current KCL 2.0 solid-body generation is the submission path.

---

## 6. Geometry Fidelity Verification & Tolerance Standards (Stage S8.4)

Per **ADR-001** and **ADR-003**, exported CAD models must be verified for geometric fidelity against requested canonical parameters:

1. **Linear Dimension Tolerance:** Measured STL bounding box and profile dimensions must match requested schema values within **±0.2 mm**.
2. **Angle-based output:** No angle-based output claim is made for the submission.
3. **Lateral Offset Tolerance:** Measured bounding box span must reflect requested `offset_x` and `offset_y` translation within **±0.2 mm**.
4. **Hollow Passage Verification:** Every exported adapter solid must contain a hollow passage created via solid-body subtraction, producing non-box facet topologies (> 12 facets for STL).
5. **Non-Box Topology Requirement:** Uniform 12-facet / 684-byte solid boxes are rejected as unproven fallback geometry.


