# InterfaceForge

> Help non-CAD users create manufacturable parametric adapters between incompatible physical products using two 2D interface images or sketches, a few measurements, and a guided visual workflow.

---

## Competition Status

**Zoo API Makeathon 2026 Submission Entry**  
Current stage: **S2 — Architecture Skeleton and Local Development Environment** (Complete)

---

## Problem Summary

Makers, hobbyists, small workshops, and technicians often need to connect two physical products that were never designed to fit together (e.g., a Dyson vacuum hose to a CNC router dust port, or a custom camera plate to an incompatible tripod mount).

Creating a custom 3D-printable adapter usually requires learning complex CAD software, hiring a designer, or trial-and-error physical prototyping. InterfaceForge solves this by converting real-world 2D interface profiles and basic dimensions into verified, parametric, manufacturing-ready 3D CAD models powered by Zoo’s CAD Engine.

---

## Proposed Workflow

1. **Capture Interface A:** Upload an image or sketch of the first physical interface.
2. **Review & Approve A:** Review extracted SVG profile, correct dimensions/provenance, and approve profile A.
3. **Capture Interface B:** Upload image or sketch of the second interface.
4. **Review & Approve B:** Review and approve profile B.
5. **Configure Connection:** Choose connection mode (Coaxial, Offset, or Limited-Angle) and set parameters (length, wall thickness, clearances).
6. **Generate Adapter:** Validate canonical schema and generate deterministic KCL for execution via Zoo Engine API.
7. **Review & Revise:** Inspect 3D preview, refine parameters via structured UI or natural-language prompts via Zoo Agent API.
8. **Export:** Download manufacturing-ready STL, STEP, and KCL source files via Zoo File Format API.

---

## Architecture & Technical Stack

* **Frontend:** React 18, TypeScript 5, Vite 5, Vanilla CSS, React Router 6.
* **Backend:** Python 3.12 (compatible 3.10+), FastAPI 0.110+, Pydantic 2, Uvicorn.
* **CAD & AI Engine:** Zoo Engine API, Zoo Agent API, Zoo File Format API *(Integrations scheduled for Stage S5+)*.
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

### 2. Running Services

#### Run Backend Server (FastAPI on port 8000)
```powershell
python scripts/run_backend.py
# Server will start at http://localhost:8000
# OpenAPI Docs available at http://localhost:8000/docs
```

#### Run Frontend Server (Vite on port 5173)
```powershell
python scripts/run_frontend.py
# Application will start at http://localhost:5173
```

---

## Testing & Quality Checks

Run all verification checks (Backend pytest/ruff/mypy + Frontend vitest/eslint/tsc/build + Repo audit):
```powershell
python scripts/run_all_checks.py
```

Run test suites only:
```powershell
python scripts/run_tests.py
```

Individual component commands:
```powershell
# Backend tests & checks
$env:PYTHONPATH="backend"
.\venv\Scripts\pytest backend/tests
.\venv\Scripts\ruff check backend
.\venv\Scripts\ruff format --check backend
.\venv\Scripts\mypy --explicit-package-bases backend/app

# Frontend tests & checks
cd frontend
npm test
npm run lint
npx tsc --noEmit
npm run build
cd ..

# Repository governance audit
python scripts/audit_repository.py
```

---

## Repository Documentation Map

* [`InterfaceForge_PRD_v0.1.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/InterfaceForge_PRD_v0.1.md) — Product Requirements Document (PRD)
* [`technical_design.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/technical_design.md) — System Architecture, Data Model, API Contracts & Accepted ADRs
* [`user_flow.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/user_flow.md) — Implementation-ready User Flows and State Machine
* [`ascii_wireframes.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/ascii_wireframes.md) — Complete UI Layout Wireframes and Accessibility Specs
* [`AGENTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/AGENTS.md) — Agent Governance, Rules, and Execution Guidelines
* [`production_docs/S1_PROJECT_FOUNDATION.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/production_docs/S1_PROJECT_FOUNDATION.md) — Stage S1 Production Control Document
* [`production_docs/S2_ARCHITECTURE_SKELETON.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/production_docs/S2_ARCHITECTURE_SKELETON.md) — Stage S2 Production Control Document
* [`docs/ARCHITECTURE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/ARCHITECTURE.md) — Architecture Specification
* [`docs/API_USAGE.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/API_USAGE.md) — API Contracts & Integration Guide
* [`docs/TEST_PLAN.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_PLAN.md) — Master Test Plan
* [`docs/DESIGN_SCHEMA.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/DESIGN_SCHEMA.md) — *(Not started)* Canonical Design Schema Specification
* [`docs/GEOMETRY_RULES.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/GEOMETRY_RULES.md) — *(Not started)* Geometry & Lofting Rules
* [`docs/TEST_RESULTS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/TEST_RESULTS.md) — *(Not started)* Test Execution Results
* [`docs/ZOO_API_NOTES.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/ZOO_API_NOTES.md) — *(Not started)* Zoo API Technical Notes
* [`docs/BUGS_AND_LIMITATIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/BUGS_AND_LIMITATIONS.md) — *(Not started)* Bug and Limitation Log
* [`docs/DESIGN_DECISIONS.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/DESIGN_DECISIONS.md) — *(Not started)* Design Decisions Log
* [`docs/DEMO_SCRIPT.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/DEMO_SCRIPT.md) — *(Not started)* Demo Video Script
* [`docs/SUBMISSION_CHECKLIST.md`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/docs/SUBMISSION_CHECKLIST.md) — *(Not started)* Competition Submission Checklist

---

## License

This project is licensed under the terms of the MIT License. See [`LICENSE`](file:///C:/Users/jvsin/Documents/GitHub/InterfaceForge/LICENSE) for details.
