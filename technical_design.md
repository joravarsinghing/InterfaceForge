## Implementation configuration and evidence

The active backend settings are `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `DEBUG`, `CORS_ORIGINS`, `HOST`, `PORT`, `DB_PATH`, `ENGINE_PROVIDER`, `ZOO_API_TOKEN`, `ZOO_API_BASE_URL`, `GENERATION_TIMEOUT_SECONDS`, `ANALYSIS_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_VISION_MODEL`, `GEMINI_VISION_FALLBACK_MODEL`, `GEMINI_VISION_FALLBACK_ENABLED`, `GEMINI_MODEL`, `ANALYSIS_TIMEOUT_SECONDS`, `OPENROUTER_API_KEY`, `OPENROUTER_API_BASE_URL`, `OPENROUTER_VISION_MODEL`, `OPENROUTER_VISION_FALLBACK_MODEL`, and `EXPORT_PROVIDER`. The frontend uses `VITE_BACKEND_URL`.

SQLite is configured by `DB_PATH` and defaults to `artifacts/interfaceforge.db`. Uploads, generated KCL, previews, and exports use the runtime `artifacts` directory. Render filesystem persistence must be treated as deployment-dependent; the application does not claim durable object storage.

The active Agent allowlist contains exactly six fields: `connection.length_mm`, `connection.offset_x_mm`, `connection.offset_y_mm`, `manufacturing.wall_thickness_mm`, `manufacturing.clearance_a_mm`, and `manufacturing.clearance_b_mm`. Confirmation changes canonical values and marks the model stale; a separate generation request is required.

A prior credentialed Zoo Agent integration flow completed successfully. During the focused 2026-08-04 adversarial audit, 17 of 18 Agent attempts timed out or closed their WebSocket. The direct live Engine audit timed out before a fresh STL conversion result. These observations do not establish a confirmed Zoo defect, and offline tests are not live-provider proof.
## Current submission evidence and boundary

This design document preserves historical rationale below, but active behavior is: two approved profiles, two-point calibration with one known real-world distance per profile, OpenCV tracing, LoftPlan authority, KCL 2.0, coaxial/parallel offset connections, bounded Zoo Agent proposals, separate regeneration after confirmation, SQLite persistence, and STL/KCL exports. STEP and angle-based connections are not submission capabilities. A prior credentialed Zoo Agent flow succeeded; the focused 2026-08-04 audit had 17 of 18 Agent attempts timeout or close WebSocket, and the direct live Engine audit timed out before a fresh STL conversion result. Offline tests are not live-provider proof.


# InterfaceForge Ã¢â‚¬â€ Technical Design

**Document status:** Submission implementation record  
**Last reviewed:** 2026-08-03  
**Source documents:** `InterfaceForge_PRD_v0.1.md`, `user_flow.md`, `ascii_wireframes.md`  
**Audience:** Product owner, technical lead, implementation agents, reviewers, and judges  
**Purpose:** Describe the implemented architecture, contracts, boundaries, operational model, and important technical decisions for the Zoo API Makeathon submission.

---

# Technical Design

## 1. Context

InterfaceForge is a guided adapter-generation application for users who do not know CAD but can provide two clean 2D interface profiles and known real-world measurements.

The product converts:

`	ext
Two user-approved 2D interface definitions
        +
Connection relationship
        +
Manufacturing parameters
        Ã¢â€ â€œ
Validated canonical project schema
        Ã¢â€ â€œ
Persisted LoftPlan
        Ã¢â€ â€œ
Deterministic KCL 2.0
        Ã¢â€ â€œ
Zoo Engine execution
        Ã¢â€ â€œ
3D preview, KCL, and STL output
``

The primary submission scenario is a hollow dust-extraction adapter connecting:

* a circular vacuum-hose profile;
* a rounded-rectangle CNC dust-port profile.

The system prioritizes:

* accessibility over unrestricted CAD flexibility;
* deterministic geometry over unconstrained AI generation;
* explicit user approval over hidden inference;
* validated canonical data over direct model manipulation;
* clear recovery over silent failure;
* meaningful Zoo API integration;
* one reliable adapter workflow over many unstable features.

---

## 2. Submission scope

### Supported capabilities

