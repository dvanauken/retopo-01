# Viewer controls and source-vertex snapping

## Draw3D interaction alignment — 2026-10-26

Reviewed `C:/dbva/code/claude-skills/specs/draw3d/draw3d-spec.pdf`,
Draw3D 1.0.0-draft.1 with inherited Draw2D 3.0.0-draft.21. The relevant
requirements are PDF pages 20–24 (selection, navigation, input ownership) and
99–101 (one selection snapshot, click/Shift/marquee semantics).

Select is now the startup/home tool and remains available on every ribbon tab.
One ordered selection snapshot covers visible mesh parts and the current working
source's guides. A click selects; Shift-click toggles membership; empty click
clears; empty-space drag selects fully contained visible objects in either
direction. Guide editing uses only the guide subset of a mixed selection.
Part selection shows a blue overlay and synchronized list/inspector feedback.
Selecting a part does not switch its working source, move it, or move the camera.

**Work on selected** requires one included part and isolates it for guide and
remesh operations. **Show assembly** restores the assembly without changing
exclusions. **Exclude selected**, **Keep only selected**, and **Restore all**
control inclusion separately from temporary isolation. Excluded objects are
removed from assembly display, picking, and export. Original open imported parts
can be restored; open regions produced by a repair split retain the existing
Undo-split restoration policy. Generate acts on one selected included part, or the current working part when no part is selected. Generate selected opens that part, retains the displayed target and uses its saved guides. Imported
manifold open islands use a boundary-preserving route; they are not capped.
Inclusion/name commands have atomic Undo/Redo in Parts. Guide Undo/Redo remains
scoped to the current working source. View changes retain selected part IDs;
changing the actual source model clears selection.

Navigation is routed by the application's canvas handlers. The DOM-free
`ViewportNavigation` adapter owns camera calculations and has no competing
pointer listeners. Controls:

| Input | Result |
| --- | --- |
| Middle drag, Space + left drag | Orbit around the current target |
| Shift-middle, right drag, Shift-Space + left drag | Pan in the camera plane |
| Orbit / O; Pan / H | One navigation gesture, then resume the prior tool |
| Wheel at cursor | Perspective dolly or orthographic zoom, anchored on the target-depth plane |
| Fit / F | Frame selection (or source if empty), preserving orientation |
| Front / Top / Right / Isometric | Set orientation, preserving target and distance; Isometric selects orthographic |
| Projection menu | Switch perspective/orthographic with target-plane scale preserved |
| Escape | Cancel the current interaction and release capture |

Orbit uses Z-up yaw/pitch with pitch bounded to 0.001–π−0.001 radians. It
preserves target and distance. Pan translates camera and target together.
Navigation has no inertial tail; drawing can resume immediately at release.
Perspective starts at 45° vertical FOV. This Z-up application maps Front to
look along +Y, Top along −Z with +Y screen-up, Right along −X, and Isometric
from (1, −1, 1). Fit derives clipping and zoom bounds from the framed geometry. Pointer-free
Polyline/Spline construction retains its instance and accepted points across
temporary navigation. An owned edit/draw drag must end or cancel first.
Selection and camera changes add no geometry undo records.

This is an interaction adaptation, not Base 3D conformance. This application
authors meshes rather than BREP, has no kernel face/edge/vertex edit roles,
and uses coupled cameras for its source/result comparison. Mesh surfaces remain
two-sided because original imported pieces include open/inconsistently oriented
faces; nearest visible depth still governs picking, with no select-through mode.
Part marquee clips triangles at the near/far planes before testing the full
projected footprint, with 0.5 CSS pixel boundary tolerance. A separate depth-tested
ID pass requires a visible rendered pixel at the display resolution, including
all source occluders. Ghosting does not enable selection through surfaces.
The source/result comparison deliberately shares one camera; full independent
multi-viewport cameras and BREP face/edge/vertex editing are outside this mesh
workflow. Guide selection retains its existing sampled surface-visibility policy.
The existing face-paint/split operation remains a separate operation on the
working source; global object selection does not imply mesh deformation.

Current evidence and reproduction:

- `python -X utf8 tests/verify_global_selection.py`: 13 scenarios with real
  pointers, Shift-union marquee in both directions, selection, exclusion,
  atomic inclusion undo/redo, isolation, input focus, navigation, capture and IO.
- `python -X utf8 tests/verify_camera_contract.py`: projection/view invariants,
  near-plane crossing, tiny visible surfaces, occluded and partial-footprint
  rejection, renderer restoration and DPR 2.
- `python -X utf8 tests/verify_guide_editor.py`: 60 existing guide checks,
  including edits, cancellation, native capture, IO and two actual worker solves.
- `python -X utf8 tests/verify_skp_parts.py`: 25,809 original triangles conserved,
  eleven selectable/exportable parts, and per-part generation availability.
