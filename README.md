# InterfaceForge

InterfaceForge turns two reviewed, clean, front-facing 2D profiles into a hollow parametric transition adapter for dust extraction. The submission workflow uses two-point calibration, explicit profile approval, an authoritative `LoftPlan`, deterministic KCL 2.0, Zoo Engine generation, bounded Zoo Agent revisions, and STL/KCL exports.

> Outputs are user-reviewed engineering candidates. This submission does not claim unrestricted photo-to-CAD reconstruction, angle-based connections, internal cavities, STEP export, certified dimensional accuracy, or manufacturing readiness.

[Open the live app](https://interfaceforge.pages.dev/) | [GitHub repository](https://github.com/joravarsinghing/InterfaceForge) | [Zoo](https://zoo.dev/)

## Documentation map

- [README](README.md) - Judge quick start, scope, deployment, and links.
- [PRD](InterfaceForge_PRD_v0.1.md) - Implemented product scope and success criteria.
- [User flow](user_flow.md) - Locked workflow, recovery, and approval behavior.
- [Technical design](technical_design.md) - Detailed components, state, security, and data flow.
- [Architecture](docs/ARCHITECTURE.md) - Deployment topology and provider boundaries.
- [API usage](docs/API_USAGE.md) - Exact active routes and payload contracts.
- [Design schema](docs/DESIGN_SCHEMA.md) - Canonical JSON and revision fields.
- [Geometry rules](docs/GEOMETRY_RULES.md) - Calibration, contour, fit, and validation rules.
- [Design decisions](docs/DESIGN_DECISIONS.md) - ADR rationale and superseded decisions.
- [Bugs and limitations](docs/BUGS_AND_LIMITATIONS.md) - Sanitized defect and evidence record.
- [Zoo API notes](docs/ZOO_API_NOTES.md) - Classified live-provider observations.
- [Test plan](docs/TEST_PLAN.md) - Retained test coverage and smoke checks.
- [Test results](docs/TEST_RESULTS.md) - Evidence-backed results and blockers.
- [Live integration checklist](docs/ZOO_LIVE_INTEGRATION_CHECKLIST.md) - Live verification status.
- [Demo script](docs/DEMO_SCRIPT.md) - Time-boxed final video sequence.
- [Submission checklist](docs/SUBMISSION_CHECKLIST.md) - Final manual and external-deliverable checks.

`production_docs/` and `ascii_wireframes.md` are historical records. They may contain superseded stages, fields, or scope and do not define current behavior.

Recommended audit path: `README -> technical design -> API usage -> bugs/limitations -> test results`.

## Judge Quick Start

1. Open the [live app](https://interfaceforge.pages.dev/) or run the local frontend/backend.
2. Create a project in Mock mode for deterministic offline review, or select Live only when backend Zoo credentials are configured.
3. Upload `samples/valid_circle.png` as Interface A and `samples/valid_rounded_rectangle.png` as Interface B.
4. For each profile select two points representing `50 mm` of known distance, confirm calibration, review the trace, and approve it.
5. Use `fit-over` for both profiles, `coaxial` mode, `40 mm` length, `2.4 mm` wall thickness, and `0.3 mm` / `0.1 mm` clearances.
6. Validate and explicitly generate. Inspect the result, then download current STL and KCL.
7. Try the Agent prompt: `Make the adapter 10 mm longer.` Review the structured proposal, confirm it, then explicitly regenerate. Confirmation alone marks the model stale; it does not launch generation.

Expected result: two approved profiles, a persisted LoftPlan, deterministic KCL 2.0, a generated model when the selected Engine is available, and revision-current STL/KCL exports.

## What Zoo does

Zoo Engine is the authoritative CAD executor for generated KCL. Zoo Agent interprets natural-language parameter changes but may propose only length, X/Y offsets, wall thickness, and clearances. The server validates and recalculates proposals; contours, providers, and KCL are not Agent-editable.

A prior credentialed Zoo Agent flow succeeded. During the focused 2026-08-04 adversarial audit, 17 of 18 Agent calls timed out or closed. Prior project evidence verified STL export, while the direct live Engine audit timed out before a fresh STL conversion result. Offline tests are not live Zoo proof, and no confirmed Zoo bug was established.

## Demonstration evidence

![Homepage workflow showing the two-profile adapter use case](assets/homepage.png)

*Figure 1. InterfaceForge entry point and dust-extraction adapter workflow.*

![Interface A upload and profile guidance](assets/step11.png)

*Figure 2. Clean circular Interface A input.*

![Interface B review and approval](assets/step2.png)

*Figure 3. Rounded-rectangle Interface B review state.*

![Generated adapter result](assets/step5.png)

*Figure 4. Zoo-generated model inspection state.*

![STL and KCL export controls](assets/export1.png)

*Figure 5. Current export controls for STL and KCL.*

![Printed adapter example](assets/export5.jpg)

*Figure 6. Physical print example for demonstration only; it is not dimensional certification.*

Demo video: [https://youtu.be/z8Ge7i2QtFM](https://youtu.be/z8Ge7i2QtFM) - unlisted, accessible to anyone with the link; not public.

## Deployment summary

- Frontend: Cloudflare Pages.
- Backend: FastAPI on Render.
- Persistence: SQLite through `DB_PATH`.
- Frontend/backend connection: `VITE_BACKEND_URL`.
- Zoo, Gemini, and OpenRouter credentials: backend environment only.
- Runtime uploads, traces, KCL, previews, and exports: ignored artifact storage; Render filesystem durability is deployment-dependent.

## Local setup

```powershell
py -3.14 -m venv venv314
.\venv314\Scripts\python.exe -m pip install -e backend[dev]
cd frontend
npm install
cd ..
$env:PYTHONPATH = (Resolve-Path .\backend).Path
.\venv314\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontend development uses `VITE_BACKEND_URL=http://127.0.0.1:8000`. See [backend setup](backend/README.md) for exact environment variables and test commands.

## Scope

Supported profiles: circle, rectangle, rounded rectangle, and approved `traced_closed`. Supported fits: fit-over and fit-inside. Supported connections: coaxial and parallel X/Y offset. Active exports: STL and KCL. Angle-based connections, internal cavities, threads, mounting holes, countersinks, dovetails, undercuts, branches, assemblies, curved centerlines, STEP, and certified manufacturing-ready output are excluded.