* Two interface profiles per project
* Clean image upload
* OpenCV-based profile extraction
* Two-point scale calibration
* User review and approval
* Circle profiles
* Rectangle profiles
* Rounded-rectangle profiles
* Approved arbitrary traced closed profiles
* Fit-over and fit-inside intent
* Coaxial connections
* Parallel offset connections
* Transition length
* X and Y offset
* Wall thickness
* Interface clearances
* Interface A and B straight extensions
* Deterministic KCL 2.0 generation
* Zoo Engine execution
* Natural-language bounded parameter revisions
* KCL export
* Verified STL export
* Model revision tracking
* Last-known-good model preservation

### Not implemented for submission

* STEP export
* Angle-based connections
* Internal cavities within uploaded profiles
* Threads
* Mounting holes
* Countersinks
* Dovetails
* Undercuts
* Assemblies
* Curved pipe paths
* Certified manufacturing readiness
* Unrestricted photograph-to-CAD reconstruction

---

## 3. Constraints

### Competition constraints

* The project must remain open source.
* Zoo API use must be meaningful and visible.
* API credentials must not be committed.
* The final workflow must be understandable and reproducible.
* Documentation must accurately distinguish verified features from planned features.
* The final demo video must remain within the competition time limit.

### Product constraints

* No end-user authentication.
* No billing or subscription system.
* Desktop-first interface.
* Two interfaces per project.
* Each interface requires explicit review and approval.
* The user must not need to operate Zoo Design Studio manually.
* The system outputs KCL and STL.
* STEP is planned but not implemented for this submission.

### Geometry constraints

Supported profiles:

* circle;
* rectangle;
* rounded rectangle;
* validated traced closed profile.

Supported connection modes:

* coaxial;
* parallel offset.

Unsupported:

* angle-based connections;
* curved centerline paths;
* multiple branches;
* nested internal cavities;
* unrestricted freeform surfacing.

Traced profiles must be:

* closed;
* finite;
* non-self-intersecting;
* consistently wound;
* resampled to compatible point counts;
* reviewed by the user before approval.

### Operational constraints

* Render instances may restart or sleep.
* Cloudflare Pages serves only the frontend.
* Zoo services may be temporarily unavailable.
* Zoo Agent and Zoo Engine may fail independently.
* Uploaded images and provider outputs are untrusted.
* Failed generation must not destroy the previous successful model.

---

## 4. Deployment architecture

``text
Ã¢â€Å’Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â
Ã¢â€â€š Cloudflare Pages                                              Ã¢â€â€š
Ã¢â€â€š                                                               Ã¢â€â€š
Ã¢â€â€š React + Vite frontend                                         Ã¢â€â€š
Ã¢â€â€š - Guided workflow                                             Ã¢â€â€š
Ã¢â€â€š - Upload and calibration UI                                   Ã¢â€â€š
Ã¢â€â€š - Profile review                                              Ã¢â€â€š
Ã¢â€â€š - Connection configuration                                    Ã¢â€â€š
Ã¢â€â€š - Preview and result screens                                  Ã¢â€â€š
Ã¢â€â€š - Agent revision panel                                        Ã¢â€â€š
Ã¢â€â€š - KCL and STL download controls                               Ã¢â€â€š
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Ëœ
                               Ã¢â€â€š HTTPS
                               Ã¢â€â€š VITE_BACKEND_URL
                               Ã¢â€“Â¼
Ã¢â€Å’Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â
Ã¢â€â€š Render                                                        Ã¢â€â€š
Ã¢â€â€š                                                               Ã¢â€â€š
Ã¢â€â€š FastAPI backend                                               Ã¢â€â€š
Ã¢â€â€š - Project/session API                                         Ã¢â€â€š
Ã¢â€â€š - SQLite persistence                                          Ã¢â€â€š
Ã¢â€â€š - Upload and artifact storage                                 Ã¢â€â€š
Ã¢â€â€š - OpenCV analysis                                             Ã¢â€â€š
Ã¢â€â€š - Profile normalization                                       Ã¢â€â€š
Ã¢â€â€š - Canonical schema management                                 Ã¢â€â€š
Ã¢â€â€š - LoftPlan generation                                         Ã¢â€â€š
Ã¢â€â€š - KCL 2.0 compiler                                            Ã¢â€â€š
Ã¢â€â€š - Zoo Engine integration                                      Ã¢â€â€š
Ã¢â€â€š - Zoo Agent integration                                       Ã¢â€â€š
Ã¢â€â€š - STL generation and validation                               Ã¢â€â€š
Ã¢â€â€š - Revision and export lineage                                 Ã¢â€â€š
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Ëœ
                        Ã¢â€â€š Server-side credentials
                        Ã¢â€“Â¼
