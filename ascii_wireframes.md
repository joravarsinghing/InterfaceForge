# InterfaceForge — ASCII Wireframes

**Document status:** Draft v0.1  
**Source documents:** `InterfaceForge_PRD_v0.1.md`, `user_flow.md`  
**Purpose:** Define page regions, responsibilities, navigation, responsive behavior, and accessibility before visual styling.

---

## 1. Global Application Shell

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Skip to main content                                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ InterfaceForge logo     Project status     Help     Service status indicator │
├──────────────────────────────────────────────────────────────────────────────┤
│ Interface A  Interface B  Connection    Generate     Review & Export          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Main page content                                                            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ Privacy note | API/service status | GitHub | Makeathon information           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **Header**
  - Product identity
  - Current project status
  - Help access
  - Remote-service availability
  - Shows progress through the guided workflow
- **Main content**
  - Contains one focused task per page
- **Footer**
  - Privacy and data handling summary
  - API/service status
  - Public repository link when available

### Navigation

- Logo → Landing page
- Help → Contextual guidance panel
- Service status → Service-status details

### Responsive

- Header actions collapse into a compact menu.
- Main task remains above secondary help content.
- MVP remains desktop-first; narrow layouts must remain usable but are not optimized for advanced editing.

### Accessibility

- Skip link precedes the header.
- Header and workflow navigation have accessible names.
- Service-status changes use a polite live region.
- Main page contains one primary H1.

---

# 2. WF-001 — Landing / Start Project

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge                                      Help     Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    Two interfaces in. One adapter out.                       │
│                                                                              │
│  Upload or sketch two physical interfaces, confirm what the system sees,    │
│  choose how they should connect, and generate a parametric adapter.          │
│                                                                              │
│                         [ Start New Project ]                                │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ How it works                                                                 │
│                                                                              │
│  1. Capture Interface A     2. Capture Interface B                           │
│  3. Choose connection      4. Generate model                                │
│  5. Review and export                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Optional examples                                                            │
│                                                                              │
│ [ Vacuum hose adapter ]     [ Camera mounting adapter ]                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Privacy note | GitHub | Makeathon information                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **Hero region**
  - States the product promise
  - Starts the project
- **How-it-works region**
  - Sets expectations
  - Makes the workflow understandable before upload
- **Example region**
  - Optional onboarding through known-good examples

### Navigation

- Start New Project → Interface A upload
- Vacuum hose adapter → Sample project or sample walkthrough
- Camera mounting adapter → Sample project or sample walkthrough
- Help → Product explanation

### Responsive

- Hero CTA remains visible without scrolling on common laptop sizes.
- Example cards stack vertically on narrow screens.
- Workflow stages stack into a numbered list.

### Accessibility

- Hero heading is the single H1.
- CTA has an explicit label: “Start new adapter project.”
- Example cards identify that they are examples, not saved user projects.
- No auto-playing media.

---

# 3. WF-002 — Interface Upload

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge     Project: Untitled                  Help   Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│ [1 Interface A]   2 Interface B   3 Connection   4 Generate   5 Review      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Interface A — Upload an image or sketch                                     │
│                                                                              │
│ Capture the face that must connect to the second product.                    │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Upload region                         │ Image guidance                       │
│                                       │                                      │
│ ┌───────────────────────────────────┐ │ GOOD                                 │
│ │                                   │ │ - Camera directly facing interface   │
│ │ Drop image here                   │ │ - Full outline visible               │
│ │ or                                │ │ - Good contrast                      │
│ │ [ Choose file ]                   │ │ - Minimal reflection                 │
│ │                                   │ │                                      │
│ └───────────────────────────────────┘ │ BAD                                  │
│                                       │ - Perspective angle                  │
│ Supported formats: TBD                │ - Cropped edge                       │
│ Maximum size: TBD                     │ - Heavy shadow                       │
│                                       │ - No measurable reference            │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ [Back]                                                     [Continue disabled]│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Selected-file state

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Interface A — Confirm source image                                           │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Image preview                         │ Checklist                            │
│                                       │                                      │
│ ┌───────────────────────────────────┐ │ [✓] Full interface visible           │
│ │                                   │ │ [✓] Camera approximately square-on   │
│ │          Uploaded image           │ │ [ ] At least 2 dimensions available  │
│ │                                   │ │                                      │
│ └───────────────────────────────────┘ │ File: interface-a.jpg                │
│                                       │ Size: 2.4 MB                         │
│ [Replace image]                       │                                      │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ [Back]                                        [ Use This Image and Analyze ] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **Upload region**
  - File selection
  - Drag-and-drop
  - Preview
