# InterfaceForge — Product Requirements Document (PRD)

**Document status:** Draft v0.1  
**Project:** Zoo API Makeathon 2026  
**Product owner:** Joravar Singh  
**Primary implementation window:** July 22–August 5, 2026  
**Audience:** Product owner, project manager, Codex, Antigravity/Gemini, Claude, and any coding or review agent working on the project

---

## 1. Purpose

This PRD is the source of truth for InterfaceForge during the Zoo API Makeathon.

All implementation agents must follow the scope, priorities, product principles, and data flow defined here. They must document assumptions, deviations, bugs, and API limitations; prefer reliable and testable geometry over impressive but unstable generation; and never silently expand or alter scope.

Where an ad hoc coding suggestion conflicts with this PRD, this PRD takes priority unless the product owner explicitly approves the change.

---

## 2. Product Summary

**InterfaceForge helps people without CAD experience create a manufacturable adapter between two incompatible physical products using two interface images or sketches, a few measurements, and a guided visual workflow.**

The user defines and approves two 2D interface profiles, chooses how they should connect, and receives a parametric 3D adapter generated through Zoo’s CAD technology.

InterfaceForge is not a general text-to-CAD system. It is a constrained interface-to-interface geometry generator.

---

## 3. Problem Statement

Hobbyists, makers, small workshops, technicians, and 3D-printing users often need to connect two products that were not designed to fit together.

Examples:

- a vacuum hose and a CNC-router dust port;
- a camera plate and an incompatible mounting pattern;
- a tool outlet and a custom nozzle;
- two products with different hole patterns;
- two openings with different shapes or sizes.

Today, the user must usually search online for an existing model, install and learn CAD software, ask a CAD-capable friend, pay a designer, create several inaccurate prototypes, or abandon the project.

The core barrier is converting real-world interface geometry into accurate, adjustable, manufacturable CAD.

---

## 4. Product Vision

InterfaceForge should make custom adapter creation feel closer to configuring a product than operating CAD software.

> Upload or sketch two physical interfaces, verify what the system understood, choose how they should connect, and receive editable manufacturing-ready geometry.

The Makeathon MVP will prove this workflow for a restricted set of profiles and adapter types.

---

## 5. Goals

### 5.1 Primary goals

1. Allow a non-CAD user to define two physical interfaces visually.
2. Distinguish user-provided data from inferred data.
3. Require user approval before 3D generation.
4. Generate a parametric adapter through Zoo’s Engine API.
5. Allow safe iteration without exposing raw CAD complexity.
6. Export useful manufacturing formats.
7. Produce at least one physically validated 3D-printed adapter.
8. Demonstrate meaningful use of Zoo’s Engine, Agent, and File Format APIs.
9. Produce strong documentation, technical notes, and reproducible bug reports.

### 5.2 Secondary goals

- Show how a purpose-built UI can make Zoo’s programmable CAD engine accessible.
- Demonstrate natural-language revisions without uncontrolled AI geometry generation.
- Establish a reusable canonical design schema.
- Build a foundation for later fixtures, toy-compatible parts, and other adapter families.

---

## 6. Non-Goals

The MVP will not provide:

- general-purpose CAD editing;
- arbitrary photo-to-perfect-3D reconstruction;
- unrestricted freeform surface modelling;
- a complete browser CAD system;
- arbitrary assemblies;
- structural certification or finite-element analysis;
- automatic load validation;
- arbitrary thread generation;
- complex moving mechanisms;
- unrestricted 3D transform gizmos;
- advanced mesh repair;
- accounts, billing, subscriptions, or credit systems;
- mobile-first editing;
- slicing or automatic support generation;
- production engineering guarantees.

Any agent proposing these must classify them as post-MVP ideas.

---

## 7. Target Users

### Primary user

A hobbyist or maker who:

- has two products that need to connect;
- has little or no CAD experience;
- can take basic measurements;
- may own or have access to a 3D printer;
- wants to avoid installing or learning CAD software;
- wants to iterate without starting again;
- values a guided, visual workflow.

### Secondary users

- small workshops;
- technicians;
- 3D-printing services;
- product customizers;
- maintenance workers;
- makerspaces.

### Initial buyer hypothesis

Potential future buyers include individual makers, small workshops, 3D-printing services, and equipment owners who frequently need one-off adapters. Monetization is outside the Makeathon MVP.

---

## 8. Jobs to Be Done

### Core job

> When I have two products that do not connect, help me create the missing adapter without requiring me to learn CAD.

### Supporting jobs