Ã¢â€Å’Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Â
Ã¢â€â€š Zoo services                                                  Ã¢â€â€š
Ã¢â€â€š                                                               Ã¢â€â€š
Ã¢â€â€š - Zoo Engine                                                  Ã¢â€â€š
Ã¢â€â€š - Zoo Agent                                                   Ã¢â€â€š
Ã¢â€â€š - KCL execution/export tooling                                Ã¢â€â€š
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€Ëœ
``

### Deployment rules

* Zoo credentials exist only in Render environment variables.
* The frontend never receives provider secrets.
* `VITE_BACKEND_URL` points the Cloudflare frontend to the Render backend.
* Render is the authoritative application backend.
* Cloudflare Pages serves static frontend assets only.
* Generated artifacts remain associated with project and model revisions.

---

## 5. Architectural style

InterfaceForge uses:

* one React frontend;
* one FastAPI backend;
* SQLite persistence;
* deterministic service boundaries;
* a canonical project schema;
* a persisted LoftPlan as the geometry plan;
* generated KCL as the executable CAD artifact;
* server-side Zoo integrations;
* explicit model and schema revision tracking.

The architecture avoids:

* direct browser access to Zoo credentials;
* arbitrary Agent-generated KCL;
* multiple competing geometry authorities;
* export regeneration from a different schema;
* silent fallback from live Agent behavior to Mock behavior.

---

## 6. Core data flow

``text
Image upload
    Ã¢â€ â€œ
Image validation
    Ã¢â€ â€œ
OpenCV profile extraction
    Ã¢â€ â€œ
Profile normalization
    Ã¢â€ â€œ
Two-point calibration
    Ã¢â€ â€œ
User review and approval
    Ã¢â€ â€œ
Connection and manufacturing configuration
    Ã¢â€ â€œ
Server-side validation
    Ã¢â€ â€œ
Canonical project update
    Ã¢â€ â€œ
LoftPlan generation
    Ã¢â€ â€œ
Deterministic KCL 2.0 compilation
    Ã¢â€ â€œ
Zoo Engine execution
    Ã¢â€ â€œ
Model revision marked current
    Ã¢â€ â€œ
KCL and STL made available
``

For Agent revisions:

``text
Natural-language request
    Ã¢â€ â€œ
Zoo Agent interpretation
    Ã¢â€ â€œ
Structured bounded proposal
    Ã¢â€ â€œ
Server-side allowlist validation
    Ã¢â€ â€œ
Trusted arithmetic using current project values
    Ã¢â€ â€œ
User confirmation
    Ã¢â€ â€œ
Canonical project update
    Ã¢â€ â€œ
Derived geometry marked stale
    Ã¢â€ â€œ
LoftPlan rebuilt
    Ã¢â€ â€œ
KCL regenerated
    Ã¢â€ â€œ
Zoo Engine executes revised model
    Ã¢â€ â€œ
New model revision and exports
``

---

## 7. Component responsibilities

### 7.1 Frontend application

Responsible for:

* guided navigation;
* image upload;
* calibration interaction;
* profile review;
* fit-intent selection;
* connection configuration;
* validation feedback;
* loading and generation progress;
* result preview;
* Agent revision requests;
* proposal confirmation;
* KCL and STL download actions;
* user-facing errors.

Must not:

* contain Zoo credentials;
* generate authoritative KCL;
* apply Agent changes without confirmation;
* treat client validation as authoritative;
* fabricate generation success.

### 7.2 API layer

Responsible for:

* route handling;
* request parsing;
* project-token validation;
* Pydantic validation;
* response envelopes;
* error normalization;
* service orchestration;
* authorization checks.

### 7.3 Project service

Responsible for:

* project creation;
* project-token validation;
* workflow state;
* schema revision tracking;
* approved interface state;
* connection and manufacturing configuration;
* stale/current transitions;
* model revision records;
* last-known-good revision;
* persistence through SQLite.

### 7.4 Analysis provider

Responsible for:

* reading uploaded profile images;
* preprocessing;
* contour detection;
* primitive classification where applicable;
* arbitrary closed contour extraction;
* confidence and warning output;
* trace artifact generation.

OpenCV is the authoritative profile-extraction path for the controlled workflow.

External vision assistance, where present, is advisory and untrusted.

### 7.5 Profile normalization

Responsible for:

* contour closure;
* duplicate-point removal;
* winding normalization;
* point resampling;
* start-point alignment;
* self-intersection detection;
* finite coordinate validation;
* supported complexity limits;
* conversion to canonical millimetre coordinates.

