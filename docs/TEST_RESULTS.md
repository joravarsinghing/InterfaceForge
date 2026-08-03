# InterfaceForge - Submission Test Results

**Status:** Submission documentation and cleanup update
**Date:** 2026-08-03
**Commit:** `c07b178`
**Scope:** Submission documentation and cleanup update reflecting the current verified product state.

## Current verified submission evidence

The current verified submission state records:

- **KCL 2.0 solid-body generation:** PASSED. Generated KCL uses current KCL 2.0 standards and produces valid solid-body geometry.
- **Deprecated-KCL geometry issue:** RESOLVED. The prior failure was caused by deprecated syntax in generated KCL.
- **STL export:** PASSED and verified.
- **Approved arbitrary traced-profile generation:** PASSED. Custom `traced_closed` profiles generate final adapters through the supported KCL/STL path.
- **STEP export:** NOT IMPLEMENTED; no STEP test or export evidence is claimed.
- **Limited-angle mode:** NOT SUPPORTED; no limited-angle test evidence is claimed.

The product-state statements above reflect the current verified submission truth; the rerun results below are recorded separately.

## Checks rerun for this update

- **Backend full suite:** 415 tests collected; 345 passed, 65 failed, and 2 warnings in 705.75 seconds. The failures span stale historical workflow/export/angle/surface-shell expectations and current geometry/provider integration mismatches; no full-suite pass is claimed.
- **Frontend full suite with restored baseline tests:** 126 tests across 39 files; 121 passed, 5 failed, 0 pending.
- **Focused Agent checks:** 4 backend tests passed (`test_secret_redaction`, length, outlet offset, and wall-thickness proposal cases); 17 tests were deselected.
- **Focused traced-profile checks:** 7 frontend `TracedProfile.test.tsx` tests passed. The restored backend traced-profile selection ran 4 tests: 1 passed and 3 failed in legacy promotion expectations.
## Remaining evidence boundaries

- Live Zoo Agent chat-revision execution was credential-tested and **PASSED**. Verified coverage included bounded revision proposals, explicit confirm/reject flow, and preservation of unapplied rejected proposals.
- No claim is made for STEP export, live export beyond the verified STL result, or manufacturing readiness.
