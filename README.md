<div align="center">
  <img src="InterfaceForge_logo.svg" alt="InterfaceForge logo" width="220" />

  <h3>From two interface profiles to a reviewable parametric adapter.</h3>

  <p>
    InterfaceForge helps makers, technicians, hobbyists, and small workshops create adapter candidates between incompatible physical products without starting from a blank CAD workspace.
  </p>

  <p>
    <a href="https://github.com/joravarsinghing/InterfaceForge"><img alt="Repository" src="https://img.shields.io/badge/GitHub-InterfaceForge-181717?logo=github" /></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-29AA3B" /></a>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10.x-3776AB?logo=python&logoColor=white" />
    <img alt="React" src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111827" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white" />
    <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white" />
    <img alt="Zoo API Makeathon 2026" src="https://img.shields.io/badge/Zoo_API_Makeathon-2026-29AA3B" />
  </p>
</div>

---

## Overview

InterfaceForge converts two reviewed 2D interface profiles and a small set of user-confirmed measurements into a deterministic parametric adapter workflow powered by [Zoo](https://zoo.dev/).

It is designed for situations such as:

- adapting a vacuum hose to a CNC router dust port;
- joining two incompatible round, rectangular, or traced interfaces;
- creating a custom camera, workshop, or equipment adapter;
- producing editable KCL together with STL and STEP artifacts for inspection.

> InterfaceForge creates **editable adapter candidates that must be inspected and approved before manufacturing**. It does not claim unrestricted photo-to-CAD reconstruction or automatic manufacturing readiness.

---

## Product preview

<!-- Replace the placeholder below with a wide application screenshot or animated GIF. -->

<div align="center">

**[PLACEHOLDER — Add a wide screenshot or GIF showing upload → profile review → generated adapter]**

</div>

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>Input</h3>
      <p>Two clean, front-facing interface cross-sections and one known measurement for each profile.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Output</h3>
      <p>A reviewed parametric adapter with KCL source plus Zoo-generated STL and STEP artifacts.</p>
    </td>
  </tr>
</table>

---

## How it works

<table>
  <tr>
    <th align="left">Stage</th>
    <th align="left">What happens</th>
    <th align="left">Primary safeguard</th>
  </tr>
  <tr>
    <td><strong>1. Capture</strong></td>
    <td>Upload a clean cross-section for Interface A and Interface B.</td>
    <td>File, image, and workflow validation.</td>
  </tr>
  <tr>
    <td><strong>2. Trace</strong></td>
    <td>OpenCV extracts a deterministic closed profile and internal holes.</td>
    <td>Trace warnings, rejection reasons, and review overlays.</td>
  </tr>
  <tr>
    <td><strong>3. Scale</strong></td>
    <td>The user confirms one known real-world measurement.</td>
    <td>Scale is never applied silently.</td>
  </tr>
  <tr>
    <td><strong>4. Approve</strong></td>
    <td>Each interface is inspected and explicitly approved.</td>
    <td>Invalid or incomplete profiles cannot proceed.</td>
  </tr>
  <tr>
    <td><strong>5. Configure</strong></td>
    <td>Select connection mode, length, wall thickness, clearances, and offsets.</td>
    <td>Canonical schema and manufacturing-rule validation.</td>
  </tr>
  <tr>
    <td><strong>6. Generate</strong></td>
    <td>InterfaceForge compiles deterministic KCL and executes it through Zoo Engine.</td>
    <td>Revision tracking and last-known-good preservation.</td>
  </tr>
  <tr>
    <td><strong>7. Revise</strong></td>
    <td>Request safe parameter changes in natural language through Zoo Agent.</td>
    <td>Seven-field allowlist plus explicit confirmation.</td>
  </tr>
  <tr>
    <td><strong>8. Export</strong></td>
    <td>Download KCL, STL, and STEP artifacts.</td>
    <td>Export provenance and artifact validation.</td>
  </tr>
</table>

```text
clean cross-section A + one known measurement
                ↓
      trace → review → approve
                ↓
clean cross-section B + one known measurement
                ↓
      trace → review → approve
                ↓
   configure -> Zoo Engine generation
                ↓
 bounded revision → STL / STEP / KCL
```

---

## Preferred input

The reliable supported path uses a **clean, filled cross-section image**.

<table>
  <tr>
    <th align="left">Requirement</th>
    <th align="left">Guidance</th>
  </tr>
  <tr>
    <td><strong>One profile only</strong></td>
    <td>Use a front-facing or orthographic cross-section.</td>
  </tr>
  <tr>
    <td><strong>Plain background</strong></td>
    <td>Maintain strong contrast between profile and background.</td>
  </tr>
  <tr>
    <td><strong>Solid shaded region</strong></td>
    <td>Use a filled profile instead of a thin outline where possible.</td>
  </tr>
  <tr>
    <td><strong>No annotations</strong></td>
    <td>Remove dimension lines, arrows, leaders, text, and center marks.</td>
  </tr>
  <tr>
    <td><strong>Complete boundary</strong></td>
    <td>Keep the entire uncropped profile visible.</td>
  </tr>
  <tr>
    <td><strong>One known dimension</strong></td>
    <td>Provide overall width, overall height, hole diameter, or a reference distance separately.</td>
  </tr>
</table>

<!-- Replace these placeholders with side-by-side input examples. -->

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <strong>Recommended</strong><br><br>
      [PLACEHOLDER — Clean shaded profile example]
    </td>
    <td width="50%" align="center" valign="top">
      <strong>Experimental / manual cleanup likely</strong><br><br>
      [PLACEHOLDER — Dimensioned technical drawing example]
    </td>
  </tr>
</table>

### Why dimensioned drawings are experimental

Dimension lines, leaders, extension lines, text, and center marks can be indistinguishable from true profile edges during classical image processing. They may create false cuts, false extensions, or closed regions that do not belong to the physical interface.

Dimensioned drawings may still be tested through the experimental cleanup path, but they must be manually inspected and corrected before approval.

---

## Zoo integration

InterfaceForge was built as a **Zoo API Makeathon 2026** entry and uses Zoo as the authoritative CAD platform.

<div align="center">
  <a href="https://zoo.dev/">
    <img
      src="zoo.dev.logo.svg"
      alt="Zoo — Parametric CAD infrastructure powering InterfaceForge"
      width="180"
    />
  </a>
</div>

<br>

<table>

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>Zoo Engine API</h3>
      <ul>
        <li>Executes deterministic KCL generated from the canonical project schema.</li>
        <li>Produces the authoritative model used for final exports.</li>
        <li>Returns STL and STEP artifact bytes tied to the exact stored KCL revision.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>Zoo Agent API</h3>
      <ul>
        <li>Interprets natural-language parameter revision requests.</li>
        <li>Operates behind a strict seven-field allowlist.</li>
        <li>Never applies a proposal until the user explicitly confirms it.</li>
      </ul>
    </td>
  </tr>
</table>

Learn more at [zoo.dev](https://zoo.dev/) and in the project’s [API usage guide](docs/API_USAGE.md).

---

## Core capabilities

- Guided two-interface workflow with route guards and state restoration.
- Clean-profile OpenCV tracing with outer contours and internal holes.
- Explicit one-measurement scale calibration.
- Editable SVG profile review.
- Coaxial, offset, and limited-angle connection modes.
- Manufacturing checks for dimensions, wall thickness, and clearances.
- Deterministic KCL compilation.
- Live Zoo Engine generation.
- Bounded natural-language revisions through Zoo Agent.
- Last-known-good model preservation after failed regeneration.
- STL, STEP, and KCL exports for inspection.
- Mock providers for deterministic offline development and automated testing.

---

## Architecture

<!-- Replace this placeholder with a rendered architecture diagram. -->

<div align="center">

**[PLACEHOLDER — Architecture diagram: React → FastAPI → canonical schema → KCL compiler → Zoo Engine / Zoo Agent]**

</div>

<table>
  <tr>
    <th align="left">Layer</th>
    <th align="left">Technology</th>
    <th align="left">Responsibility</th>
  </tr>
  <tr>
    <td><strong>Frontend</strong></td>
    <td>React 18, TypeScript 5, Vite 5, React Router 6</td>
    <td>Guided workflow, profile review, generation status, revisions, and exports.</td>
  </tr>
  <tr>
    <td><strong>Backend</strong></td>
    <td>Python 3.14, FastAPI, Pydantic 2, Pydantic Settings, Uvicorn</td>
    <td>Workflow invariants, validation, analysis orchestration, generation, and exports.</td>
  </tr>
  <tr>
    <td><strong>Persistence</strong></td>
    <td>SQLite</td>
    <td>Canonical project state, schema revisions, and model revision history.</td>
  </tr>
  <tr>
    <td><strong>Vision</strong></td>
    <td>OpenCV, NumPy, Pillow, optional Gemini guidance</td>
    <td>OpenCV contour extraction and trace metrics, with optional Gemini input guidance.</td>
  </tr>
  <tr>
    <td><strong>CAD</strong></td>
    <td>KCL, Zoo Engine API, Zoo Agent API</td>
    <td>Parametric model execution, bounded revisions, and tracked exports.</td>
  </tr>
  <tr>
    <td><strong>Quality</strong></td>
    <td>Pytest, Ruff, Mypy, Vitest, ESLint, TypeScript</td>
    <td>Backend, frontend, contract, lint, type, and build verification.</td>
  </tr>
</table>

For the detailed system design, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [technical_design.md](technical_design.md).

---

## Local setup

### Prerequisites

- Python 3.14.x. The supported backend runtime is the repository root `venv314` environment.
- Node.js 18 or newer.
- npm 9 or newer.
- Zoo API credentials for live generation and Agent workflows.

Backend runtime dependencies are declared in [backend/pyproject.toml](backend/pyproject.toml): FastAPI, Uvicorn, Pydantic, Pydantic Settings, WebSockets, Pillow, NumPy, OpenCV headless, and Python Multipart. `httpx`, `msgpack`, and `google-genai` are declared in the backend `dev` extra because they are used by the test harness, WebSocket payload tests, or provider-mocked tests rather than local backend startup.

### Install

```powershell
# From the repository root
py -3.14 -m venv venv314
.\venv314\Scripts\python.exe -m pip install --upgrade pip
.\venv314\Scripts\python.exe -m pip install -e backend[dev]

cd frontend
npm install
cd ..
```

Create the local backend environment file from the included example and add the credentials required for the providers you plan to use.

### Run frontend and backend together

```powershell
python scripts/start_local.py
```

Open:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- FastAPI docs: `http://localhost:8000/docs`

### Run services individually

```powershell
python scripts/run_backend.py
python scripts/run_frontend.py
```

---

## Testing and verification

Run the complete local verification suite:

```powershell
python scripts/run_all_checks.py
```

Run component suites separately:

```powershell
# Backend
.\venv314\Scripts\python.exe -m pytest backend\tests

# Frontend
cd frontend
npm test
cd ..
```

Live provider verification may require valid Zoo or analysis-provider credentials and should remain separate from deterministic offline checks.

---

## Current limitations

- Clean, orthographic cross-sections are the reliable supported input.
- Dimensioned engineering drawings remain experimental and may require manual SVG cleanup.
- Annotation masking may leave residual false edges or remove valid detail.
- Scale calibration always requires explicit user confirmation.
- Geometry support is intentionally constrained to circles, rectangles, rounded rectangles, and reviewed closed traces.
- Generated adapters remain user-reviewed engineering candidates rather than automatically certified manufacturing designs.

See [docs/BUGS_AND_LIMITATIONS.md](docs/BUGS_AND_LIMITATIONS.md) for the maintained limitation log.

---

## Documentation

<table>
  <tr>
    <th align="left">Document</th>
    <th align="left">Purpose</th>
  </tr>
  <tr>
    <td><a href="InterfaceForge_PRD_v0.1.md">Product requirements</a></td>
    <td>Product scope, users, requirements, and success criteria.</td>
  </tr>
  <tr>
    <td><a href="technical_design.md">Technical design</a></td>
    <td>System architecture, data model, contracts, and accepted design decisions.</td>
  </tr>
  <tr>
    <td><a href="user_flow.md">User flow</a></td>
    <td>Guided workflow, route progression, and state-machine behavior.</td>
  </tr>
  <tr>
    <td><a href="ascii_wireframes.md">Wireframes</a></td>
    <td>Implementation-oriented layouts and interaction notes.</td>
  </tr>
  <tr>
    <td><a href="docs/ARCHITECTURE.md">Architecture</a></td>
    <td>Current system structure and provider boundaries.</td>
  </tr>
  <tr>
    <td><a href="docs/API_USAGE.md">API usage</a></td>
    <td>Backend contracts and external-provider integration.</td>
  </tr>
  <tr>
    <td><a href="docs/GEOMETRY_RULES.md">Geometry rules</a></td>
    <td>Profile, connection, and manufacturing validation rules.</td>
  </tr>
  <tr>
    <td><a href="docs/TEST_PLAN.md">Test plan</a></td>
    <td>Verification strategy and scenario coverage.</td>
  </tr>
  <tr>
    <td><a href="docs/TEST_RESULTS.md">Test results</a></td>
    <td>Recorded verification outcomes.</td>
  </tr>
  <tr>
    <td><a href="docs/BUGS_AND_LIMITATIONS.md">Bugs and limitations</a></td>
    <td>Known issues, experimental paths, and product boundaries.</td>
  </tr>
  <tr>
    <td><a href="AGENTS.md">Agent governance</a></td>
    <td>Repository rules and implementation-agent guidance.</td>
  </tr>
</table>

---

## Credits

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>Built by</h3>
      <p><strong><a href="https://joravarsinghing.github.io/portfolio/">Joravar Singh</a></strong></p>
      <p>Product concept, engineering direction, implementation coordination, testing, and submission development.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Powered by Zoo</h3>
      <p><strong><a href="https://zoo.dev/">Zoo</a></strong></p>
      <p>Parametric CAD execution, KCL tooling, native model exports, and bounded natural-language CAD revision capabilities.</p>
    </td>
  </tr>
</table>

InterfaceForge is an independent Zoo API Makeathon project and is not an official Zoo product.

---

## License

InterfaceForge is available under the [MIT License](LICENSE).

---

<div align="center">

  <h3>Powered by</h3>

  <a href="https://zoo.dev/">
    <img src="zoo.dev.logo.svg" alt="Zoo logo" width="150" />
  </a>

  <p>
    Parametric CAD execution, KCL tooling, native model exports, and bounded natural-language CAD revision capabilities.
  </p>

  <p>
    <strong>Vision-assisted by Google Gemini</strong><br>
    Gemini provides optional multimodal guidance for interpreting uploaded interface images. Final geometry is produced deterministically through OpenCV, user review, KCL, and Zoo Engine.
  </p>

  <br>

  <h3>Built by</h3>

  <a href="https://joravarsinghing.github.io/portfolio/">
    <img src="J_initial.svg" alt="Joravar Singh" width="90" />
  </a>

  <p>
    <strong>
      <a href="https://joravarsinghing.github.io/portfolio/">Joravar Singh</a>
    </strong><br>
    Product concept, engineering direction, implementation coordination, testing, and submission development.
  </p>

  <br>

  <img src="InterfaceForge_logo_in.svg" alt="InterfaceForge icon" width="110" />

  <p>
    <sub>Designed for reviewed geometry, deterministic CAD, and honest engineering boundaries.</sub>
  </p>

</div>
