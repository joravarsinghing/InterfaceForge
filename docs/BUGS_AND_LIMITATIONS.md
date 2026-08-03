# InterfaceForge - Bugs and Limitations

**Document Status:** Active submission record
**Project:** InterfaceForge (Zoo API Makeathon 2026)
**Last reviewed:** 2026-08-03

## Current verified state

- Generated KCL uses current KCL 2.0 solid-body standards and produces valid solid-body geometry.
- The deprecated-KCL geometry issue is resolved. It was caused by deprecated sketch-v1 syntax in the generated artifact, not by an established solid-subtraction limitation.
- Solid subtraction is part of the working solid-body generation path; it is not currently classified as unproven or blocked.
- STL export works and has been verified.
- STEP export is not implemented and is out of scope for this submission.
- Limited-angle connection mode is not supported.
- Live Zoo Agent execution has not been credential-tested for this submission and remains unproven.

## Genuine current limitations

1. **Preferred input:** Clean, front-facing, filled 2D cross-section images are the reliable submission input. Perspective distortion, poor lighting, and annotation-heavy drawings can reduce tracing quality.
2. **Dimensioned drawings:** Dimensioned engineering drawings are experimental/manual-review inputs. Annotation masking may reduce false edges but does not guarantee a correct trace. The profile must be reviewed and approved by the user.
3. **Scale confirmation:** A known measurement is used for calibration, but scale and detected geometry require explicit user confirmation. Perspective distortion is not automatically corrected.
4. **Profile scope:** Final adapter generation is limited to the supported circle, rectangle, rounded-rectangle, and approved traced-profile paths. Arbitrary geometry may require manual review or may be rejected.
5. **Manufacturing scope:** Threads, mounting holes, countersinks, dovetails, undercuts, multi-depth interfaces, and certified manufacturing readiness are outside the current scope.
6. **Output status:** Generated adapters are user-reviewed engineering candidates and require inspection before manufacturing.

## Resolved issues retained for context

### Deprecated KCL geometry syntax - resolved

The prior geometry failure was traced to deprecated sketch-v1 commands emitted in a KCL 2.0 artifact. The compiler now emits current KCL 2.0 solid-body syntax. The failure is closed and must not be described as a current Boolean or solid-generation blocker.

## Evidence boundaries

Offline tests and current verified submission checks must not be presented as credentialed live-provider proof. In particular, live Zoo Agent execution remains unproven until it is run with valid credentials. No STEP evidence is retained because STEP is not implemented for this submission.
