# Geometry Rules

## Input, coordinates, and units

Inputs are clean, filled, front-facing or orthographic 2D images. OpenCV produces one approved closed outer profile. Trace coordinates are normalized into `canonical_profile_v1`, then calibrated into millimetres using two selected points and one positive known distance. Calibration is uniform scale only; it does not correct perspective, camera tilt, or lens distortion. KCL and all connection/manufacturing values use millimetres.

## Profile preparation

Contours are cleaned by rejecting non-finite points, removing adjacent points closer than `1e-6`, removing a duplicated closing point, requiring at least three distinct points, rejecting self-intersection, and rejecting near-zero signed area (`<= 1e-8`). Profiles are centered by subtracting the arithmetic mean of their points and normalized to counter-clockwise winding (positive signed area).

Closed contours are resampled by perimeter distance. The target point count is `min(256, max(32, estimated))`, where `estimated` is the larger input point count or `ceil(2*pi*max_edge/0.2 mm)`. This preserves a minimum of 32 and caps complexity at 256. Correspondence uses equal point counts, same winding, cyclic seam shifts, reversal candidates, tangent/displacement/seam cost, and a large crossing penalty. Crossing or unavailable correspondence rejects the loft.

## Supported profiles and fit intent

Active final profiles are `circle`, `rectangle`, `rounded_rectangle`, and approved `traced_closed`. `custom_closed` is compatibility-only. Each interface has `fit-over` or `fit-inside` intent:

- `fit-over`: target -> outward clearance -> outward wall offset. The clearance boundary is the inner passage and the outer boundary is one wall thickness farther outward.
- `fit-inside`: target -> inward clearance. That boundary is the outer boundary and the inner passage is one wall thickness farther inward.

The outer loop must be simple, counter-clockwise, positive-area, and larger than the inner loop. Inner/outer loops may not cross; the inner area must be strictly smaller. Wall midpoint deviation is checked against `max(2.0, 1.25 * wall_thickness)` mm, and local inner clearance must remain at least `0.1 mm`.

Uploaded internal cavities, holes, branches, assemblies, threads, mounting features, dovetails, undercuts, and curved centerlines are excluded from submission geometry.

## Connection and manufacturing rules

- `coaxial`: X/Y offsets must both equal zero; profiles remain parallel.
- `offset`: Interface B is displaced by `offset_x_mm` and `offset_y_mm` on a parallel plane.
- Angle-based connections are unsupported. Legacy `angle_deg` remains in compatibility schemas but must be zero and is not an active control.

`length_mm` must be finite and greater than zero. Length below `10 mm` produces warning `IF-CONN-W001`; length above `300 mm` produces `IF-CONN-W002`. Each extension must be finite and at least `0 mm`; values above `300 mm` produce `IF-CONN-W005`. Extensions add straight sections aligned with their respective approved profiles.

Wall thickness must be finite and positive. Values below `0.4 mm` block with `IF-MFG-002`; below `1.2 mm` warns `IF-MFG-W001`; above `15 mm` warns `IF-MFG-W002`. Clearance must be finite and within `[0.0, 5.0] mm`, otherwise `IF-MFG-003`; below `0.1 mm` warns `IF-MFG-W003`.

The offset-to-length ratio is `hypot(offset_x_mm, offset_y_mm) / length_mm`. Above `1.0` warns `IF-CONN-W004`; above `1.5` blocks with `IF-CONN-006`. Coaxial non-zero offsets block with `IF-CONN-007`. Missing approvals use `IF-CONN-001`; unsupported mode uses `IF-CONN-002`; invalid length uses `IF-CONN-003`; invalid extensions use `IF-CONN-008`.

Additional fit failures use `IF-MFG-004` for a closed passage, `IF-MFG-005` for a collapsed fitted boundary, and `IF-MFG-006` for an unsupported rounded-rectangle radius. Missing calibrated trace data uses `IF-CAL-001`.

## LoftPlan and KCL construction

The persisted `LoftPlan` records normalized/resampled `outer_a`, `outer_b`, `inner_a`, `inner_b`, target/mating loops, fit modes, clearances, wall thickness, correspondence diagnostics, geometry hash, and ordered sections. Sections are ordered from Interface A at `z=0`, through optional Interface A extension and the transition, to Interface B and optional Interface B extension. The transition uses the configured length and X/Y displacement.

The compiler emits KCL 2.0 solid-body syntax: outer closed sketches are lofted into `outerSolid`; inner closed sketches are lofted into `innerCutter`; `adapterModel = subtract([outerSolid], tools = [innerCutter])`. The same LoftPlan drives preview, deterministic KCL, mock geometry checks, and Zoo Engine execution.

## Output and safety

Zoo Engine is the authoritative CAD executor. STL and KCL are the active submission exports. STEP fields/providers remain compatibility-only and are not claimed as implemented. Outputs are user-reviewed engineering candidates, not certified manufacturing-ready products. Any upstream change makes the model and exports stale; failed generation preserves the last-known-good revision.
