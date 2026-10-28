# Retopo1 review handoff

## Original SKP parts and Draw3D interactions — 2026-10-26

The original `SW_Toilet.skp` is available as **White toilet — original SKP parts**:
11 separate objects, all 25,809 triangles retained. Global Select covers parts
and guides. Work on selected establishes an explicit operation scope; exclusion,
restoration and per-part inputs/results remain independent. See
[PARTS_WORKFLOW.md](PARTS_WORKFLOW.md) for the tested first-part walkthrough.

[VIEWER_CONTROLS.md](VIEWER_CONTROLS.md) records the Draw3D adaptation:
single input ownership, temporary navigation, clipped visible-only part marquee,
projection switching and standard views. This is a mesh-workflow adaptation,
not full Base 3D/BREP conformance. The real open-part browser tests accepted
551 quads without a guide and 481 with a user-drawn guide at target 500, and
verified cancellation, persistence and exact worker OBJ downloads. Other
original parts still have rejected default-target candidates; retain the
negative reports rather than describing all eleven as solver-qualified.

Current verification bindings: `runs/draw3d-review/verification.json`.
The historical reports below describe earlier changes and evidence.


## Viewer controls — 2026-10-25

Source-vertex snapping, mesh vertex display (F10), edge display, ghosting with
opacity control, middle-drag orbit and right-drag pan are implemented. A module
worker builds the snap index. Camera motion no longer rebuilds guide geometry or
raycasts all edit handles on each frame. Existing source meshes, solver code, user
guide storage and historical mesh-quality reports are preserved.

Read [VIEWER_CONTROLS.md](VIEWER_CONTROLS.md) for the changed paths, controls,
reproduction commands, measured performance, verification and remaining limits.
Final verification: 26 Node tests and 102 browser assertions passed, including
two real synthetic remesh jobs. Exact records and SHA-256 bindings are in
`verification.json` in the task directory.

The raw task record is `C:/dbva/code/ghidra-workbench/work/retopo-viewer-controls-20261025/`.
This work improves interaction and inspection. It does not qualify the rejected
toilet remesh or add protected-crease constraints to the general solver.

## Historical mesh-quality repair handoff

The user rejected actual job `ffeef5297eb24682961917bc01791bf0` (620quads at target450,452-point guide). The previous checks certified weaker properties and missed poor mesh quality. Complete before-code/result bytes were archived before modifications. Read [QUALITY_REPAIR.md](QUALITY_REPAIR.md) for the cause, replacement algorithm, actual comparisons and unresolved scope.

Changed implementation: `worker.py`, `app.js`, `index.html`; added `structured_prism.py`, `quad_quality.py`. Changed startup artifacts: `assets/previews/hexagon.json`, `hexagon.obj`, reassessed `terrain.json`, `cylinder.json`, and `provenance.json`. Existing Reset/density/drawing controls are retained. Reports: README, VERIFICATION, QUALITY_REPAIR and this handoff. Canonical copied research algorithms and original Ghidra databases are unchanged.

Actual replacement is a geometry-class detector and direct periodic quad layout on convex prismatic annuli. It is not triangle conversion or a stored mesh lookup. The rejected stroke now has480quads, minimum angle52.20°, edge ratio max3.011, signed corner Jacobian min0.790, zero irregular-valence vertices and unchanged closed through-hole. Exact user curves/source and independently reread surface samples are retained. Guide fit is approximate and measured; nearest-edge p95 is0.017796.

Current checks: `tests/quality-repair/validation-second/result.json` (46 checks/seven cases), `browser-final/result.json` (15 checks), `rejection-controls/result.json` (7 controls). The transformed octagonal fixture is a new source, not an altered native output. The explicitly injected620-face negative candidate is a failed mesh, never a successful construction. Old prototype/harness failures and prior browser source remain historical. `tests/quality-repair/original/` preserves original code and complete user failure. Raw exploratory files remain `C:/dbva/code/ghidra-workbench/work/retopo-quality-repair/`.

Screenshots of the actual new browser result and real downloaded OBJ are under `tests/quality-repair/browser-final/`. Exact worker inputs/settings/provenance/quality/outputs are under `runs/<job>/`. `tests/quality-repair/artifact-bindings.json` pins all qualifying and negative-job artifacts; record/manifest validation is performed after report writes. Require passed=true in the final records; historical topology-only passes are not quality evidence.

Remaining: general guide-driven patch layout outside the recognized class; nonconvex/multiple holes; crossing/nonmonotone contours; robust predicates/extreme scales; complete self-intersection certification; native algorithm equivalence. Source-frame assumptions and rejected-input prerequisites are in the repair report. Existing terrain/cylinder backends are subjected to the same acceptance gate; rejected density cases are not exported as good results. A cylinder preview with excessive count explicitly warns.

The app serves updated files dynamically. Existing localhost:8741 and127.0.0.1:8742 services are checked without restart; neither user's browser storage nor guide data was cleared. Preserve the user's existing origin when refreshing, then Generate. Runtime health, source/artifact hashes and final manifest are retained in the quality-repair records.
