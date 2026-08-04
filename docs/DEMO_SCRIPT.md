# InterfaceForge Demo Script

**Status:** Draft final recording script
**Target duration:** 60 seconds maximum
**Evidence rule:** Show only behavior available in the current build. Do not imply live Zoo success if the selected provider is unavailable.

## Timeline

| Time | Screen/action | Voiceover or caption |
|---|---|---|
| 0-06s | Homepage and dust-adapter use case | "InterfaceForge turns two reviewed 2D interface profiles into a parametric dust-extraction adapter." |
| 06-14s | Upload `samples/valid_circle.png` as Interface A | "Start with a clean front-facing profile." |
| 14-22s | Select two points and enter `50 mm`; confirm; review and approve | "Two-point calibration uses one known real-world distance, followed by explicit profile approval." |
| 22-30s | Upload `samples/valid_rounded_rectangle.png` as Interface B; calibrate with `50 mm`; approve | "Interface B stays locked until Interface A is approved." |
| 30-39s | Configure fit-over, coaxial, length `40 mm`, wall `2.4 mm`, clearances `0.3/0.1 mm`; validate | "The connection is bounded to coaxial or X/Y offset settings." |
| 39-47s | Explicitly generate; show generation status/result | "The canonical LoftPlan drives deterministic KCL 2.0 and Zoo Engine execution when live credentials are available." |
| 47-54s | Agent panel; enter `Make the adapter 10 mm longer.`; show proposal; confirm | "Zoo Agent proposes a bounded change. Confirmation marks the model stale; regeneration is explicit." |
| 54-60s | Show current STL/KCL downloads and result | "Download revision-current STL and KCL. These are user-reviewed engineering candidates." |

## Scope caption

Show briefly or include in the description: angle-based connections, internal cavities, STEP export, and certified manufacturing readiness are not part of this submission.

## Recording notes

Use the supplied sample images and values above. If live Zoo transport is unreliable, record the deterministic Mock workflow and label it clearly as offline/mock evidence; do not present it as live Zoo proof. Demo video: https://youtu.be/z8Ge7i2QtFM (unlisted, accessible to anyone with the link; not public).
