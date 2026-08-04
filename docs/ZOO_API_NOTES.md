# Zoo API Notes

**Status:** Active submission evidence record
**Last reviewed:** 2026-08-04

## Active boundary

- Zoo Engine is the authoritative CAD executor for deterministic KCL 2.0.
- Zoo Agent proposes bounded parameter changes only; the server validates/recalculates and explicit confirmation is required.
- Active outputs are STL and KCL. STEP is not an implemented submission output.
- Angle-based connections and unsupported profile topology are outside submission scope.
- Credentials remain backend-only. Mock providers are explicit offline/test providers.

## Classified findings

| Classification | Finding | Evidence/status |
|---|---|---|
| Verified live behavior | Prior credentialed Zoo Agent integration completed successfully, including bounded proposal and confirmation/rejection flow. | Prior project evidence; retained as historical live success. |
| Transient/inconclusive | 17 of 18 Agent calls timed out or closed during the 2026-08-04 adversarial audit. | Latest audit; not classified as a Zoo bug. |
| Verified live behavior | Prior project evidence verified STL export. | No fresh STL conversion result was obtained in the latest Engine audit. |
| Transient/inconclusive | Direct live Engine audit timed out before fresh STL conversion. | Latest audit; live Engine matrix remains unproven. |
| InterfaceForge defect | A live Engine timeout propagated as `asyncio.TimeoutError` instead of the intended failed-job envelope. | Provider/orchestration handling issue, not a confirmed Zoo defect. |
| Resolved InterfaceForge defect | Deprecated KCL/sketch emission was replaced by current KCL 2.0 solid-body syntax. | Current compiler fixture evidence. |
| Offline-only evidence | Local KCL compilation, geometry, mock providers, and regression tests. | Does not prove Zoo provider execution. |

## Security and evidence rules

Never commit tokens, authorization headers, private IDs, or raw provider logs. Authenticated REST reachability proves only authentication/reachability, not geometry or export correctness. Do not claim Agent reliability, live Engine completeness, manufacturing readiness, STEP, or angle support from offline or partial live evidence.
