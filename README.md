# InterfaceForge

> Help non-CAD users create manufacturable parametric adapters between incompatible physical products using two 2D interface images or sketches, a few measurements, and a guided visual workflow.

---

## Competition Status

**Zoo API Makeathon 2026 Submission Entry**  
Current stage: **S9 — Bounded Zoo Agent Revisions** (Complete & Proven PASS)

---

## Problem Summary

Makers, hobbyists, small workshops, and technicians often need to connect two physical products that were never designed to fit together (e.g., a Dyson vacuum hose to a CNC router dust port, or a custom camera plate to an incompatible tripod mount).

Creating a custom 3D-printable adapter usually requires learning complex CAD software, hiring a designer, or trial-and-error physical prototyping. InterfaceForge solves this by converting real-world 2D interface profiles and basic dimensions into verified, parametric, manufacturing-ready 3D CAD models powered by Zoo’s CAD Engine.

---

## Complete Guided Workflow

1. **Capture Interface A:** Upload an image or sketch of the first physical interface.
2. **Review & Approve A:** Review extracted SVG profile, correct dimensions/provenance, and approve profile A.
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

## Repository Documentation Map

* [`InterfaceForge_PRD_v0.1.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/InterfaceForge_PRD_v0.1.md) — Product Requirements Document (PRD)
* [`technical_design.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/technical_design.md) — System Architecture, Data Model, API Contracts & Accepted ADRs
* [`user_flow.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/user_flow.md) — Implementation-ready User Flows and State Machine
* [`ascii_wireframes.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/ascii_wireframes.md) — Complete UI Layout Wireframes and Accessibility Specs
* [`AGENTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/AGENTS.md) — Agent Governance, Rules, and Execution Guidelines
* [`production_docs/S6A_FULL_WEB_APP_WORKFLOW.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/production_docs/S6A_FULL_WEB_APP_WORKFLOW.md) — Stage S6A Production Control Document
* [`docs/ARCHITECTURE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/ARCHITECTURE.md) — Architecture Specification
* [`docs/API_USAGE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/API_USAGE.md) — API Contracts & Integration Guide
* [`docs/TEST_PLAN.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_PLAN.md) — Master Test Plan
* [`docs/TEST_RESULTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_RESULTS.md) — Test Execution Results
* [`docs/BUGS_AND_LIMITATIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/BUGS_AND_LIMITATIONS.md) — Bug and Limitation Log

---

## License

This project is licensed under the terms of the MIT License. See [`LICENSE`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/LICENSE) for details.