- `python -X utf8 tests/verify_open_part_browser.py --guided`: user-drawn guide,
  real open-part worker, native OBJ download, sibling independence, persistence,
  inclusion and cancellation preserving the accepted output.
- Domain/snapping/display: 34 Node checks across `guide-editor`,
  `parts-document`, `vertex-snapping` and `crease-normals` test files.

The accepted original bowl (`skp-2`, target 500) produced 551 quads unguided
and 481 with the browser-drawn guide. All quality, source-feature, topology,
boundary, surface-distance, guide and both-diagonal contact gates passed.
Open parts are not universally solved: several other original islands failed
at their default targets. Failed attempts retain source geometry and any prior
accepted output. This is interaction/workflow verification, not certification
that every part or guide network has an acceptable remesh.

`runs/draw3d-review/verification.json` binds current implementation files and
records the detailed test/evidence paths. Screenshots include `selection.png`
and `orthographic.png`; accepted open outputs are under the recorded job IDs.

## Solver activity — 2026-10-28

Generate opens the Log dock. The worker writes append-only `events.jsonl`
records containing real stage/candidate timestamps and validation outcomes;
the server delivers new complete records using a cursor. Partial writes are
retried without losing events. The browser records a heartbeat every 30 seconds
without a new worker stage; a heartbeat is elapsed-time feedback, not solver
iteration progress. Warnings show the rejected checks and measurements/limits.
**Save log** exports the visible activity (up to 1,000 entries). The full worker
event stream remains with the run on disk.

A failed saved run keeps its job identity and can be inspected after a service
restart. Opening a part with a remembered failed attempt restores its diagnostic
activity. Older runs have no stage timestamps; recovered candidate rows display
`—` rather than invented times. The first captured island 6 failure at target
7,200 ran 15 candidates across three layouts. Its best candidate passed quad
shape/count, surface/boundary and intersection checks, but exceeded two source
crease-distance limits. This rejection does not publish a mesh.

Evidence: `runs/job-activity-review/result.json` and the current positive worker
run referenced by `runs/job-activity-review/verification.json`. Reproduce with
`python -X utf8 tests/verify_job_activity.py` (reads the captured real failure)
and `python -X utf8 tests/verify_open_part_browser.py --direct` (a fresh real
worker, stage/candidate log, Save log, accepted OBJ and cancellation).

The historical controls and evidence below describe the previous implementation.

Implemented 2026-10-25. These controls improve drawing and inspection of the
existing source/result meshes. Protected-crease remeshing, local density painting
and patch isolation remain separate solver work. Showing a sharp edge or snapping
a guide to its vertex does not make that edge a protected solver constraint.

## Controls

| Control | Behavior |
| --- | --- |
| Properties → Drawing options → Snap to source vertices | Snap freehand, Polyline and Spline input and their point edits to visible source vertices. Both comparison panes use the original source. |
| Snap to guide points | Independent existing option for authored guide points. When both options are enabled, distance chooses between their candidates, subject to snap retention. |
| Alt while drawing or editing | Bypass both point snap types, including the release sample. Closure has its existing separate behavior. |
| F10, View → Vertices, or Properties → Mesh vertices | Show source/result mesh vertex positions as fixed-size points. This is a display option, not mesh vertex editing. |
| View → Edges or Properties → Mesh edges | Show/hide mesh edges. |
| View → Ghosted or Properties → Ghosted surfaces | Make source and result translucent. Properties exposes opacity from 10–70%, initially 28%. Guides, edges and points retain their independent toggles. |
| Middle-button drag | Orbit from a drawing or selection tool. |
| Right-button drag | Pan from a drawing or selection tool. |
| Mouse wheel | Zoom, including while a drawing tool is selected. |
| Hold Space and left drag | Existing temporary orbit gesture. |
| Fit / F; Top | Existing camera reset commands. |

An unfinished click-based guide survives temporary navigation. An owned guide drag
must finish or cancel before camera navigation begins. Navigation and display
options create no guide undo entries. Input fields retain keyboard ownership.
The calculation panel leaves the viewport available for navigation while its
Cancel button remains usable. Rendering preferences are saved separately in
`retopo-1:viewer`; this does not change the authored guide file format.

## Snap contract and limits

Acquire within 8 CSS pixels; retain the same target up to 12 CSS pixels. A square
marks a source-vertex snap; a circle marks a guide-point snap. The committed source
vertex coordinates come from the original mesh record, not the rendered Float32
buffer. The cursor must hit the source surface. Visibility is checked by raycasting
the candidate's projected position and requiring a world-space distance no greater
than `1e-5` in the application's source coordinate frame. Ghosting never permits
snapping through a surface. The source remains the snapping authority in the
result pane, even when its tessellation differs from the remesh.