- Help me capture both interfaces correctly.
- Show me what was measured, extracted, and inferred.
- Let me correct dimensions before generation.
- Help me understand coaxial, offset, and angled connections.
- Generate geometry suitable for 3D printing.
- Let me revise through simple controls or plain language.
- Give me files I can print or continue editing elsewhere.
- Warn me when input or geometry is unreliable.

---

## 9. Hero Use Cases

### 9.1 Vacuum adapter — primary

**Scenario:** Connect a Dyson-style vacuum hose to a CNC-router dust port.

This demonstrates image-assisted profile extraction, profile calibration, fit clearance, wall thickness, coaxial/offset/angled relationships, hollow geometry, manufacturability, STL export, and physical validation.

### 9.2 Camera mounting adapter — secondary

**Scenario:** Convert one simple camera or tripod mounting interface to another flat mounting pattern.

This demonstrates flat geometry, hole patterns, plate thickness, offsets, mounting clearances, and parametric editing. STEP export is planned but not implemented for this submission.

The camera example must remain simple and must not expand into a complete camera-rig system.

---

## 10. Product Principles

### Guided, not magical
AI may interpret images and intent, but must not silently create unverified engineering geometry.

### User approval before generation
Both interface profiles must be approved before 3D generation.

### Visible uncertainty
The UI must distinguish user-entered, image-extracted, system-inferred, and unresolved values.

### Deterministic geometry
Final KCL must be generated from a validated canonical schema and tested geometry functions.

### Safe iteration
Users edit exposed parameters or bounded natural-language changes, not raw KCL.

### Manufacturing awareness
The system applies basic FDM rules and warnings without unsupported engineering claims.

### Honest failure
Poor input or unsafe geometry must trigger correction, not confident output.

---

## 11. MVP Scope

### Required capabilities

1. Two interface inputs: A and B.
2. Image or sketch upload for each.
3. Guidance showing good and bad image examples.
4. Profile extraction into editable SVG.
5. At least two known dimensions per interface, with more requested when necessary.
6. Visual distinction between entered, extracted, inferred, and unresolved values.
7. Direct editing of dimension values.
8. Explicit approval of both profiles.
9. Profile types:
   - circle;
   - rectangle;
   - rounded rectangle;
   - validated traced closed profile.
10. Connection modes:
   - coaxial;
   - offset;
   - angle-based connections are not supported.
11. Visual guidance for connection parameters.
12. Controls for transition length, X/Y offset, angle, wall thickness, and clearance.
13. Parametric 3D generation through Zoo.
14. Final 3D preview.
15. Structured warnings and assumptions.
16. Natural-language parameter revision through the Agent API.
17. STL and KCL exports; STEP is planned but not implemented for this submission.
18. Useful File Format API conversion or analysis.
19. Model volume output if reliable.
20. One physically printed and tested hero adapter.
21. Complete README, setup instructions, demo, API notes, and bug log.

### Optional capabilities

Only after all required capabilities are stable:

- draggable major SVG control points;
- profile centre adjustment;
- fit presets;
- material estimate;
- downloadable design JSON;
- GLB preview export;
- camera adapter demo;
- local project persistence;
- before/after revision comparison.

### Explicitly deferred

- user accounts;
- cloud project storage;
- payments;
- credit limits;
- mobile editing;
- arbitrary imported STEP editing;
- arbitrary freeform lofts;
- engineering certification;
- toy-compatible part generation;
- fixture generation.

---

## 12. End-to-End User Flow

1. **Start project:** User sees a concise explanation and begins.
2. **Capture Interface A:** Guidance explains camera angle, contrast, scale, and dimensions.
3. **Interpret A:** The system detects the likely outer profile and dimensions.
4. **Review A:** User sees a clean SVG, dimension provenance, confidence, and editable values.
5. **Approve A.**
6. **Repeat for B.**
7. **Choose connection:** Coaxial, offset, or angled, each with a plain-language explanation and visual diagram.
8. **Configure:** Set length, offsets, angle, wall thickness, and fit.
9. **Generate:** Validate schema, generate deterministic KCL, execute through Zoo Engine API.
10. **Review result:** Show 3D preview, parameters, warnings, assumptions, and volume where available.
11. **Revise:** Change fields or submit a bounded natural-language revision.
12. **Export:** Download STL and KCL; STEP is planned but not implemented.

---

## 13. Functional Requirements

### FR-001 — Image guidance
Show concise instructions for producing a usable source image.

### FR-002 — Two interface records
Each MVP project contains exactly two interface definitions.

### FR-003 — Profile extraction
Derive a clean 2D profile from each input image or sketch.