### 7.6 Canonical project schema

Responsible for storing:

* interface definitions;
* calibration information;
* profile geometry;
* approval state;
* fit intent;
* connection configuration;
* manufacturing parameters;
* schema revision;
* model revision;
* last-known-good revision;
* current workflow state.

This schema is the application source of truth.

### 7.7 LoftPlan service

Responsible for producing one authoritative geometry plan from the canonical project.

The LoftPlan defines:

* outer profile sections;
* inner profile sections;
* Z positions;
* offsets;
* interface extensions;
* compatible point correspondence;
* transition geometry;
* metadata required for preview and KCL.

The preview and KCL compiler must consume the same LoftPlan.

### 7.8 Geometry validation

Responsible for:

* approved-interface prerequisites;
* positive transition length;
* wall-thickness validation;
* clearance bounds;
* offset limits;
* fit-intent compatibility;
* profile validity;
* self-intersection risk;
* extension validity;
* manufacturing warnings.

Angle validation is not part of the current submission because angle-based connections are unsupported.

### 7.9 KCL compiler

Responsible for:

* converting the LoftPlan into deterministic KCL 2.0;
* emitting current supported KCL syntax;
* generating solid outer geometry;
* generating the inner cutter;
* performing solid subtraction;
* using stable variable names;
* declaring units explicitly;
* maintaining deterministic output;
* producing a KCL hash;
* rejecting invalid geometry before execution.

The current compiler uses KCL 2.0 solid-body generation. Historical surface-shell and `joinSurfaces()` workarounds are not part of the active design.

### 7.10 Zoo Engine integration

Responsible for:

* executing the generated KCL;
* returning generation status;
* reporting progress;
* capturing normalized errors;
* associating the result with the exact KCL artifact;
* preserving the previous model after failure.

Generation success must refer to execution of the actual project KCL, not placeholder modeling commands.

### 7.11 Zoo Agent integration

Responsible for interpreting natural-language parameter requests into structured proposals.

Supported bounded fields include:

* `connection.length_mm`
* `connection.offset_x_mm`
* `connection.offset_y_mm`
* `manufacturing.wall_thickness_mm`
* `manufacturing.clearance_a_mm`
* `manufacturing.clearance_b_mm`

Supported operations include:

* increase;
* decrease;
* set.

Common aliases include:

* length;
* height;
* transition height;
* adapter height;
* longer;
* shorter;
* tolerance;
* clearance.

The Agent must not:

* generate KCL;
* modify profile contours;
* modify provider settings;
* bypass server validation;
* directly apply project changes.

Server-side code calculates the trusted final value using the current project state.

### 7.12 Export service

Responsible for:

* exposing the current KCL artifact;
* generating and validating STL;
* associating exports with model revisions;
* rejecting stale exports;
* caching current-revision artifacts where safe;
* reporting per-format status.

Supported outputs:

* KCL;
* STL.

STEP is not implemented for this submission.

### 7.13 Artifact manager

Responsible for:

* uploaded images;
* cleaned images;
* analysis images;
* trace SVGs;
* overlay SVGs;
* persisted KCL;
* STL files;
* artifact metadata;
* safe filenames;
* project-scoped access;
* cleanup.

### 7.14 Observability

Responsible for:

* request IDs;
* provider selection logs;
* generation stages;
* durations;
* schema revision;
* model revision;
* KCL hash;
* export status;
* normalized errors;
* secret redaction.

Tokens and raw credentials must never appear in logs.

---

## 8. Trust boundaries

``text
Untrusted user input
    - images
    - calibration points
    - dimensions
    - connection values
    - Agent prompts
        Ã¢â€ â€œ
Application validation boundary
        Ã¢â€ â€œ
Canonical project schema
        Ã¢â€ â€œ
LoftPlan
        Ã¢â€ â€œ
Deterministic KCL compiler
        Ã¢â€ â€œ
Zoo execution
        Ã¢â€ â€œ
Validated KCL and STL artifacts
``

### Trust rules

* User input is untrusted.
* Image-analysis output is untrusted until reviewed.
* Profile approval is explicit.
* Agent output is always untrusted.
* Agent proposals are never directly executable.
* KCL is generated only from validated canonical data.
* Export artifacts must be validated.
* API credentials remain server-side.
* Generation success does not imply certified manufacturability.

---

## 9. Data model

### 9.1 Project