- **Guidance region**
  - Teaches correct capture
  - Prevents avoidable failure
- **Footer actions**
  - Back
  - Confirm and analyze

### Navigation

- Choose file → System file picker
- Replace image → Return to empty upload state
- Use This Image and Analyze → Processing state

### Responsive

- Guidance moves below upload region.
- File preview remains large enough to inspect.
- Continue action remains sticky near the bottom on narrow screens.

### Accessibility

- File picker is keyboard accessible.
- Drag-and-drop is not the only upload method.
- Guidance examples have textual descriptions.
- Upload progress and result are announced.
- Error text is linked to the upload control.

---

# 4. WF-003 — Processing / Analysis

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge     Project: Untitled                  Help   Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│ [1 Interface A]   2 Interface B   3 Connection   4 Generate   5 Review      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Analyzing Interface A                                                       │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Uploaded image thumbnail                                                 │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ [✓] Upload complete                                                         │
│ [●] Detecting profile                                                       │
│ [ ] Reading dimensions                                                      │
│ [ ] Creating editable profile                                               │
│ [ ] Running validation                                                      │
│                                                                              │
│ This usually takes a short while. Your image and project inputs are safe.   │
│                                                                              │
│ [ Cancel Analysis ]                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Shows transparent staged progress
- Reassures user that work is preserved
- Allows cancellation if supported

### Navigation

- Cancel Analysis → Return to upload confirmation
- Successful analysis → Profile review
- Failed analysis → Poor-image recovery or service-error state

### Responsive

- Progress list remains vertical.
- Thumbnail may collapse to a smaller preview.

### Accessibility

- Progress stage is announced through a polite live region.
- Spinner is supplementary, not the only progress indicator.
- Cancel button states consequences clearly.

---

# 5. WF-004 — Profile Review and Approval

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge     Project: Untitled                  Help   Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│ [1 Interface A]   2 Interface B   3 Connection   4 Generate   5 Review      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Review Interface A                                      Status: Not approved │
│ Confirm the detected profile and correct any uncertain dimensions.          │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Source image                  │ Clean editable profile                       │
│                               │                                              │
│ ┌───────────────────────────┐ │ ┌──────────────────────────────────────────┐ │
│ │                           │ │ │               52.0 mm                    │ │
│ │      Uploaded image       │ │ │         ┌────────────────┐               │ │
│ │                           │ │ │         │                │               │ │
│ └───────────────────────────┘ │ │         │                │               │ │
│ [Zoom -] [Reset] [Zoom +]     │ │         └────────────────┘               │ │
│                               │ │               34.0 mm                    │ │
│                               │ └──────────────────────────────────────────┘ │
│                               │ [Zoom -] [Fit] [Zoom +]                     │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ Detected profile: [ Rounded rectangle ▼ ]                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Dimensions                                                                  │
│                                                                              │
│ Name               Value       Source             Confidence     Action      │
│ Width              [52.0 mm]   User entered       High           Edit        │
│ Height             [34.0 mm]   Image extracted    Medium         Edit        │
│ Corner radius      [ 4.0 mm]   System inferred    Low            Edit        │
│ Wall/interface ID  [   —   ]   Unresolved         —              Required    │
│                                                                              │
│ Legend: User entered | Extracted | Inferred | Unresolved                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ Validation                                                                  │
│ ⚠ One critical dimension is unresolved. Approval is blocked.                │
│ [Upload Better Image]                                  [Update Profile]      │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Back]                                                 [Approve disabled]    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Approved state

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Review Interface A                                          Status: Approved │
│                                                                              │
│ All critical values are resolved.                                            │
│ [Edit Again]                                       [Continue to Interface B] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **Source image**
  - Visual reference