### FR-004 — Calibration
Require at least two dimensions per profile and request more when geometry remains ambiguous.

### FR-005 — Dimension provenance
Every dimension must carry one state: `user_entered`, `image_extracted`, `system_inferred`, or `unresolved`.

### FR-006 — Editable SVG review
Users can edit displayed dimension values and regenerate the SVG.

### FR-007 — Approval gate
3D generation cannot begin until both profiles are approved.

### FR-008 — Profile validation
Reject or flag open contours, self-intersections, duplicate points, excessive noise, invalid scale, unsupported internal features, and unsafe loft conditions.

### FR-009 — Connection modes
Support coaxial and offset relationships. Angle-based connections are not supported.

### FR-010 — Guided parameters
Each connection mode exposes only valid controls.

### FR-011 — Canonical design schema
Convert approved inputs into a versioned structured design object before KCL generation.

### FR-012 — Deterministic KCL generation
Generate KCL from validated data and tested functions.

### FR-013 — Engine API integration
Use the Engine API centrally for geometry creation and regeneration.

### FR-014 — Agent API integration
Use the Agent API for bounded structured revisions or explanations, never unvalidated final geometry.

### FR-015 — File Format API integration
Use the File Format API for meaningful export, conversion, or analysis.

### FR-016 — Manufacturability rules
Include at least minimum wall thickness, fit/clearance handling, minimum transition length, excessive-angle warning, self-intersection prevention, and export validation.

### FR-017 — Error handling
Every user-facing error must explain the issue and corrective action. Internal error IDs may also be logged.

### FR-018 — Logging
Log schema, generated KCL, API operation, status, error, duration, output references, and timestamp. Do not log secrets or raw uploads unnecessarily.

### FR-019 — Export
Successful projects produce STL and KCL outputs. STEP is planned but not implemented for this submission.

### FR-020 — Reproducibility
At least one known-good fixture must regenerate consistently.

---

## 14. Canonical Data Model

The canonical design schema is the source of truth for each project.

```json
{
  "schema_version": "0.1",
  "units": "mm",
  "interface_a": {
    "profile_type": "circle",
    "profile_points": [],
    "dimensions": [
      {
        "name": "outer_diameter",
        "value": 34.5,
        "provenance": "user_entered",
        "confidence": 1.0
      }
    ],
    "approved": true
  },
  "interface_b": {
    "profile_type": "circle",
    "profile_points": [],
    "dimensions": [
      {
        "name": "outer_diameter",
        "value": 52.0,
        "provenance": "user_entered",
        "confidence": 1.0
      }
    ],
    "approved": true
  },
  "connection": {
    "mode": "offset",
    "length": 90.0,
    "offset_x": 12.0,
    "offset_y": 0.0,
    "angle_deg": 0.0
  },
  "manufacturing": {
    "process": "fdm",
    "material": "PETG",
    "wall_thickness": 2.4,
    "clearance_a": 0.3,
    "clearance_b": 0.5
  }
}
```

AI may propose changes to this schema, but only validated changes may reach the KCL generator.

---

## 15. Geometry Strategy

### Supported families

**Hollow flow adapters**
- circular to circular;
- circular to rectangular;
- rectangular to rectangular;
- supported traced-profile transitions.

**Flat mounting adapters**
- plate between simple mounting patterns;
- circular or rectangular holes;
- limited offsets;
- countersink/counterbore only if reliable.

### Loft normalization

Before lofting traced profiles:

1. remove noise;
2. enforce closure;
3. remove duplicate points;
4. validate winding direction;
5. resample profiles;
6. align start points;
7. validate concavity;
8. check self-intersection;
9. validate transition length and angle;
10. reject unsupported geometry.

### Safeguards

Enforce conservative limits for wall thickness, angle, transition length, offset-to-length ratio, point count, contour complexity, edge-treatment radius, and clearance range. Initial limits may be empirical but must be documented.

---

## 16. AI Responsibilities

### Vision model
May assist with profile detection, reading dimensions, identifying likely shapes, and explaining image-quality problems. It returns structured data, never final KCL.

### Zoo Agent API
Handles natural-language parameter revisions, explanations of missing information, clarification prompts, readable failure explanations, and design summaries.

Expected output is constrained JSON, for example:

```json
{
  "parameter_changes": {
    "manufacturing.clearance_a": 0.5,
    "connection.length": 110
  },
  "requires_confirmation": true,
  "explanation": "The vacuum-side fit was loosened and the transition was extended."
}
```

### Forbidden AI behaviour

