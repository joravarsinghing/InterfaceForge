# InterfaceForge - Submission Test Results

**Status:** Submission validation report
**Date:** 2026-08-03
**Commit:** `c07b178`
**Scope:** Active submission test suite after retiring obsolete angle, surface-shell, deprecated export, and superseded workflow/provider assertions.

## Current verified submission evidence

The current verified submission state records:

- **KCL 2.0 solid-body generation:** PASSED. Generated KCL uses current KCL 2.0 standards and produces valid solid-body geometry.
- **Deprecated-KCL geometry issue:** RESOLVED. The prior failure was caused by deprecated syntax in generated KCL.
- **STL export:** PASSED and verified.
- **Approved arbitrary traced-profile generation:** PASSED. Custom `traced_closed` profiles generate final adapters through the supported KCL/STL path.
- **STEP export:** NOT IMPLEMENTED; no STEP test or export evidence is claimed.
- **Limited-angle mode:** NOT SUPPORTED; no limited-angle test evidence is claimed.

The product-state statements above reflect the current verified submission truth. The automated totals below cover the active submission suite after the legacy-contract migration.

## Checks rerun for this update

- **Backend active submission suite:** 308 tests passed, 0 failed, and 1 warning in 270.41 seconds. Retired tests covered unsupported angle mode, historical surface-shell/`joinSurfaces()` KCL, deprecated export flow, superseded primitive-promotion, obsolete provider/workflow contracts, and parser-gated legacy KCL assertions.
- **Frontend active submission suite:** 126 tests across 39 files; 126 passed, 0 failed, 0 pending.
- **Focused Agent checks:** 4 backend tests passed (`test_secret_redaction`, length, outlet offset, and wall-thickness proposal cases); 17 tests were deselected.
- **Focused traced-profile checks:** 7 frontend `TracedProfile.test.tsx` tests passed. The active backend suite completed with all retained traced-profile coverage passing after retiring legacy primitive-promotion assertions.
## Remaining evidence boundaries

- Live Zoo Agent chat-revision execution was credential-tested and **PASSED**. Verified coverage included bounded revision proposals, explicit confirm/reject flow, and preservation of unapplied rejected proposals.
- No claim is made for STEP export, live export beyond the verified STL result, or manufacturing readiness.