- **SVG profile**
  - Clean interpreted geometry
  - Reflects updates live
- **Profile selector**
  - Allows correction of detected shape family
- **Dimension table**
  - Source, confidence, value, editability
- **Validation**
  - Blocks approval when critical data is missing
- **Approval actions**
  - Explicit user confirmation gate

### Navigation

- Upload Better Image → Interface upload
- Update Profile → Recalculate and validate current SVG
- Approve Interface → Lock current interface
- Continue to Interface B → Interface B upload
- Edit Again → Reopen profile

### Responsive

- Source image and SVG stack vertically.
- Dimension table becomes labeled cards on narrow screens.
- Approval action remains visible after validation passes.

### Accessibility

- Every SVG dimension has a corresponding form field.
- Provenance uses text/icon labels, not only color.
- Validation summary links to affected fields.
- Zoom controls are keyboard accessible.
- Approval state is announced.

---

# 6. WF-005 — Poor Image Recovery

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Interface A could not be interpreted reliably                               │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Rejected image                │ What went wrong                              │
│                               │                                              │
│ ┌───────────────────────────┐ │ Perspective angle is too high.              │
│ │        Uploaded image     │ │ The opening appears distorted, so scale     │
│ │       [problem marker]    │ │ and profile dimensions cannot be trusted.   │
│ └───────────────────────────┘ │                                              │
│                               │ How to fix it                                │
│                               │ 1. Face the opening directly                 │
│                               │ 2. Keep the entire contour visible           │
│                               │ 3. Add two measured dimensions               │
│                               │                                              │
│                               │ [View good example]                          │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ Error ID: IF-IMAGE-002                                                    │
│                                                                              │
│ [Exit Project]                         [Upload Sketch] [Upload Another Image] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Explains the exact rejection reason
- Preserves trust by refusing unreliable inference
- Provides direct recovery actions

### Navigation

- Upload Another Image → Upload flow
- Upload Sketch → Upload flow with sketch guidance
- Exit Project → Exit flow
- View good example → Guidance modal/panel

### Responsive

- Explanation moves below rejected preview.
- Recovery actions stack but preserve recommended action prominence.

### Accessibility

- Problem marker has equivalent text.
- Error is announced when page opens.
- Recovery options are explicit and keyboard accessible.

---

# 7. WF-006 — Connection Mode Selection

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge     Project: Vacuum Adapter            Help   Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✓ Interface A   ✓ Interface B   [3 Connection]   4 Generate   5 Review      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Choose how the interfaces connect                                           │
│ Both profiles are approved. Select the relationship between them.            │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐ │
│ │ COAXIAL               │ │ OFFSET                │ │ ANGLED                │ │
│ │                       │ │                       │ │                       │ │
│ │  ○──────────────○     │ │  ○─────────────○      │ │  ○────────────╱○      │ │
│ │                       │ │      shifted          │ │      rotated          │ │
│ │ Same center axis      │ │ Parallel, different  │ │ Limited relative      │ │
│ │                       │ │ center positions      │ │ angle                 │ │
│ │ [Select]              │ │ [Select]              │ │ [Select]              │ │
│ └───────────────────────┘ └───────────────────────┘ └───────────────────────┘ │
├──────────────────────────────────────────────────────────────────────────────┤
│ Interface summary                                                           │
│ A: Circle, 34.5 mm OD, approved                                             │
│ B: Circle, 52.0 mm ID, approved                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Edit Interface A] [Edit Interface B]                         [Back]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Explains coaxial, offset, and angled modes visually and textually
- Shows approved interface summary
- Allows return to profile correction

### Navigation

