# InterfaceForge — Bugs and Limitations Log

**Document Status:** Active Log  
**Project:** InterfaceForge (Zoo API Makeathon 2026)  

---

## 1. Active Stage Limitations (Stage S5A)

1. **Deterministic KCL Code Generation (No Zoo Execution Yet):** Stage S5A generates valid deterministic KCL code artifacts (`artifacts/kcl_*.kcl`) and metadata, but does NOT invoke remote Zoo Engine execution API calls yet. 3D Engine execution and GLB/STL preview rendering are deferred to Stage S5B.
2. **Model Status Remains Draft:** Compiled KCL artifacts create model revisions with status `draft`. Per ADR-005 and ADR-001, models are NOT marked `current` until Zoo Engine API execution completes successfully.
3. **Unverified KCL Surface Interpolation Assumptions:** Lofting across dissimilar profiles (e.g. circle to rounded rectangle) or angled planes (up to 45°) is generated using standard KCL `loft()` and `plane()` syntax. Verification of exact surface curvature and solid manifold validity requires Stage S5B Zoo Engine execution testing.
4. **Supported Profile Geometries:** Geometry scope is strictly constrained to `circle`, `rectangle`, and `rounded_rectangle`. Traced closed profiles (`traced_closed`) are rejected by the KCL compiler (`IF-KCL-001`).
5. **Mock Analysis Provider Scope:** Image profile analysis continues to be served by `MockAnalysisProvider`. Real multimodal AI vision integration (Gemini Vision API) remains deferred per specification.
6. **Heuristic Conservative Defaults:** Parameter default values and manufacturing rules are conservative heuristic defaults and are not certified engineering structural calculations. Physical validation is required prior to load-bearing hardware production.

