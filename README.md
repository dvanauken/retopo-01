# Retopo1

The workspace uses a top ribbon, left navigator, central viewport, right properties panel, and a bottom Measurements / History / Log dock. Light is the default, with blue primary actions, white/gray surfaces and gold accents. Panels resize and collapse; View contains visibility controls. See [WORKSPACE_LAYOUT.md](WORKSPACE_LAYOUT.md).

The guide editor now supports freehand and clicked Polylines, smooth Splines, analytic Circles, 5-pixel green loop-closure snapping, whole-guide and point selection, surface-constrained editing, snapping, atomic undo/redo, and source-bound guide files. See [GUIDE_EDITOR.md](GUIDE_EDITOR.md) for controls, the Draw 2D requirements mapping, surface policies, and verification. This is the guide-specific adaptation of Draw 2D draft.21, not full Base 2D conformance.

Current quality repair: the exact user-rejected620-face stroke is rebuilt as480coherent quads, with minimum angle52° and worst edge ratio3.01. See [QUALITY_REPAIR.md](QUALITY_REPAIR.md) for actual before/after data, screenshots, reproduction and remaining scope. Use `http://localhost:8741` if that is the origin of your existing browser session; refresh and Generate again to retain its saved curves.

A local HTML canvas app for exploring retopology with user-drawn surface curves. The viewport uses WebGL through a vendored Three.js renderer. A local Python worker actually reconstructs and validates the mesh; drawing a guide does not just recolor an existing grid.

## Start

Double-click `start.cmd`, or run:

```powershell
cd C:\dbva\code\retopo-1
python -X utf8 server.py
```

Open **http://127.0.0.1:8741**. Choose another local port with `start.cmd --port 8742` if needed. The app and its renderer work without an Internet connection after installation. Keep the terminal open when starting this way.

This machine already has the qualified64-bit Windows Python numerical environment. On a new environment, install `requirements.txt`; Python3.12 is the reference environment. The independent SuiteSparse CHOLMOD DLL and its source/build evidence accompany `engine/`. No ZBrush process or Maxon binary is used. Node/npm is optional; `npm start` simply starts the same Python service. There is no frontend build step.

The toilet's curved-surface quad solver also uses the locally installed Blender. On a new machine, install Blender or set `RETOPO_BLENDER` to its executable before starting the server. See [TOILET_SOLVER.md](TOILET_SOLVER.md) for construction, acceptance limits and verification.

Exhaustive toilet testing remains open. After fixing quad warpage, fresh unguided, lid-guide and lid-Circle results at target 1,800 pass the strengthened surface and contact checks plus independent export audits. Bowl and combined-guide cases remain unresolved. The five historical exports failed the stronger audits and remain superseded. See [the audit plan and coverage gaps](TOILET_TEST_PLAN.md) and [current solver limitations](TOILET_SOLVER.md).

## Try it

1. Start with **Hollow hexagon**, the downloaded online example. The right view initially shows an explicitly labeled example baseline. Its source has896 triangles; the current baseline has624 actual quads.
2. Choose **Draw** (or press **G**), then hold the mouse button and drag on either mesh. A blue stroke appears immediately. Both views attach guides to the original source surface; drawing also turns guide visibility on. Hold **Space** to turn it, or use **Orbit**. Scroll to zoom. **Top** is useful for drawing around the hole.
3. Load **Contour loop** or **Loop and crossings** to see a repeatable example. Or draw your own loop, checking **Close the next stroke** and finishing near its start. A stroke across empty space splits into separate surface guides.
4. Select a target density and press **Generate retopology**. **Half / Same / Double** set the target from the source density, as ZRemesher does; the readout compares source and target spacing (`sqrt(area / quads)`, counting two source triangles as one quad) and warns when the target is more than 1.5× finer than the source. The displayed result is the actual new geometry from your submitted curves. Changed inputs mark the previous result **Needs update** until generated again.
5. Compare **Split** and **Overlay**, toggle guides/mesh/sharp edges, and inspect **Details**. **Export OBJ** exports real polygon faces; **Save guides** exports source-frame curve JSON. **Load guides** restores it for the matching source mesh.

Undo/redo: Ctrl+Z / Ctrl+Shift+Z. G draws freehand; P/S construct Polyline/Spline guides by clicking, then Enter; return within 5 CSS pixels of the green first point and click to close. C creates a Circle from center and radius; Alt+Enter closes. V selects whole guides; A edits points; double-click also enters point editing. Shift adds guides, empty-space drag selects by containment, and Escape cancels. O orbits; E erases by clicking near a guide; F fits the model. Local browser storage preserves guides/settings per source hash. Source and result views share the camera.

## Included meshes