``json
{
  "project_id": "uuid",
  "project_token": "secret-project-token",
  "schema_version": "0.1",
  "state": "interfaces_approved",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "interface_a": {},
  "interface_b": {},
  "connection": {},
  "manufacturing": {},
  "loft_plan": {},
  "current_schema_revision": 3,
  "current_model_revision": 2,
  "last_known_good_model_revision": 2,
  "model_revisions": []
}
``

### 9.2 Interface definition

``json
{
  "id": "interface_a",
  "source_image_ref": "artifact-id",
  "profile_type": "custom_closed",
  "profile_points": [],
  "center": {
    "x": 0.0,
    "y": 0.0
  },
  "fit_mode": "fit_over",
  "scale_calibration": {
    "point_a": {
      "x": 10.0,
      "y": 15.0
    },
    "point_b": {
      "x": 110.0,
      "y": 15.0
    },
    "known_distance_mm": 60.0,
    "confirmed": true
  },
  "validation": {
    "is_closed": true,
    "self_intersects": false,
    "warnings": []
  },
  "approved": true,
  "approved_at": "ISO-8601"
}
``

### 9.3 Connection definition

``json
{
  "mode": "offset",
  "length_mm": 50.0,
  "offset_x_mm": 10.0,
  "offset_y_mm": 0.0,
  "angle_deg": 0.0,
  "extension_a_mm": 12.0,
  "extension_b_mm": 12.0
}
``

`angle_deg` may remain in the persisted schema for backward compatibility, but submission workflows require it to remain `0.0`.

### 9.4 Manufacturing definition

``json
{
  "process": "fdm",
  "material": "PETG",
  "wall_thickness_mm": 2.4,
  "clearance_a_mm": 0.3,
  "clearance_b_mm": 0.1
}
``

### 9.5 Model revision

``json
{
  "model_revision": 2,
  "schema_revision": 3,
  "status": "current",
  "kcl_artifact_ref": "artifact-id",
  "kcl_hash": "sha256",
  "preview_artifact_ref": "artifact-id",
  "exports": {
    "stl": "artifact-id"
  },
  "warnings": [],
  "generated_at": "ISO-8601"
}
``

### 9.6 Agent proposal

``json
{
  "changes": [
    {
      "field": "connection.length_mm",
      "operation": "decrease",
      "amount": 3.0,
      "current_value": 50.0,
      "proposed_value": 47.0,
      "unit": "mm",
      "reason": "Decrease transition height by 3 mm."
    }
  ],
  "summary": "Decrease transition height from 50 mm to 47 mm.",
  "is_valid": true,
  "provider_used": "zoo"
}
``

### 9.7 Error record

``json
{
  "error_id": "IF-ENGINE-004",
  "request_id": "uuid",
  "category": "engine",
  "message": "The adapter could not be generated.",
  "recovery_steps": [
    "Review the connection parameters.",
    "Retry model generation."
  ],
  "retryable": true,
  "timestamp": "ISO-8601"
}
``

---

## 10. Implemented API design

API responses use:

``json
{
  "success": true,
  "data": {}
}
``

Errors use the application error model with:

* error ID;
* message;
* recovery steps;
* HTTP status;
* safe technical context.

### Core project routes

``text
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
``

### Provider routes

``text
GET    /api/projects/provider-mode
PATCH  /api/projects/provider-mode
GET    /api/projects/{project_id}/provider-mode
PATCH  /api/projects/{project_id}/provider-mode
``

### Interface routes

``text
POST   /api/projects/{project_id}/interfaces/{interface_id}/upload
POST   /api/projects/{project_id}/interfaces/{interface_id}/analyze
PATCH  /api/projects/{project_id}/interfaces/{interface_id}
POST   /api/projects/{project_id}/interfaces/{interface_id}/approve
``

### Calibration routes

``text
POST   /api/projects/{project_id}/interfaces/{interface_id}/scale/snap
POST   /api/projects/{project_id}/interfaces/{interface_id}/scale/calibrate
DELETE /api/projects/{project_id}/interfaces/{interface_id}/scale/calibration
``

### Artifact routes

``text
GET /api/projects/{project_id}/interfaces/{interface_id}/image
GET /api/projects/{project_id}/interfaces/{interface_id}/cleaned_image
GET /api/projects/{project_id}/interfaces/{interface_id}/analysis_image
GET /api/projects/{project_id}/interfaces/{interface_id}/trace_svg
GET /api/projects/{project_id}/interfaces/{interface_id}/overlay_svg
``

