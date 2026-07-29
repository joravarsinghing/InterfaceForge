# InterfaceForge — Bugs and Limitations Log

**Document Status:** Active Log  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Active Stage Limitations (Stage S10.5H — Input Requirements and Honest Upload Guidance)

1. **Preferred Input: Clean Cross-Section Only (S10.5H):** The supported and reliable input is a clean cross-section image without dimension annotations. Upload guidance on both Interface A and B screens now communicates this explicitly with a preferred input section, example illustrations, checklist, and quality status badge.

2. **Dimensioned Drawing Support: Experimental / Manual Review Required (S10.5H):** Dimensioned engineering drawings (with leaders, extension lines, center marks, and text) are **not automatically supported**. Annotation masking (S10.5G/S10.5G.1) is an experimental pre-processing step that reduces but does not eliminate false edges. The traced SVG profile must be reviewed and corrected manually before approval.

3. **Gemini Cleanup Does Not Preserve CAD Geometry Perfectly:** Gemini vision analysis identifies annotation regions for masking — it does not redraw or reconstruct profile geometry. False edges near masked annotation junctions may persist. This is documented as a known limitation, not a production capability.

4. **One-Dimension Scaling — User Confirmation Mandatory (S10.5H, ADR-004):** Scale calibration from a user-supplied known measurement is not automatically applied. The user must explicitly confirm the scale after the trace is reviewed. No manufacturing-ready output is claimed before this gate.

5. **Input Quality Classification is Heuristic Only (S10.5H):** The client-side quality classification (Recommended / Usable with review / Manual cleanup likely / Unsupported) is a filename-based heuristic. It is a pre-analysis signal, not a guarantee. The authoritative quality assessment comes from the backend GeminiAnalysisProvider after upload.

6. **Live Zoo Agent API Bounded Revisions Active (S9):** Natural-language model revisions use live Zoo Copilot WebSocket API (`wss://api.zoo.dev/ws/ml/copilot`). AI proposals are strictly bounded by a 7-field server-side allowlist (`connection.length_mm`, `connection.offset_x_mm`, `connection.offset_y_mm`, `connection.angle_deg`, `manufacturing.wall_thickness_mm`, `manufacturing.clearance_a_mm`, `manufacturing.clearance_b_mm`). Direct CAD/KCL code generation by the AI is strictly prohibited.
7. **User Confirmation Gate Enforced:** Changes are presented as unapplied proposals in a before/after review panel. Canonical schema parameters, KCL compilation, and 3D generation execute ONLY after explicit user confirmation.
8. **Preservation of Last-Known-Good Model (ADR-005):** Failed 3D regeneration attempts preserve the last successful model revision without overwriting active model state.
9. **Live Export Geometry Fidelity Audit PASSED (S8.4):** Proven that Zoo-native exported CAD geometry matches requested canonical design parameters (coaxial, parallel offset, angled, dissimilar profile transitions) with real hollow passage subtraction (`boolean_subtract`), matching linear dimensions (±0.2mm) and angle inclinations (±0.5°). Uniform 12-facet solid box fallbacks are eliminated.
10. **Live Native WebSocket Export Active (S8.3 & S8.4):** Exports execute native `export` command directly on Zoo Engine WebSocket gateway (`wss://api.zoo.dev/ws/modeling/commands`) using `loft` and `boolean_subtract` modeling commands. Local OBJ mesh generator is strictly prohibited in production export path.
11. **Deep Topology & Geometry Validation Active:** File format validation uses `parse_and_validate_stl()` and `parse_and_validate_step()`, rejecting empty ASCII STL files, zero-facet binary STL files, header-only STEP files, and STEP files lacking solid body entities.
12. **Live Gemini Vision Provider Active & Verified (S7.3):** Real multimodal vision analysis (`GeminiAnalysisProvider`) uses `gemini-3.5-flash-lite` by default (`GEMINI_VISION_MODEL`) with single fallback to `gemini-3.6-flash`.
13. **Camera Angle & Lighting Sensitivity:** Automatic vision profile extraction requires direct square-on camera orientation and adequate lighting; off-axis perspective skew or severe shadows trigger honest low-confidence rejection (< 0.60).
14. **Live Zoo Engine Execution Active:** Stage S6 implements live Zoo Engine execution (`ZooEngineProvider`) via `wss://api.zoo.dev/ws/modeling/commands` with `MockEngineProvider` available as configurable fallback.
15. **Supported Profile Scope:** Geometry scope remains strictly constrained to `circle`, `rectangle`, `rounded_rectangle`, and `traced_closed` per ADR-012.



---

## 2. Bug Tracking & Resolved Issues

* **P0 Defects (Resolved in S6A.5):**
  - **RESOLVED:** Fixed runtime `Cannot read properties of undefined (reading 'approved')` crash by introducing optional chaining on `project?.interface_a?.approved` and `project?.interface_b?.approved` across all workflow components, route guards (`ProtectedRoute`), and navigation helpers (`workflow.ts`). Added session recovery for expired or malformed session state.
* **P1/P2 Defect Fixes (Resolved in S6A.5):**
  - **Upload Page Stabilization:** Rebuilt Upload Page with styled drag-and-drop card, hidden accessible native file input, fixed `object-fit: contain` responsive preview frame, compact metadata panel, and structured GOOD/BAD guidance cards.
  - **Visual Hierarchy & Theme:** Enforced approved dark/neon-green theme token direction (`--accent-neon-green`), removing purple as dominant CTA color. Demoted prominent developer banners on Landing Page into a collapsible details section.
  - **Privacy Wording Correction:** Updated user-facing privacy copy in Footer and documentation to accurately explain local SQLite backend persistence and temporary file storage.
* **P1/P2 Non-Blocking Notices:**
  - JSDOM test runner emits React Router v7 startTransition future flag warnings during test execution (non-blocking, standard React Router v6 migration notice).

### 2026-07-29 - P0 Golden Path Live STL/STEP Export Blocker

- **Status:** Active blocker for Day 1 AM golden path proof.
- **Scope:** Live Zoo-native STL and STEP export after successful live model generation for circle -> rounded_rectangle adapter.
- **Observed:** KCL export is ready, but STL and STEP exports fail with `IF-EXPORT-001` because Zoo Engine returns: `The Zoo engine cannot handle this 3D subtraction yet. Please report this as an issue`.
- **Impact:** The workflow is PARTIAL/UNPROVEN for valid STL and STEP downloads in Live mode. Mock or local geometry output must not be used as proof.
- **Workaround:** None accepted for the P0 proof. Preserve validation and report the blocker.

### 2026-07-29 - Zoo KCL Export Runtime Compatibility Blocker

- **Status:** Active environment blocker for live STL/STEP proof in the current Python 3.10 backend venv.
- **Scope:** Authoritative export from the stored KCL/model revision without rebuilding a second WebSocket model.
- **Observed:** `pip install zoo-kcl` reports available releases require Python >=3.11, while `backend/pyproject.toml` pins runtime support to Python >=3.10,<3.11. The local `zoo` CLI is also not installed, and `ZOO_API_TOKEN` is not configured in this environment.
- **Impact:** The code path is covered by tests with a fake KCL executor, but live STL/STEP artifacts remain UNPROVEN until the backend runtime is upgraded/provisioned with a supported Zoo KCL export tool and credentials.
- **Rejected workaround:** Do not fall back to local OBJ conversion, mock exports, or separate non-hollow solids as proof.
