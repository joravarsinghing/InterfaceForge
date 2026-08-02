# InterfaceForge Agent Handoff

Date: 2026-08-02
Repository: C:\Users\jvsin\Documents\GitHub\InterfaceForge
Status: Surface-shell KCL path restored; local focused validation passes; full live Agentic matrix remains unproven.

## Executive summary

InterfaceForge originally generated a hollow adapter with two solid lofts and a Boolean subtraction:

```kcl
outerSolid = loft([...])
innerVoid = loft([...])
adapterModel = subtract(outerSolid, tools = [innerVoid])
```

Live Zoo KCL execution repeatedly returned:

```text
The Zoo engine cannot handle this 3D subtraction yet. Please report this as an issue
```

A deterministic through-cutter experiment was implemented with a 0.1 mm Z-only extension and exact XY endpoint contours. The downloaded KCL proved that the cutter passed beyond both outer end planes, but Zoo still rejected `subtract()`. This established that the blocker is an engine capability limitation, not merely coincident end caps.

The compiler was switched to the earlier surface-shell construction:

```kcl
outerSurface = loft([...], bodyType = "surface")
innerSurface = loft([...], bodyType = "surface")
bottomRim = loft([outer_end, inner_rim_bottom], bodyType = "surface")
topRim = loft([outer_end, inner_rim_top], bodyType = "surface")
adapterModel = joinSurfaces([outerSurface, innerSurface, bottomRim, topRim])
```

A later attempt split the outer and inner lofts into eight surface bodies to avoid extension-boundary preview seams. That made the Zoo Agentic preview worse: the final KCL displayed exploded horizontal surface layers. The problematic KCL contained:

```kcl
outerExtensionA = loft([...])
innerExtensionA = loft([...])
outerSurface = loft([...])
innerSurface = loft([...])
outerExtensionB = loft([...])
innerExtensionB = loft([...])
adapterModel = joinSurfaces([
  outerExtensionA,
  outerSurface,
  innerExtensionA,
  innerSurface,
  outerExtensionB,
  innerExtensionB,
  bottomRim,
  topRim
])
```

That split has now been reverted. The active compiler again emits exactly four joined surfaces. Fresh KCL must be regenerated before recording; old downloaded KCL files still contain the eight-surface regression.

## Current implementation changes

### `backend/app/services/kcl_compiler.py`

- Uses lowerCamelCase identifiers for Zoo compatibility, including `sketchOuter0`, `outerSurface`, and `adapterModel`.
- Emits extension values in KCL metadata:
  - `extensionAMm`
  - `extensionBMm`
- Validates extension values as finite numbers.
- Emits one outer surface loft and one inner surface loft across the persisted LoftPlan sections.
- Emits explicit annular bottom and top rim surfaces using a 0.001 mm duplicate rim-plane offset.
- Joins exactly four surface bodies with `joinSurfaces()`.
- Does not emit `subtract()` or `shell()`.
- Does not modify canonical contour XY coordinates.
- Does not modify preview or STL geometry-generation code.

The final construction is intentionally small because the Zoo Agentic preview did not reliably consolidate a larger list of surface bodies.

### `backend/app/services/agent_service.py`

On confirmed Agent changes:

1. The server validates the allowlisted fields.
2. The canonical connection/manufacturing configuration is updated.
3. The derived `LoftPlan` is explicitly invalidated.
4. A fresh `LoftPlan` is rebuilt from canonical data.
5. KCL is recompiled before generation starts.
6. A failed compile returns a structured API error instead of starting generation.
7. Generation service reloads the persisted canonical project and compiles the authoritative KCL again.
8. Existing last-known-good model preservation remains in `GenerationJobService`.

The Agent provider remains bounded. It may propose only these seven fields:

- `connection.length_mm`
- `connection.offset_x_mm`
- `connection.offset_y_mm`
- `connection.angle_deg`
- `manufacturing.wall_thickness_mm`
- `manufacturing.clearance_a_mm`
- `manufacturing.clearance_b_mm`

The Agent does not author KCL or geometry code.

## Root-cause findings

### Solid Boolean failure

The file `interfaceforge_adapter_rev1 (6).kcl` contained a through-cutter:

```kcl
inner_void = loft([
  sketchInnerThroughStart,
  sketchInner0,
  ...,
  sketchInnerThroughEnd
])
adapterModel = subtract(outerSolid, tools = [innerVoid])
```