Circle center/radius input uses its existing analytic construction and is not
vertex-snapped. No grid, intersection, tangent, edge-interior or protected-crease
selection is added. Ghosted faces use ordinary transparent WebGL rendering;
intersecting transparent surfaces are not guaranteed to sort perfectly.

## Responsiveness changes

`VertexIndexWorker.js` projects source vertices and builds 16 CSS-pixel spatial
bins outside the UI thread. `VertexSnapIndex.js` allows one pending worker request
and one latest camera snapshot. It rejects stale camera/source results. While an
index is pending or workers are unavailable, snapping tests only the front-hit
triangle's vertices. The current implementation keeps rendering, raycasting and
document editing on the main thread. Remeshing already runs in a separate Python
process; this change does not move the solver into a browser worker.

Guide geometry is rebuilt once per requested frame when guide data or styling
changes. Idle pointer movement no longer rebuilds all guide tubes and UI rows.
Coalesced pointer input batches UI synchronization. Expensive edit-handle visibility
raycasts are deferred during camera movement and restored after the camera settles;
GPU guides and mesh points continue to render while navigating.

The same headless Chromium test on the 24,000-triangle toilet with a guide selected
for point editing measured a 24-step orbit at **56.195 seconds before** and
**2.646 seconds after**. RAF interval p95 was **849.9 ms before** and **50.1 ms after**.
This is a same-machine diagnostic, not a desktop FPS guarantee or a solver benchmark.

## Changed files

- `app.js`, `index.html`, `index.css`: controls, points/ghosting, temporary navigation,
  drawing synchronization, rendering scheduling and nonblocking progress panel.
- `src/snapping/GuideSnap.js`: shared guide-point/source-vertex snap policy.
- `src/snapping/VertexProjection.js`, `VertexIndexWorker.js`, `VertexSnapIndex.js`:
  projection, worker and request lifecycle.
- `tests/vertex-snapping.test.mjs`: projection, clipping, hysteresis, exclusions and
  stale/coalesced worker tests.
- `GUIDE_EDITOR.md`, `WORKSPACE_LAYOUT.md`, `REVIEW_HANDOFF.md`, this document:
  current controls, evidence and limitations.

No Python solver, input mesh, saved guide file or historical result was replaced.
Original frontend files and hashes are retained before deployment.

## Final verification

Installed-code validation passed: **26 Node tests and 102 browser assertions**
(19 viewer checks, 23 workspace checks, 60 guide-editor checks). The guide-editor
suite includes two successful actual synthetic hexagon remesh jobs and verifies
that their worker inputs equal the editor-derived freehand/Spline samples. This
does not newly qualify the toilet's output geometry. No browser JavaScript errors
were recorded. Final source/artifact identities are checked in `verification.json`.

The installed viewer's toilet orbit measured 2.916 seconds with RAF interval p95
50 ms during the concurrent regression run. The staged before/after comparison
above remains the retained performance comparison.

The predeployment hash check detected an existing update to GUIDE_EDITOR.md's
description of prior toilet qualification. That sentence was preserved; its bytes
and reconciliation are retained in `predeployment-existing/` and `reconciliation.json`.

## Evidence and reproduction

The retained task directory is
`C:/dbva/code/ghidra-workbench/work/retopo-viewer-controls-20261025/`.
Paths below are relative to that directory:

- `baseline-hashes.json` and `original/`: original bytes and SHA-256 identities.
- `baseline-20261025-075136/result.json`: pre-change camera benchmark.
- `staged-20261025-075324/result.json`: 19 passing real-browser checks, performance
  measurements and no JavaScript errors. Adjacent PNGs show both themes and the
  toilet with solid/ghosted faces and visible vertices.
- `deployment.json`: hash-guarded deployed file list and before/after identities.
- `verification.json`: final verification records and artifact hashes. Consult its
  status for deployed verification; historical passes describe their recorded bytes.
- `verify_viewer.py`: owned read-only HTTP server and real Chromium pointer/keyboard
  tests; the pending-calculation test uses intercepted responses and no solver job.
- `run_existing_regressions.py`: retained adaptation of the existing browser suites,
  with fresh evidence directories and an owned server that preserves the normal
  service's discovery record. The guide-editor suite makes two new synthetic jobs.

From `C:/dbva/code/retopo-1`:

```powershell
node --test tests/guide-editor.test.mjs tests/vertex-snapping.test.mjs
python -X utf8 C:/dbva/code/ghidra-workbench/work/retopo-viewer-controls-20261025/verify_viewer.py --deployed
python -X utf8 C:/dbva/code/ghidra-workbench/work/retopo-viewer-controls-20261025/run_existing_regressions.py
```

The Python checks require the existing Playwright/Chromium environment. Each owns
its own browser context and loopback server. No user's open browser storage is
cleared, no running application is restarted, and prior verification directories
are preserved. Refresh the existing application page to load the deployed frontend.
