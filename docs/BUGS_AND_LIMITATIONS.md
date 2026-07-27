# InterfaceForge — Bugs and Limitations Log

**Document Status:** Active Log  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Active Stage Limitations (Stage S9 — Bounded Zoo Agent Revisions)

1. **Live Zoo Agent API Bounded Revisions Active (S9):** Natural-language model revisions use live Zoo Copilot WebSocket API (`wss://api.zoo.dev/ws/ml/copilot`). AI proposals are strictly bounded by a 7-field server-side allowlist (`connection.length_mm`, `connection.offset_x_mm`, `connection.offset_y_mm`, `connection.angle_deg`, `manufacturing.wall_thickness_mm`, `manufacturing.clearance_a_mm`, `manufacturing.clearance_b_mm`). Direct CAD/KCL code generation by the AI is strictly prohibited.
2. **User Confirmation Gate Enforced:** Changes are presented as unapplied proposals in a before/after review panel. Canonical schema parameters, KCL compilation, and 3D generation execute ONLY after explicit user confirmation.
3. **Preservation of Last-Known-Good Model (ADR-005):** Failed 3D regeneration attempts preserve the last successful model revision without overwriting active model state.
4. **Live Export Geometry Fidelity Audit PASSED (S8.4):** Proven that Zoo-native exported CAD geometry matches requested canonical design parameters (coaxial, parallel offset, angled, dissimilar profile transitions) with real hollow passage subtraction (`boolean_subtract`), matching linear dimensions (±0.2mm) and angle inclinations (±0.5°). Uniform 12-facet solid box fallbacks are eliminated.
5. **Live Native WebSocket Export Active (S8.3 & S8.4):** Exports execute native `export` command directly on Zoo Engine WebSocket gateway (`wss://api.zoo.dev/ws/modeling/commands`) using `loft` and `boolean_subtract` modeling commands. Local OBJ mesh generator is strictly prohibited in production export path.
6. **Deep Topology & Geometry Validation Active:** File format validation uses `parse_and_validate_stl()` and `parse_and_validate_step()`, rejecting empty ASCII STL files, zero-facet binary STL files, header-only STEP files, and STEP files lacking solid body entities.
7. **Live Gemini Vision Provider Active & Verified (S7.3):** Real multimodal vision analysis (`GeminiAnalysisProvider`) uses `gemini-3.5-flash-lite` by default (`GEMINI_VISION_MODEL`) with single fallback to `gemini-3.6-flash`.
8. **Camera Angle & Lighting Sensitivity:** Automatic vision profile extraction requires direct square-on camera orientation and adequate lighting; off-axis perspective skew or severe shadows trigger honest low-confidence rejection (< 0.60).
9. **Live Zoo Engine Execution Active:** Stage S6 implements live Zoo Engine execution (`ZooEngineProvider`) via `wss://api.zoo.dev/ws/modeling/commands` with `MockEngineProvider` available as configurable fallback.
10. **Supported Profile Scope:** Geometry scope remains strictly constrained to `circle`, `rectangle`, `rounded_rectangle`, and `traced_closed` per ADR-012.


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