- Select mode → Connection configuration for selected mode
- Edit Interface A/B → Reopen approved interface
- Back → Interface B review

### Responsive

- Mode cards stack vertically.
- Interface summary remains visible before selection.

### Accessibility

- Each diagram includes a text explanation.
- Cards are selectable by keyboard.
- Selected mode uses text and control state, not only visual styling.

---

# 8. WF-007 — Connection Configuration

## Coaxial example

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Configure Coaxial Adapter                                                   │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Parameters                            │ Live visual guide                    │
│                                       │                                      │
│ Transition length                     │ Side view                            │
│ [ 90.0 ] mm                           │                                      │
│                                       │     Interface A      Interface B     │
│ Wall thickness                        │        ○───────────────○              │
│ [ 2.4 ] mm                            │           90.0 mm                     │
│                                       │                                      │
│ Fit at Interface A                    │ Section view                         │
│ [ Slip fit ▼ ]  Clearance [0.3] mm    │   ┌──────────────────────────────┐   │
│                                       │   │ outer wall / hollow passage  │   │
│ Fit at Interface B                    │   └──────────────────────────────┘   │
│ [ Snug fit ▼ ] Clearance [0.1] mm     │                                      │
│                                       │ Legend / dimensions                  │
│ Material preset                       │                                      │
│ [ PETG ▼ ]                            │                                      │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ Validation                                                                  │
│ ✓ Transition length is valid                                                │
│ ✓ Wall thickness meets current minimum                                      │
│ ⚠ Interface B fit may be tight for some FDM printers                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Back to Modes] [Edit Interface]                       [Generate Adapter]    │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Offset example

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Configure Offset Adapter                                                    │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Transition length  [110.0] mm         │ Live side/top guide                  │
│ X offset           [ 20.0] mm         │                                      │
│ Y offset           [  0.0] mm         │ A ○───────────────○ B                │
│ Wall thickness     [  2.4] mm         │         ↕ 20 mm offset               │
│ Clearances         [A 0.3] [B 0.1]    │                                      │
│                                       │ [Top] [Side]                         │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ ⚠ Offset-to-length ratio is near the supported limit.                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Angled example

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Configure Angled Adapter                                                    │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Transition length  [120.0] mm         │ Live side guide                      │
│ Angle              [ 25.0] degrees    │                                      │
│ X offset           [  0.0] mm         │ A ○────────────╲                     │
│ Y offset           [  0.0] mm         │                 ╲○ B                 │
│ Wall thickness     [  2.4] mm         │                 25°                  │
│                                       │                                      │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ ✓ Angle is within supported range                                           │
│ ⚠ Shorter lengths may cause self-intersection                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **Parameter panel**
  - Only mode-relevant controls
- **Live visual guide**
  - Explains geometric effect without requiring CAD knowledge
- **Validation panel**
  - Separates blocking errors from warnings
- **Footer actions**
  - Go back, edit inputs, or generate

### Navigation

- Back to Modes → Mode selection
- Edit Interface → Profile review
- Generate Adapter → Generation flow

### Responsive

- Parameter panel and live guide stack.
- Numeric inputs remain visible beside units.
- Main action remains sticky after valid configuration.

### Accessibility

- Sliders, if present, always pair with numeric input.
- Every diagram has text equivalent.
- Validation updates are announced only when status meaningfully changes.
- Units are programmatically associated with inputs.

---

# 9. WF-008 — Generation Progress

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Generating your adapter                                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ [✓] Validating approved profiles                                             │
│ [✓] Preparing parametric model                                               │
│ [●] Generating geometry through Zoo                                          │
│ [ ] Rendering preview                                                        │
│ [ ] Preparing export data                                                    │
│                                                                              │
│ Current stage: Building the hollow transition                                │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Progress / activity region                                               │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Your approved profiles and settings are preserved.                           │
│                                                                              │
│ [Cancel Generation]                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Shows staged progress
- Indicates data safety
- Provides cancellation or recovery

### Navigation