The cutter began at `z = -0.1` and ended beyond the outer solid. Zoo still returned the subtraction capability error. Therefore larger epsilon values are not the primary fix.

### Surface preview regression

The file `interfaceforge_adapter_rev2 (1).kcl` that produced the exploded screenshot had:

- `transitionLengthMm = 50.0`
- `extensionAMm = 12.0`
- `extensionBMm = 12.0`
- eight LoftPlan sections from `z = 0` to `z = 74`
- eight surface bodies passed to `joinSurfaces()`
- an additional `hidden001 = hide(innerExtensionA)` command at the end

The screenshot matched the eight independent surface bodies being displayed separately. This was a compiler graph regression, not an OBS recording issue.

### STL versus KCL preview

The supplied STL `interfaceforge_adapter_rev2 (1).stl` was validated locally as:

- valid STL;
- 2,976 facets;
- closed-manifold validation passed;
- bounding box approximately `70.029 x 65.249 x 70.0 mm`;
- Z range exactly `0.0 -> 70.0 mm`.

The STL export path can therefore produce clean manifold output from the same general surface construction even when the Zoo KCL Agentic preview displays surface seams or separate bodies. The KCL preview and STL export are not equivalent visual evidence.

## Tests and validation completed

Focused compiler tests after restoring the four-surface graph:

```text
7 passed, 1 warning
```

Focused Agent and lineage tests:

```text
5 passed, 1 warning
```

Additional recent focused run:

```text
3 passed, 1 warning
```

Validation commands used:

```powershell
$env:PYTHONPATH='.'; ..\venv314\Scripts\python.exe -m pytest tests/test_kcl_compiler.py::test_kcl_surface_shell_preserves_open_rims_for_primitive_profiles tests/test_kcl_compiler.py::test_kcl_surface_shell_handles_extensions_without_coplanar_rims tests/test_agent_revision_geometry_propagation.py::test_revision_to_kcl_propagation -q

$env:PYTHONPATH='.'; ..\venv314\Scripts\python.exe -m py_compile app/services/kcl_compiler.py app/services/agent_service.py tests/test_kcl_compiler.py tests/test_agent_revision_geometry_propagation.py

git diff --check
```

A previous live Zoo export harness run against the surface path failed STL validation with:

```text
Zoo KCL STL export failed geometry validation: STL topology is not a closed manifold.
```

This means the full live surface-shell export and Agentic revision matrix is not proven. Do not claim live PASS from the local parser or mock execution.

A previous live export run against the solid path produced valid STL and STEP for four basic cases, but that does not prove the rejected solid Boolean path is suitable for the current Agentic workflow.

## Documentation changes

- `README.md` now briefly states that Zoo KCL rejects `subtract()` between loft-generated solid bodies and that the active path uses surface lofts plus annular rims.
- `docs/BUGS_AND_LIMITATIONS.md` records the Zoo subtraction limitation.
- `docs/ZOO_API_NOTES.md` records the subtraction limitation and lowerCamelCase identifier compatibility.

## Current worktree

Expected modified files:

- `README.md`
- `backend/app/services/agent_service.py`
- `backend/app/services/kcl_compiler.py`
- `backend/tests/test_agent_revision_geometry_propagation.py`
- `backend/tests/test_kcl_compiler.py`
- `docs/BUGS_AND_LIMITATIONS.md`
- `docs/ZOO_API_NOTES.md`

No commit, push, branch creation, or pull request has been performed.

## Safe next steps

1. Regenerate a fresh KCL from the current compiler; do not reuse an old downloaded KCL.
2. Confirm the final commands contain exactly one `outerSurface`, one `innerSurface`, `bottomRim`, `topRim`, and one four-item `joinSurfaces()` call.
3. Confirm the output does not contain `outerExtensionA`, `innerExtensionA`, `outerExtensionB`, or `innerExtensionB`.
4. Run the Agent confirmation flow with a bounded length change and inspect the regenerated KCL hash/artifact.
5. Run live Zoo execution for the exact custom-profile, offset, two-extension case.
6. Validate live preview, STL, and STEP independently.
7. Preserve the prior current model if the live surface execution or export fails.

## Do not do

- Do not restore `subtract()` as the primary path unless Zoo confirms support.
- Do not reintroduce the eight-surface `joinSurfaces()` graph without a live Agentic test proving it consolidates correctly.
- Do not silently use mock STL or local OBJ output as live proof.
- Do not let Zoo Agent write arbitrary KCL or geometry.
- Do not claim the KCL preview is clean solely because an STL export is valid.
