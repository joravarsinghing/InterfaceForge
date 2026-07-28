# InterfaceForge

> Help non-CAD users create manufacturable parametric adapters between incompatible physical products using two 2D interface images or sketches, a few measurements, and a guided visual workflow.

---

## Competition Status

**Zoo API Makeathon 2026 Submission Entry**  
Current stage: **S10.5H — Input Requirements and Honest Upload Guidance** (Complete)

---

## Problem Summary

Makers, hobbyists, small workshops, and technicians often need to connect two physical products that were never designed to fit together (e.g., a Dyson vacuum hose to a CNC router dust port, or a custom camera plate to an incompatible tripod mount).

Creating a custom 3D-printable adapter usually requires learning complex CAD software, hiring a designer, or trial-and-error physical prototyping. InterfaceForge solves this by converting real-world 2D interface profiles and basic dimensions into verified, parametric, manufacturing-ready 3D CAD models powered by Zoo's CAD Engine.

---

## Preferred Input Format

The most reliable input for profile extraction is a **clean cross-section image**:

| Requirement | Detail |
|:---|:---|
| **One cross-section only** | Front-facing / orthographic view |
| **Plain background** | High contrast between profile and background |
| **Solid shaded region** | Filled profile area, not just an outline |
| **No annotations** | No dimension lines, text, arrows, leaders, or center marks |
| **Full profile visible** | Uncropped — complete boundary in frame |
| **One known dimension** | Supplied separately by the user for scale calibration |

> For best results, upload a clean cross-section image without dimensions or annotations. One confirmed measurement is enough to scale the profile accurately.

### Why dimensioned drawings are unreliable

Dimension lines, leaders, extension lines, and center marks are indistinguishable from profile edges by OpenCV. They create **false cuts** and false boundary extensions in the traced profile. Dimensioned drawings are treated as **Experimental / manual review required** — the traced profile must be inspected and corrected before approval.

### One-dimension scaling

You do not need dimensions inside the drawing. Provide one known real-world measurement separately (overall width, overall height, hole diameter, or a reference distance). After the trace is generated, you confirm the measurement — scale is **never applied automatically**.

### Input quality statuses

| Status | Meaning |
|:---|:---|
| **Recommended input** | Clean shaded profile, no annotations |
| **Usable with review** | Limited text outside profile; review trace carefully |
| **Manual cleanup likely** | Leaders or center marks touch geometry; expect false edges |
| **Unsupported** | Cropped, angled, blurry, or multiple profiles |

---

## Supported Workflow

```
clean profile
→ OpenCV trace
→ user confirms one scale dimension
→ editable SVG
→ Zoo CAD generation
```

Dimensioned drawing support exists as an **experimental path** requiring manual SVG cleanup — it is not the primary workflow.

---

## Complete Guided Workflow

1. **Capture Interface A:** Upload a clean cross-section image of the first physical interface. Review input quality guidance before uploading.
2. **Review & Approve A:** Review extracted SVG profile, confirm one scale dimension, correct dimensions/provenance, and approve profile A.
3. **Capture Interface B:** Upload image or sketch of the second interface.
4. **Review & Approve B:** Review and approve profile B.
5. **Configure Connection:** Choose connection mode (Coaxial, Offset, or Limited-Angle) and set parameters (length, wall thickness, clearances).
6. **Generate Adapter:** Validate canonical schema, compile deterministic KCL, and execute 3D generation via live Zoo Engine API.
7. **Safe Natural-Language Revisions:** Request parameter revisions in plain English using live Zoo Agent API (`wss://api.zoo.dev/ws/ml/copilot`). AI proposals are strictly bounded by a 7-field allowlist and require explicit user confirmation before 3D model regeneration.
8. **Export:** Download verified STL, STEP, and KCL CAD files produced directly by Zoo Engine.

---

## Architecture & Technical Stack

* **Frontend:** React 18, TypeScript 5, Vite 5, Vanilla CSS, React Router 6.
* **Backend:** Python 3.12 (compatible 3.10+), FastAPI 0.110+, Pydantic 2, SQLite, Uvicorn.
* **CAD & Mock Engine:** Zoo Engine API abstraction layer, deterministic `MockEngineProvider`, KCL Compiler.
* **Development Tooling:** Pytest, Ruff, Mypy, Vitest, ESLint, TypeScript.

---

## Setup & Local Execution (Windows & Cross-Platform)

### Prerequisites
- Python 3.10+ (Target Python 3.12)
- Node.js 18+ and npm 9+

### 1. Initial Setup
Set up virtual environment and install dependencies:
```powershell
# Create Python virtual environment and install backend packages
python -m venv venv
.\venv\Scripts\python -m pip install -e backend[dev]

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Manual QA Local Development Runner
Run frontend and backend together using a single script:
```powershell
python scripts/start_local.py
```
Open your browser to `http://localhost:5173`. Backend runs on `http://localhost:8000`. Press `Ctrl+C` to terminate both services.

#### Individual Service Runners
```powershell
# Run Backend Server (FastAPI on port 8000)
python scripts/run_backend.py

# Run Frontend Server (Vite on port 5173)
python scripts/run_frontend.py
```

---

## Testing & Quality Checks

Run all verification checks (Backend pytest/ruff/mypy + Frontend vitest/eslint/tsc/build + Repo audit):
```powershell
python scripts/run_all_checks.py
```

Individual component test suites:
```powershell
# Backend Pytest Suite
.\venv\Scripts\python -m pytest backend/tests

# Frontend Vitest Suite
cd frontend
npm test
cd ..
```

---

## Current Limitations

- Dimensioned engineering drawings require manual profile cleanup — they are **not automatically supported**.
- Annotation masking (S10.5G) is **experimental** and may leave residual false edges.
- Gemini vision extraction is reliable for clean, orthographic cross-sections only.
- Scale calibration requires explicit user confirmation — no automatic scaling.
- Geometry scope is constrained: circle, rectangle, rounded rectangle, and traced closed profiles only.

See [`docs/BUGS_AND_LIMITATIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/BUGS_AND_LIMITATIONS.md) for the full limitation log.

---

## Repository Documentation Map

* [`InterfaceForge_PRD_v0.1.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/InterfaceForge_PRD_v0.1.md) — Product Requirements Document (PRD)
* [`technical_design.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/technical_design.md) — System Architecture, Data Model, API Contracts & Accepted ADRs
* [`user_flow.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/user_flow.md) — Implementation-ready User Flows and State Machine
* [`ascii_wireframes.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/ascii_wireframes.md) — Complete UI Layout Wireframes and Accessibility Specs
* [`AGENTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/AGENTS.md) — Agent Governance, Rules, and Execution Guidelines
* [`production_docs/S10.5H_INPUT_REQUIREMENTS_AND_GUIDANCE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/production_docs/S10.5H_INPUT_REQUIREMENTS_AND_GUIDANCE.md) — Stage S10.5H Production Control Document
* [`docs/ARCHITECTURE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/ARCHITECTURE.md) — Architecture Specification
* [`docs/API_USAGE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/API_USAGE.md) — API Contracts & Integration Guide
* [`docs/GEOMETRY_RULES.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/GEOMETRY_RULES.md) — Geometry Rules & Manufacturing Validation
* [`docs/TEST_PLAN.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_PLAN.md) — Master Test Plan
* [`docs/TEST_RESULTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_RESULTS.md) — Test Execution Results
* [`docs/BUGS_AND_LIMITATIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/BUGS_AND_LIMITATIONS.md) — Bug and Limitation Log

---

## License

This project is licensed under the terms of the MIT License. See [`LICENSE`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/LICENSE) for details.