AI must not silently overwrite approved dimensions, bypass validation, claim certification, invent unmarked dimensions, expose secrets, or directly control final geometry without validation.

---

## 17. Zoo API Responsibilities

### Engine API
Required for model generation, regeneration, geometry execution, rendering/snapshots, and supported validation.

### Agent API
Required for structured revisions, explanation, or recovery.

### File Format API
Required for useful output conversion, STL production or verification, and model analysis such as volume where reliable.

Zoo use must be meaningful, visible, and documented.

---

## 18. UX Requirements

The interface must feel guided and understandable to a non-CAD user.

Required states:

- start;
- upload;
- image-quality guidance;
- processing;
- profile review;
- validation failure;
- profile approval;
- connection selection;
- connection configuration;
- generation;
- result;
- revision;
- export failure;
- export success.

Dimension provenance must not rely on colour alone; include labels or icons.

Basic accessibility requirements:

- keyboard-accessible fields;
- clear labels;
- sufficient contrast;
- non-colour indicators;
- readable errors;
- adequately sized controls;
- descriptive buttons;
- logical focus order;
- no critical information shown only in the 3D viewport.

Long-running operations must show progress, current stage, retry, and useful failure information.

---

## 19. Privacy and Security

Uploaded images may reveal surroundings, proprietary components, equipment, or notes.

Requirements:

- never commit uploads;
- never expose API keys in frontend code;
- use environment variables;
- avoid persistent storage unless required;
- delete temporary uploads where practical;
- disclose use of external AI services;
- do not log raw images by default;
- do not claim enterprise confidentiality;
- redact secrets from logs;
- include `.env.example` without real keys.

---

## 20. Error Model

Error categories:

1. input/image;
2. profile extraction;
3. dimension conflict;
4. profile validation;
5. design-rule violation;
6. KCL generation;
7. Engine API;
8. Agent API;
9. File Format API;
10. export/download.

Each error includes a user explanation, corrective action, internal ID, and technical detail in logs.

Example:

**IF-PROFILE-004** — The detected contour crosses itself and cannot be converted into a solid. Remove the overlapping segment or upload a clearer sketch.

---

## 21. Success Metrics

### Product success

- User completes the workflow without CAD software.
- Both profiles are reviewed and corrected.
- Model regenerates after parameter changes.
- STL and KCL are produced. STEP is planned but not implemented for this submission.
- At least one printed adapter physically fits.
- Workflow is understandable in the demo.
- Failures are clearly explained.

### Technical success

- Deterministic generation for known-good fixtures.
- No secrets committed.
- API failures captured and reproducible.
- Schema and KCL saved for debugging.
- Clear local setup.
- Tests cover validation and generation logic.

### Competition success

The repository must visibly support documentation, notes and bug reporting, technical depth and readability, UI/UX, and creativity.

---

## 22. Competition Deliverables

- public open-source GitHub repository;
- README covering problem, reasoning, workflow, Zoo API usage, setup, limitations, and demo;
- approximately one-minute demo video;
- public social post with required hashtag and Zoo tag;
- official submission form;
- architecture diagram;
- API notes;
- bug and limitation log;
- test results;
- screenshots;
- physical print evidence;
- open-source licence;
- no committed credentials.

---

## 23. Documentation Structure

```text
README.md
LICENSE
docs/
  PRODUCT_BRIEF.md
  PRD.md
  ARCHITECTURE.md
  API_USAGE.md
  DESIGN_SCHEMA.md
  GEOMETRY_RULES.md
  TEST_PLAN.md
  TEST_RESULTS.md
  ZOO_API_NOTES.md
  BUGS_AND_LIMITATIONS.md
  DESIGN_DECISIONS.md
  DEMO_SCRIPT.md
  SUBMISSION_CHECKLIST.md
```

Agents must update the relevant document when making material decisions.

---

## 24. Proposed Technical Architecture

```text
Frontend
  ├── image upload and guidance
  ├── editable SVG profile review
  ├── connection configuration
  ├── 3D result viewer
  └── export/revision UI

Backend
  ├── upload handling
  ├── vision-model adapter
  ├── canonical schema validation
  ├── geometry rules
  ├── deterministic KCL generator
  ├── Zoo Engine API client
  ├── Zoo Agent API client
  ├── Zoo File Format API client
  ├── logging
  └── artifact management
```

Recommended stack:

- Python 3.12;
- FastAPI;
- Pydantic;
- pytest;
- React + Vite;
- SVG-based 2D editor;
- browser-compatible 3D viewer or Zoo render output;
- environment-based secret management.

The stack may change if API testing reveals a clearly superior supported path.