- Cancel Generation → Return to connection configuration
- Success → Result review
- Failure → Generation error recovery

### Responsive

- Stages remain a vertical list.
- Long technical details remain hidden behind optional disclosure.

### Accessibility

- Current stage announced through a live region.
- Do not repeatedly announce percentage updates.
- Cancellation has clear consequences.

---

# 10. WF-009 — Result Review

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ InterfaceForge     Project: Vacuum Adapter            Help   Service: Online │
├──────────────────────────────────────────────────────────────────────────────┤
│ ✓ Interface A   ✓ Interface B   ✓ Connection   ✓ Generate   [5 Review]      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Adapter generated successfully                              Model: Current   │
├──────────────────────────────────────────────┬───────────────────────────────┤
│ 3D preview                                   │ Design summary                │
│                                              │                               │
│ ┌──────────────────────────────────────────┐ │ Type: Hollow flow adapter     │
│ │                                          │ │ Mode: Offset                  │
│ │              3D model                    │ │ Length: 110 mm                │
│ │                                          │ │ Offset: X 20 / Y 0 mm         │
│ │                                          │ │ Wall: 2.4 mm                  │
│ └──────────────────────────────────────────┘ │ Fit A: 0.3 mm                 │
│ [Orbit] [Pan] [Zoom] [Fit]                  │ Fit B: 0.1 mm                 │
│                                              │ Volume: 42.8 cm³              │
│                                              │                               │
│                                              │ Assumptions                   │
│                                              │ - FDM process                 │
│                                              │ - PETG preset                 │
├──────────────────────────────────────────────┴───────────────────────────────┤
│ Warnings                                                                     │
│ ⚠ Interface B may require a tolerance test print.                            │
│ ✓ No critical geometry errors detected.                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Edit Interface] [Revise Parameters] [Describe a Change] [Export Files]      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- **3D preview**
  - Visual inspection
- **Design summary**
  - Textual equivalent of critical geometry
- **Warnings**
  - Manufacturability and confidence
- **Action row**
  - Edit, revise, describe, export

### Navigation

- Edit Interface → Reopen profile
- Revise Parameters → Structured revision
- Describe a Change → Natural-language revision
- Export Files → Export flow

### Responsive

- 3D preview appears before summary.
- Actions may become stacked, with Export retained as the primary action.
- Design summary remains visible without relying on the viewport.

### Accessibility

- Text summary provides nonvisual equivalent.
- Viewer controls have explicit labels.
- Warnings are grouped with heading.
- Model-current/stale status is announced.

---

# 11. WF-010 — Structured Parameter Revision

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Revise Adapter Parameters                                     Model: Current │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ Editable parameters                   │ Current model summary                │
│                                       │                                      │
│ Transition length [110.0] mm          │ Existing generated model             │
│ X offset          [ 20.0] mm          │ remains available until a new        │
│ Y offset          [  0.0] mm          │ generation succeeds.                 │
│ Angle             [  0.0] degrees     │                                      │
│ Wall thickness    [  2.4] mm          │                                      │
│ Clearance A       [  0.3] mm          │                                      │
│ Clearance B       [  0.1] mm          │                                      │
│                                       │                                      │
│ [Reset to current model values]       │                                      │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ Draft change summary                                                        │
│ Transition length: 110 → 130 mm                                              │
│ Model status after applying: Out of date until regeneration                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Cancel]                                      [Validate and Regenerate]       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Exposes only safe parameters
- Preserves last-known-good model
- Shows change summary before regeneration

### Navigation

- Cancel → Result review
- Reset → Restore last generated values
- Validate and Regenerate → Generation flow

### Responsive

- Current-model summary moves below inputs.
- Change summary remains visible before action.

### Accessibility

- Inputs include ranges and units.
- Change summary is textual.
- Reset requires confirmation when multiple fields changed.

---

