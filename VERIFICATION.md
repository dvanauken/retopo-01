# Current mesh-quality verification

The latest quality repair passes46 construction/export checks across seven declared cases,15 real-browser checks and7 element-calibration/rejection controls. Exact current code hashes, raw artifacts, images and the user-rejected case are linked in [QUALITY_REPAIR.md](QUALITY_REPAIR.md). The earlier checks below are preserved historical epochs and did not establish useful retopology quality.

# Guide-drawing correction

The original split-view picker accepted only the left/source half of the canvas. In a fresh default isometric browser session, a real left-pane drag created one guide while an equivalent right-pane drag left the count unchanged. There were no JavaScript errors: the right-side input was silently discarded. Original code, manifest, screenshot and raw probe are retained in `tests/history/drawing-fix-before/`.

Drawing and erasing now work in both comparison panes. Each pane converts its own screen coordinates to the shared camera, and guide points always intersect the original source geometry. The previous output is never used as the next solve's source. A stroke stays in its starting pane; crossing the divider cannot join unrelated screen positions. In overlay, the same original source is picked. The initial point is visible immediately; drawing also enables guide visibility. Instructions and help now say to select Draw (G), then hold and drag on either mesh. Existing saved curves, undo history, engine sources and running server were preserved.

`tests/verify_drawing.py` passed **20 focused checks** using real Chromium mouse, touch and pen dispatch. It checked default isometric left/right strokes, matching source coordinates, immediate draft points and live screenshots, guide visibility, right-pane erase/undo, closed right-pane loop, overlay and divider crossing, and one actual worker solve. Browser errors: zero. The matching-gesture source tolerance is 1e-5 of source units (0.0005% of the two-unit source extent); raw measured differences were at most 3.34854e-7 due to browser subpixel coordinate rounding. Initial overly strict 1e-7 comparison failures are retained as `tests/drawing-fix/*failure.json`; they were not promoted as passing tests.

The actual job `runs/b345698d68774838b78a14b0d89a9bf6/` used the exact curve coordinates drawn in the right pane. It produced **926 quads**, changed the 736-face baseline, remained closed with Euler characteristic zero and no nonmanifold edges, and measured guide-to-output-edge p95 **0.00381951064992** source units. Submitted inputs, actual output polygons, engine provenance and report remain in that run. These finite checks establish this interaction and fixture, not arbitrary-input or native-equivalence guarantees. The earlier 37 checks below were not rerun or relabeled as checks of the modified code.

Individual results and code hashes: `tests/drawing-fix/result.json`. Coordinate comparison: `pane-comparison.json`; submitted curves: `right-pane-curves.json`; before/mid-stroke/after screenshots are retained in the same evidence folders. Both dark and light result screenshots were visually reviewed. The existing service at http://127.0.0.1:8742 serves the exact updated app hash, recorded in `running-service.json`; it was not restarted, and no existing user browser storage was edited. Refresh an already-open page to load the correction.

Changed files: `app.js`, `index.html`, `README.md`, `VERIFICATION.md`, `BUILD_MANIFEST.json`; new reproducible check: `tests/verify_drawing.py`; raw records: `tests/drawing-fix/`; original build archive: `tests/history/drawing-fix-before/`. The new manifest binds current code, assets and both evidence epochs. Runtime jobs and browser state remain outside its static inventory.

# Demo verification

The initial app build in `C:\dbva\code\retopo-1` passed all37 browser/API checks. Its original code hashes and results remain historical evidence for that build. These are actual headless Chromium interactions and live original-input calculations, including a pointer-drawn closed curve, two density settings, independent geometry rereading, real downloads, erase/undo/redo, split/overlay, source switching, both color themes and narrow/laptop layouts. Browser JavaScript errors:0. Runtime browser requests use only local assets.

The manually drawn guide's sampled edge-distance p95 improves from0.0878856576812 in the baseline to0.00381958671141 in the generated mesh. This is measured in the prepared source coordinate units against actual output edges, using the retained guide samples. It is not a native-equivalence or arbitrary-input guarantee. Bidirectional exported-surface samples meet2e-6, and the closed genus-one topology retains the through-hole.

Actual successful density runs:

| Target | Vertices | Quads | Euler |
|---:|---:|---:|---:|
| 600 | 936 | 936 | 0 |
| 450 | 690 | 690 | 0 |


`tests/verification/result.json` records individual terminal checks and exact code/source hashes. `drawn-output-measurement.json` records independent methods and tolerances. `downloaded-output.obj` is hash-equal to the actual worker export; `downloaded-guides.json` preserves the actual drawn coordinates. Original current job records remain under `runs/`. The third verification job tests owned-worker cancellation and is not a successful mesh.

`tests/candidate/geometry-measurements.json` separately measures the online asset's baseline, preset loop and preset crossings. They retain closed Euler0 and100%quads, with source-unit sampled surface tolerance2e-6. All source/preparation/online license information remains under `assets/`. Initial startup examples are labeled Example and are not the live generator.

The first deployment manifest is retained as `tests/verification/deployment-manifest.json`; `BUILD_MANIFEST.json` is refreshed after standalone verification to bind the final code/assets and test results. Runtime jobs, automatic .codestring metadata and Python caches are intentionally excluded from the static build manifest. No original workbench research, installed program or Ghidra database was changed by this application task.