### Connection and validation routes

``text
PUT  /api/projects/{project_id}/connection
POST /api/projects/{project_id}/connection/validate
``

Exact route names should remain synchronized with the implementation.

### KCL routes

``text
GET  /api/projects/{project_id}/kcl/readiness
POST /api/projects/{project_id}/kcl/compile
GET  /api/projects/{project_id}/kcl
``

### Generation routes

``text
POST /api/projects/{project_id}/generation
GET  /api/projects/{project_id}/generation/{job_id}
``

### Revision routes

``text
POST /api/projects/{project_id}/revision/propose
POST /api/projects/{project_id}/revision/confirm
``

### Export routes

``text
GET  /api/projects/{project_id}/exports/status
POST /api/projects/{project_id}/exports
POST /api/projects/{project_id}/exports/{format}/retry
GET  /api/projects/{project_id}/exports/{format}/download
``

### Contract rules

* Project routes require the project token where applicable.
* Raw KCL is never accepted from the browser.
* Profile approval requires server-side validation.
* Agent output cannot bypass the allowlist.
* Revision confirmation marks derived geometry stale.
* Export requests require a current successful model.
* Stale model exports are rejected.
* STEP requests are unsupported.

---

## 11. Authentication and authorization

### End-user authentication

No user account system is implemented.

Projects are protected using:

* project ID;
* unguessable project token.

### Backend authorization

* Zoo credentials are stored in Render environment variables.
* The frontend never receives Zoo tokens.
* Project-scoped routes validate the project token.
* Artifact access is scoped to the project.
* Invalid tokens produce a structured authorization error.

### Secret handling

* `.env` files are not committed.
* `.env.example` contains variable names only.
* Logs redact credentials.
* Provider failures never expose tokens in responses.

---

## 12. Validation strategy

Validation occurs in layers.

### 12.1 Client validation

Used for immediate feedback:

* required fields;
* numeric input;
* file type;
* file size;
* obvious parameter bounds;
* workflow prerequisites.

Client validation is not authoritative.

### 12.2 API validation

Pydantic validates:

* data types;
* enums;
* ranges;
* required fields;
* finite numbers;
* request structure.

### 12.3 Image validation

Checks:

* supported file type;
* valid image bytes;
* safe filename;
* readable dimensions;
* non-empty upload.

### 12.4 Profile validation

Checks:

* closure;
* duplicate points;
* self-intersection;
* minimum dimensions;
* valid scale;
* finite coordinates;
* supported complexity;
* usable contour area.

### 12.5 Connection validation

Checks:

* both interfaces approved;
* positive transition length;
* valid offset;
* wall thickness;
* clearance ranges;
* extension ranges;
* compatible profile geometry.

### 12.6 Agent validation

Checks:

* valid structured response;
* allowed field;
* valid operation;
* finite numeric amount;
* trusted current value;
* resulting value within bounds;
* no duplicate field changes;
* no profile or provider modifications.

### 12.7 KCL preflight

Checks:

* valid LoftPlan;
* compatible section point counts;
* finite coordinates;
* valid Z ordering;
* valid KCL 2.0 syntax construction;
* required solid operations;
* deterministic output;
* valid KCL hash.

### 12.8 Post-generation validation

Checks where available:

* generation completed successfully;
* KCL artifact exists;
* generated model revision matches the schema revision;
* STL is non-empty;
* STL has valid facets;
* STL bounding dimensions are plausible;
* STL topology is suitable for the supported workflow.

---

## 13. KCL generation design

The current KCL compiler targets current KCL 2.0 standards.

The generated model contains:

1. outer profile sketches;
2. inner profile sketches;
3. outer solid loft;
4. inner cutter loft;
5. solid subtraction;
6. one resulting hollow adapter body.

Conceptually:

``kcl
@settings(defaultLengthUnit = mm, kclVersion = 2.0)

outer_solid = loft(
  [...],
  vDegree = 1,
  baseCurveIndex = 0,
  bodyType = SOLID
)

inner_cutter = loft(
  [...],
  vDegree = 1,
  baseCurveIndex = 0,
  bodyType = SOLID
)

adapter_model = subtract(
  [outer_solid],
  tools = [inner_cutter]
)
``

The exact emitted syntax is controlled by the current compiler and tests.

### KCL design rules