# 12. WF-011 — Natural-Language Revision

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Describe a Change                                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ Explain what you want to change. InterfaceForge will propose safe parameter  │
│ updates before changing the model.                                           │
│                                                                              │
│ Examples                                                                     │
│ - Make the vacuum side 0.5 mm looser                                         │
│ - Increase the transition length by 20 mm                                    │
│ - Reduce the angle to 25 degrees                                              │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Make the vacuum side looser and extend the adapter by 20 mm              │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ [Cancel]                                                   [Interpret Change]│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Proposed-change state

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Proposed Changes                                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Parameter              Current              Proposed                         │
│ Clearance A            0.3 mm               0.8 mm                           │
│ Transition length      110 mm               130 mm                           │
│                                                                              │
│ Explanation                                                                  │
│ The Interface A fit will be loosened and the transition extended.            │
│                                                                              │
│ ⚠ The new clearance is above the recommended default but within limits.     │
│                                                                              │
│ [Edit Values Manually] [Cancel]                    [Approve and Regenerate]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Collects user intent in plain language
- Converts intent into a visible, reviewable proposal
- Never applies changes without approval

### Navigation

- Interpret Change → Processing/proposal
- Edit Values Manually → Structured revision
- Approve and Regenerate → Generation flow
- Cancel → Result review

### Responsive

- Prompt remains full width.
- Proposal table becomes stacked parameter cards.

### Accessibility

- Example prompts are real text, not placeholder-only.
- Proposal clearly announces old and new values.
- Focus moves to proposal heading after interpretation.
- Unsupported request errors provide a manual alternative.

---

# 13. WF-012 — Export

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Export Adapter                                              Model: Current   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Choose output formats                                                        │
│                                                                              │
│ [✓] STL                                                                      │
│     For 3D printing and slicer software                                      │
│                                                                              │
│     For further CAD editing and manufacturing workflows                      │
│                                                                              │
│ [✓] KCL                                                                      │
│     Parametric source used to generate this model                            │
│                                                                              │
│ Units: millimetres                                                           │
│ Model volume: 42.8 cm³                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Cancel]                                                     [Prepare Files] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Export-ready state

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Files ready                                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ STL   interfaceforge-vacuum-adapter.stl     [Download STL]                   │
│ KCL   interfaceforge-vacuum-adapter.kcl     [Download KCL]                   │
│                                                                              │
│ Inspect the STL in your slicer before printing.                              │
│                                                                              │
│ [Back to Model]                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Partial-failure state

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Export completed with one issue                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ STL   Ready                                      [Download STL]              │
│ KCL   Ready                                      [Download KCL]              │
│                                                                              │
│ Error ID: IF-EXPORT-003                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Explains format purpose
- Shows per-format progress and results
- Supports partial success

### Navigation

- Prepare Files → Export processing
- Download → Browser download
- Retry format → Retry only failed export
- Back to Model → Result review

### Responsive

- Format rows become cards.
- Download buttons remain directly associated with format.

### Accessibility

- Checkbox labels include format and purpose.
- Per-format success/failure announced.
- No forced multi-download pop-ups.
- Download button accessible name includes format.

---

# 14. WF-013 — Service Failure / Unauthorized Backend

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Generation service is temporarily unavailable                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ Your approved profiles and settings are safe in this session.                │
│                                                                              │
│ The Zoo generation service rejected the request or is currently unavailable. │
│ You do not need to enter any API credentials.                                │
│                                                                              │
│ What you can do                                                              │
│ - Retry generation                                                           │
│ - Continue editing parameters                                                │
│ - Return later                                                               │
│                                                                              │
│ Error ID: IF-SERVICE-ENGINE-001                                              │
│                                                                              │
│ [Continue Editing] [Return to Result] [Retry Generation]                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Converts credential/quota/outage failures into a user-safe service message
- Confirms project-data safety
- Offers meaningful alternatives

### Navigation

- Retry Generation → Retry failed stage
- Continue Editing → Connection or revision page
- Return to Result → Last-known-good model, if one exists

### Responsive

- Actions stack, with Retry first.
- Error details remain collapsed unless useful.

### Accessibility