---

## 25. Testing Strategy

### Unit tests

- schema validation;
- unit conversion;
- provenance states;
- profile closure;
- duplicate-point removal;
- self-intersection;
- connection limits;
- clearance logic;
- wall-thickness rules;
- Agent patch validation;
- KCL emission.

### Integration tests

- schema to KCL;
- KCL to Engine API;
- Engine output to File Format API;
- revision to regeneration;
- failure logging.

### Known-good fixtures

1. coaxial circular vacuum reducer;
2. offset circular adapter;
3. coaxial or offset circular adapter;
4. simple rectangular transition;
5. flat camera mounting plate.

### Physical test

The hero vacuum adapter must be generated, exported, printed, test-fitted, measured, revised if needed, and documented honestly.

---

## 26. Risks and Mitigations

- **Unreliable image extraction:** guided capture, calibration, SVG approval, confidence thresholds, graceful rejection.
- **Loft failure:** contour normalization, complexity limits, supported shape families, deterministic fallbacks.
- **Angled geometry failure:** angle and offset limits, minimum lengths, validation before execution.
- **Unsafe Agent output:** constrained JSON, allowlisted fields, validation, confirmation gate.
- **Zoo API changes:** logging, snapshots, known-good fixtures, dated bug reports, thin wrapper layer.
- **Weak manual correction in Zoo:** correction occurs in InterfaceForge, not Design Studio.
- **Scope creep:** vacuum adapter first, camera adapter second, optional work only after core stability.
- **Live demo instability:** deterministic saved test case and pre-approved inputs while still showing the real core flow.
- **Compliance failure:** clean repository after contest start, public repo, required docs, social post, correct email, internal early deadline.

---

## 27. Priority Order

### P0 — must work

- upload two inputs;
- extract or define two profiles;
- edit dimensions;
- approve profiles;
- configure coaxial adapter;
- generate deterministic KCL;
- execute through Zoo;
- preview result;
- export STL and KCL; STEP is planned but not implemented for this submission;
- document everything.

### P1 — should work

- offset connection;
- angle-based connections are not supported;
- natural-language revision;
- volume analysis;
- physical vacuum-adapter proof;
- flat camera adapter.

### P2 — nice to have

- draggable SVG points;
- advanced profile types;
- material estimate;
- saved local projects;
- GLB export;
- before/after comparison.

No P2 work may begin while any P0 item is unstable.

---

## 28. Decision Rules for AI Agents

1. Read this PRD before changing scope or architecture.
2. Do not build unrequested features.
3. Do not replace deterministic geometry with unrestricted AI generation.
4. Do not remove validation to make a demo pass.
5. Do not hide errors.
6. Do not commit secrets.
7. Do not perform destructive refactors without rollback.
8. Keep changes small, testable, and documented.
9. Update relevant docs with significant changes.
10. Record Zoo API bugs with reproduction steps.
11. Ask approval for changes to scope, schema, API responsibilities, user flow, formats, or compliance.
12. Preserve working behaviour unless explicitly replacing it.
13. Prefer one reliable adapter class over several unstable ones.
14. Avoid unverified accuracy claims.
15. The product owner performs final QA and scope approval.

---

## 29. Open Decisions

- exact vision model;
- exact Zoo SDK or direct API route;
- 3D viewer approach;
- traced-profile complexity limit;
- angle limit;
- minimum transition-length formula;
- default clearance presets;
- default wall-thickness recommendation;
- export route for STL; STEP is planned but not implemented;
- reliability of volume analysis;
- whether camera adapter remains in MVP.

Record resolutions in `docs/DESIGN_DECISIONS.md`.

---

## 30. Definition of Done

InterfaceForge MVP is done when:

1. The primary workflow functions end to end.
2. A non-CAD user can understand each step.
3. Two approved profiles generate a parametric adapter.
4. At least coaxial generation is reliable.
5. The model can be revised through safe controls.
6. Zoo APIs are meaningfully and visibly used.
7. STL and KCL are downloadable; STEP is planned but not implemented for this submission.
8. One adapter has been physically printed and tested.
9. Critical errors have clear handling.
10. The repository is public, documented, reproducible, and secret-free.
11. Demo video and social post are ready.
12. Submission checklist is complete.
13. Known limitations are documented honestly.
14. No critical P0 bug remains.

---

## 31. Final Positioning

InterfaceForge is not a replacement for professional CAD.

It is a guided adapter-generation tool for people who know what two physical interfaces must connect but do not know how to model the missing geometry.

> **Two interfaces in. One verified, parametric, manufacturable adapter out.**