| Mesh | Purpose | Source |
|---|---|---|
| Hollow hexagon | Through-hole, angled planar faces, hard corners, closed guides and crossings; fast default demonstration. | [Kenney Prototype Kit](https://kenney.nl/assets/prototype-kit), CC0-1.0. Original `shape-hollow-hexagon.obj` and license retained in `assets/`. |
| Terrain patch | Curved contours, ridge guides and an intentional open border. | Original synthetic research fixture; the measured enclosure/crop reference route. |
| White toilet | Original plain SW_Toilet; live curved-surface quad generation with fitted guide-edge paths and measured acceptance. | User-provided `SW_Toilet.closed.web.glb`; provenance in `assets/raw/toilet/`. |
| Curved cylinder | Curved-surface flow and flexible-direction versus preserved-path guidance. | Original synthetic research fixture; recovered field pipeline. |

The online hexagon export repeats its face group and contains one zero-area triangle and a collinear T joint. Preparation welds only identical coordinates, removes exact duplicate/degenerate faces, conforms that T joint without moving the existing surface, rotates Y-up to Z-up, normalizes the bbox, and applies two conforming midpoint subdivisions. The prepared geometry is a closed connected genus-one surface. `assets/preparation.json`, raw download, acquisition hashes and creator license record these changes. It is derived from the actual online asset, not a procedural substitute with an attribution attached.

The smooth examples are slower, typically one to three minutes on this host including import/compilation. The curved example requires a guide; its built-in guide network is loaded initially. The solid fits guides to coherent structured paths; it does not interpolate every freehand sample exactly. The terrain retains its declared path behavior. The curved source additionally exposes the two explicit recovered semantic modes; no invented0–100 strength conversion is shown.

## Results and reproducibility

Every live solve has a fresh `runs/<id>/` directory containing original source OBJ, submitted curves, settings, stdout, actual output OBJ, crease intent, mesh JSON, measurements and engine provenance. `execution.json` records actual process exit/state. Failed returned geometry is retained separately and never displayed as a successful new output. The last successful result remains visible with its update status.

`assets/previews/` contains previously completed example results for immediate startup and source switching. They are explicitly labeled **Example**. Live Generate uses the current inputs through an independent worker, not a library of canned results. Preview provenance records their origins. Original-input baseline/loop/crossing checks and independent surface/topology measurements are under `tests/candidate/`.

The app starts a new owned Python process per calculation, with one solve running at a time. Cancellation terminates only that worker. The service binds127.0.0.1. API settings are validated, project paths are not accepted from the browser, and job files are retained locally.

## What this demonstrates

The default solid now uses a direct, geometry-detected structured annular grid: shared physical seams, continuous circumferential edge loops, radial cap strips and axial side strips. Guide profiles influence these coherent paths. The previous planar triangle-pairing/subdivision route produced poor modeling quality on the user-reported stroke and is superseded for this recognized surface class. See [the measured repair and limits](QUALITY_REPAIR.md). Sharp source geometry is retained. The “Sharp edges” checkbox controls visibility; it does not disable feature preservation. Exported crease intent contains binary geometric edges; OBJ alone does not carry subdivision crease semantics. Detailed crease data remains in the run's `features.json`.

The terrain uses the separately labeled closed-enclosure/visible-crop route. The curved cylinder uses the recovered field/parameterization/extraction path. The toilet explicitly uses an engineering QuadriFlow layout plus connected guide-path fitting and surface/shape refinement; the recovered conditioning path remains unchanged. The independently built reference engine closure is copied into `engine/` with its licenses and recorded hashes. Core files are preserved from the qualified research package; this app supplies interaction, job isolation and actual export measurements around it.

Target count is approximate. Strong or numerous constraints can increase it. The metrics show actual face proportions, component/border/incidence and vertex-link checks, plus guide-to-output-edge p95 distances in source units. The curved-surface route measures 257 uniformly spaced arc-length samples against each connected guide path; legacy routes use up to 129 evenly indexed samples. These finite checks are not a Hausdorff certificate or complete3D collision test. Engineering alternatives are not claimed to reproduce every native ZBrush branch.

General overlapping/degenerate constraints, thin-sheet projection, arbitrary source attributes/flat crease strengths, exact native allocation/parameterization parity and nonconvex/holed terrain domains remain follow-up work. The UI reports unsupported networks rather than pretend a failed solve succeeded. The supplied examples deliberately expose the useful ordinary contract while keeping those limitations explicit.

## Files

- `index.html`, `app.js`: canvas viewport, surface picking/drawing, editing, comparison and exports.
- `server.py`, `worker.py`: local API, owned-job execution and measured geometry.
- `assets/`: online source, CC0 license, clean source meshes, source/preview provenance.
- `vendor/`: pinned Three.js0.180.0 and MIT license, served locally.
- `engine/`: relocatable previously qualified reference closure and numerical backend.
- `tests/`: retained interaction/API/output verification and screenshots.
- `DESIGN.md`: local design tokens and canvas material additions.

All research originals remain in `C:\dbva\code\ghidra-workbench`; this application does not modify their sealed records or Ghidra databases.


## Verify

With the optional `playwright` Python package and its Chromium browser installed, run `python -X utf8 tests/verify_demo.py`. The test starts and stops its own localhost server on a free port. It uses real pointer strokes, performs live solves at two densities, independently measures exported geometry and guide registration, verifies real downloads, exercises undo/redo/erase, checks both themes and narrow layouts, and tests invalid requests and cancellation. Results and screenshots are retained under `tests/`. It does not change an already running application server.

For the guide-drawing fix, run `python -X utf8 tests/verify_drawing.py`. Its 20 focused checks include default isometric drawing in both panes, immediate previews, hidden-guide recovery, right-pane erasing/undo, overlay, mouse/touch/pen, divider crossing, and an actual remesh from a right-pane closed stroke. Records are under `tests/drawing-fix/`.

Guide-influence repair: the exact user-reported partial curve now follows a measured output-edge path, with p95 distance improving from 0.06954 to 0.01847 and p95 tangent mismatch from 61.75° to 11.67°. See [GUIDE_INFLUENCE_REPAIR.md](GUIDE_INFLUENCE_REPAIR.md).