- Error heading receives focus.
- Service status is announced.
- No indefinite automatic retry.

---

# 15. WF-014 — Exit / Resume

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Leave this project?                                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ You have changes that may not be available after leaving.                    │
│                                                                              │
│ Current progress                                                             │
│ ✓ Interface A approved                                                       │
│ ✓ Interface B approved                                                       │
│ ✓ Connection configured                                                      │
│ ○ Model not yet generated                                                    │
│                                                                              │
│ [Stay and Continue] [Discard and Exit] [Save in This Browser — TBD]          │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Makes data-loss consequences explicit
- Supports local save only if implemented

### Navigation

- Stay and Continue → Return to current page
- Discard and Exit → Clear session and go to landing
- Save in This Browser → Persist locally, then exit

### Responsive

- Dialog fills most of narrow viewport.
- Primary safe action remains first.

### Accessibility

- Modal traps focus.
- Focus returns to initiating control on cancel.
- Buttons describe consequences.
- No reliance solely on browser unload prompt.

---

# 16. Shared Help Panel

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Help: Capturing Interface A                                           [Close]│
├──────────────────────────────────────────────────────────────────────────────┤
│ What is an interface?                                                       │
│ The face, opening, plate, or mounting pattern that must connect to another.  │
│                                                                              │
│ What should I measure?                                                      │
│ Enter at least two dimensions that define the profile scale.                 │
│                                                                              │
│ Examples                                                                     │
│ - Outer diameter of a hose                                                   │
│ - Width and height of a rectangular port                                     │
│ - Hole-center spacing on a mounting plate                                    │
│                                                                              │
│ [View image examples]                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Region responsibilities

- Context-specific explanation
- Does not navigate user away from current task
- Uses plain language

### Accessibility

- Panel receives focus when opened.
- Close returns focus to Help trigger.
- Content uses headings and lists.
- Panel does not cover critical actions without a close control.

---

# 17. Responsive Summary

## Desktop

- Two-column layouts are preferred for:
  - source image + SVG;
  - parameters + live guide;
  - 3D model + design summary.
- Primary action sits near the bottom-right of the task area.

## Tablet / narrow laptop

- Two-column regions may reduce width but remain side by side where practical.
- Secondary help content may move below the main task.

## Mobile / very narrow viewport

- MVP remains usable for review and basic values.
- Image, SVG, and 3D regions stack vertically.
- Tables become cards.
- Advanced editing is not optimized.
- A notice may recommend desktop for profile editing.
- Critical actions remain visible and reachable.

---

# 18. Global Accessibility Requirements

- One H1 per page.
- Skip link before header.
- Workflow navigation has an accessible label.
- All form controls have visible labels.
- Units are programmatically associated with numeric fields.
- Color never carries meaning alone.
- Every SVG or 3D-only value has a textual equivalent.
- Loading, success, error, and stale-state changes use appropriate live regions.
- Dialogs manage focus correctly.
- Keyboard users can complete all MVP flows without dragging.
- Minimum control sizes must remain usable.
- Error summary links to affected fields.
- Viewer motion should respect reduced-motion preferences where applicable.

---

# 19. Navigation and Redirect Rules

- Editing an approved interface invalidates downstream generated artifacts.
- Stale models cannot be exported as current.
- Failed revisions preserve the last successful model.
- Expired or missing local session redirects to Landing with:
  - explanation;
  - start-new-project action.
- No login redirect exists in MVP.
- Backend credential failures remain on the current page and show service recovery.

---

# 20. Open Wireframe Decisions

1. Whether local browser persistence is required.
2. Whether direct browser camera capture is included.
3. Whether basic manual shape entry exists without image recognition.
4. Whether the SVG supports draggable points in MVP.
5. Exact 3D viewer technology and controls.
6. Whether section view is included.
7. Whether sample projects are interactive or static.
8. Whether material preset appears in MVP configuration.
9. Whether estimated volume is shown in the result.
10. Whether design JSON is exposed as an additional recovery/export artifact.