* KCL must use current KCL 2.0 syntax.
* Variable names must be deterministic.
* Outer and inner profiles must use compatible point correspondence.
* Extensions must be represented consistently.
* The inner cutter may extend slightly beyond the end planes to ensure a through-hole.
* Surface-shell generation is not the active path.
* `joinSurfaces()` is not the current adapter construction.
* Generated KCL must be persisted before execution.
* Execution and export must use the same KCL artifact and revision lineage.

---

## 14. Model and artifact lineage

The required lineage is:

``text
Canonical schema revision
        Ã¢â€ â€œ
LoftPlan
        Ã¢â€ â€œ
KCL bytes
        Ã¢â€ â€œ
KCL SHA-256 hash
        Ã¢â€ â€œ
Zoo execution
        Ã¢â€ â€œ
Model revision
        Ã¢â€ â€œ
STL artifact
``

Required invariants:

* one schema revision maps to one authoritative LoftPlan;
* one LoftPlan maps to deterministic KCL;
* the executed KCL matches the persisted KCL;
* the model revision records the KCL hash;
* exports belong to the exact model revision;
* stale revisions cannot produce current exports;
* failed revisions preserve the previous successful model.

---

## 15. Agent revision design

The Agent is used for language interpretation, not CAD authorship.

Examples:

``text
Increase length by 3 mm.
Decrease height by 3 mm.
Make it 5 mm shorter.
Set wall thickness to 3 mm.
Move the outlet 10 mm right.
Increase Interface A tolerance by 0.2 mm.
``

The backend converts the proposal into trusted arithmetic.

Example:

``text
Current transition length: 50 mm
User request: decrease height by 3 mm
Agent operation: decrease
Agent amount: 3 mm
Backend result: 47 mm
``

The Agent must never independently decide the trusted current value.

### Confirmation flow

``text
Propose revision
    Ã¢â€ â€œ
Validate proposal
    Ã¢â€ â€œ
Display old and new values
    Ã¢â€ â€œ
User confirms
    Ã¢â€ â€œ
Canonical project changes
    Ã¢â€ â€œ
LoftPlan invalidated
    Ã¢â€ â€œ
Project marked stale
    Ã¢â€ â€œ
New generation starts
    Ã¢â€ â€œ
New model revision becomes current
``

---

## 16. State management

### Frontend state

Frontend state includes:

* current route;
* active project;
* project token;
* unsaved form values;
* upload state;
* calibration state;
* validation results;
* generation progress;
* revision proposal;
* export status.

### Backend state

The backend uses SQLite for persistent project state.

Stored data includes:

* project records;
* interface state;
* canonical configuration;
* revisions;
* model status;
* artifact references.

Artifacts are stored separately and referenced by project records.

### State invariants

* Interface approval is explicit.
* Editing approved inputs increments schema revision.
* Editing geometry inputs invalidates the current model.
* Successful generation creates a model revision.
* Failed generation does not replace the last-known-good model.
* Exports correspond to the current model revision.

---

## 17. Background generation

Generation jobs use staged application-managed execution.

Typical stages:

``text
queued
validating
building_loft_plan
compiling_kcl
executing_zoo
validating_result
succeeded
``

Failure states:

``text
failed
cancel_requested
cancelled
``

Generation requirements:

* one active generation job per project;
* progress reporting;
* stage-level errors;
* safe retry;
* no concurrent model overwrite;
* last-known-good preservation;
* exact KCL lineage.

---

## 18. Error model

### Categories

* `AUTH`
* `INPUT`
* `IMAGE`
* `PROFILE`
* `CALIBRATION`
* `DESIGN_RULE`
* `KCL`
* `ENGINE`
* `AGENT`
* `EXPORT`
* `SESSION`
* `NETWORK`
* `INTERNAL`

### Format

``text
IF-{CATEGORY}-{NUMBER}
``

Examples:

``text
IF-AUTH-401
IF-AGENT-503
IF-PROFILE-004
IF-KCL-001
IF-EXPORT-004
``

### Error requirements

Each user-facing error should include:

* stable ID;
* clear message;
* recovery steps;
* HTTP status;
* retryability where relevant;
* safe technical context;
* no exposed secret;
* no raw stack trace.

### Recovery rules

* Input errors preserve valid user work.
* Agent failures do not modify the project.
* Generation failures preserve the previous model.
* Stale models cannot export.
* Missing Zoo Agent configuration returns an explicit unavailable error.
* Zoo Agent must not silently fall back to Mock in the production path.

---

## 19. Caching

May be cached:

* normalized profiles by image hash;
* KCL by canonical schema hash;
* current-revision STL;
* static frontend assets;
* provider capability metadata.

Must not be broadly cached:

* project tokens;
* credentials;
* raw uploads across projects;
* unapproved profile results;
* stale exports;
* failed Agent proposals.

---

## 20. Security considerations

### Upload security

* validate file type;
* validate image bytes;
* sanitize filenames;
* prevent path traversal;
* limit file size;
* never execute uploaded content.

### Prompt security

* Agent fields are allowlisted.
* Agent cannot output executable KCL.
* Injection-like instructions are rejected or ignored.
* Provider responses are parsed as structured data.
* Non-JSON or malformed responses are rejected.

### API security

* validate project tokens;
* keep provider secrets server-side;
* redact tokens from logs;
* configure CORS only for required origins;
* avoid exposing internal paths;
* validate all artifact requests.

---

## 21. Testing strategy

### Backend tests

Cover:

* project creation and persistence;
* token validation;
* upload handling;
* OpenCV analysis;
* calibration;
* profile approval;
* connection validation;
* LoftPlan generation;
* KCL compilation;
* Agent proposal validation;
* relative increase/decrease/set operations;
* generation state;
* last-known-good behavior;
* STL validation;
* stale export rejection.

### Frontend tests

Cover:

* workflow navigation;
* upload states;
* profile review;
* calibration UI;
* connection configuration;
* fit-intent controls;
* explicit preview generation;
* number-input behavior;
* generation progress;
* Agent proposal review;
* export controls;
* stale-state warnings.

### Live checks

Submission-critical live checks include:

* deployed frontend loads from Cloudflare Pages;
* frontend reaches Render backend;
* project creation works;
* upload and analysis work;
* KCL generation works;
* Zoo Engine generation succeeds;
* STL download succeeds;
* Agent revision works when credentialed.

Live Zoo Agent execution should only be claimed as verified when a credentialed request has been completed successfully.

---

## 22. Current limitations

* Clean, front-facing profile images are strongly preferred.
* Perspective correction is not implemented.
* Dimensioned drawings may produce false edges.
* Internal cavities in input profiles are not supported.
* STEP export is not implemented.
* Angle-based connections are not supported.
* Complex manufacturing features are outside scope.
* Render cold starts may delay the first request.
* Generated results require user inspection before manufacturing.

---

## 23. Deployment configuration

### Frontend

Platform:

``text
Cloudflare Pages
``

Required frontend variable:

``text
VITE_BACKEND_URL
``

This must point to the deployed Render backend.

### Backend

Platform:

``text
Render
``

Backend requirements include:

* Python runtime;
* FastAPI application;
* SQLite-compatible storage;
* writable artifact directory;
* Zoo API credentials;
* allowed frontend CORS origin;
* environment-based configuration.

### Secrets

Typical server-side environment variables include:

``text
ZOO_API_TOKEN
ENGINE_PROVIDER
EXPORT_PROVIDER
DB_PATH
artifacts/
CORS_ORIGINS
``

Exact names must remain synchronized with the active backend configuration.

---

## 24. Non-reversible technical decisions

The following decisions define the submission architecture:

1. The canonical project schema is the source of truth.
2. The LoftPlan is the authoritative geometry plan.
3. KCL is generated deterministically by the backend.
4. Zoo Agent interprets bounded requests but does not author CAD.
5. The browser never receives Zoo credentials.
6. Generation and export artifacts are revision-linked.
7. Failed regeneration preserves the last-known-good model.
8. KCL 2.0 solid-body geometry is the active construction.
9. Surface-shell workarounds are not the active architecture.
10. STL and KCL are the supported submission outputs.
11. STEP is not implemented for this submission.
12. Coaxial and offset are the supported connection modes.
13. Cloudflare Pages hosts the frontend.
14. Render hosts the backend.
15. SQLite provides project persistence.

---

## 25. Submission architecture summary

InterfaceForge is implemented as a guided, revision-safe adapter-generation workflow.

Its key technical characteristics are:

* reviewed 2D profile input;
* explicit calibration;
* canonical project data;
* deterministic LoftPlan generation;
* current KCL 2.0 solid-body compilation;
* Zoo Engine execution;
* bounded Zoo Agent revisions;
* model and artifact lineage;
* verified STL output;
* KCL download;
* last-known-good preservation;
* Cloudflare frontend deployment;
* Render backend deployment.

The submission intentionally prioritizes a clear, reliable adapter workflow over unsupported breadth.
