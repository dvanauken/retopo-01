# Retopology quality repair: the rejected user stroke

The previous demonstration failed the intended modeling-quality requirement. Its successful checks established closed topology and quad percentages, but did not establish useful quad shape or coherent edge flow. The user's screenshot is matched to actual job `ffeef5297eb24682961917bc01791bf0`: target450, 620quads and one452-point open stroke. Its complete original input, settings, result, logs and actual code bytes were preserved under `tests/quality-repair/original/` before changes.

## Root cause and replacement

The old default `engineering-planar-pslg-quads` route independently triangulated constrained planar charts, greedily paired triangles, and split cell edges/centers to obtain quads. That can satisfy all-quad incidence while creating poor angles, tiny edges and unrelated irregular vertices. It also overshot the user's density target by37.78%. The old result now fails explicit quality checks; it is never relabeled as a passing quality result.

`structured_prism.py` recognizes an actual geometry class: two congruent planar caps with nested convex polygonal loops and straight extruded side walls. It derives its frame and physical outlines from original vertices/faces, rather than the model ID or a precomputed output. The replacement builds periodic circumferential loops, radial cap strips and axial wall strips directly as quads. Shared boundary ownership preserves seams and the hole. Physical corners are included in the parameter grid. Nearby corner directions caused by decimal input rounding are grouped within1e-5radians, then the actual original corner positions are snapped within1e-6source-span tolerance. Independent surface measurements test the resulting geometry without fitting output coordinates.

Guides are classified by surface and direction into contours and radial/axial spokes. Periodic or partial smoothed profiles steer loop positions; spokes steer columns. A discrete allocation search selects circumferential/height/radial counts and guide-row assignment using shape, count, spacing and actual designated-guide-path fit. Raw input curves are retained unchanged. Continuation outside a partial/open near-loop stroke is a property of the layout; it does not alter or falsely mark the user's raw curve closed. The actual output guide cycles are recorded as ordered vertex IDs and every consecutive pair is verified to be an output edge.

## Same stroke, measured result

| Measurement | User-rejected output | Rebuilt output |
|---|---:|---:|
| Faces, at target450 |620|480|
| Target error |37.78%|6.67%|
| Smallest corner angle |15.46°|52.20°|
| Largest corner angle |174.01°|127.80°|
| Worst max/min edge ratio |7.280|3.011|
| Minimum signed corner scaled Jacobian |0.104|0.790|
| Irregular-valence vertices |86|0|

Actual rebuilt job: `runs/0ab7ac79b053468ea945231a3939d505/`. A second actual browser-triggered replay is `runs/6684e6a30d80414fad63eff59e18a762/`. The original source identity remains SHA256 `2edf41e5cebbb98712f4705179a7dcdd33bfcc5f03364452a8effd19ffc765cc`. Submitted user curves compare exactly to the preserved input. Both cap hole and closed Euler-zero topology are preserved; all output faces are quads. Bidirectional exported-surface samples remain within2e-6source units. The new overall nearest-edge p95 is 0.017796source units. This distance is larger than the old0.007157, reflecting the explicit tradeoff toward a coherent sparse loop layout rather than exact local triangle constraints. Guide fit is measured and bounded separately from shape.

Screenshots are actual rendered results, not illustrations: [top dark](tests/quality-repair/browser-final/user-result-top-dark.png), [perspective dark](tests/quality-repair/browser-final/user-result-perspective-dark.png), [top light](tests/quality-repair/browser-final/user-result-top-light.png). Actual downloadable browser export is `tests/quality-repair/browser-final/actual-browser-output.obj` and is hash-equal to that worker's output. The screenshots were visually reviewed.

## Acceptance and interface corrections

`quad_quality.py` measures signed corner scaled Jacobians, included3D corner angles, max/min edge ratio, adjacent polygon area ratio, unique-edge length variation, graph valence and actual count error. It does not mislabel the simple edge ratio as a vendor's aspect-ratio formula. Its conventions are informed by [Sandia/CUBIT quadrilateral quality definitions](https://www.sandia.gov/files/cubit/15.3/help_manual/WebHelp/mesh_generation/mesh_quality_assessment/quadrilateral_metrics.htm); limits are explicitly this demo's engineering policy, not a claim of universal sculpting suitability.

Limits set before the repair tests: minimum angle30°, minimum signed corner Jacobian0.45, edge-ratio p95≤3.5 and max≤6, adjacent area-ratio p95≤4, target relative error≤15%. A designated contour path also requires p95 distance≤0.20target edge lengths and tangent p95≤30°. Surface/manifold checks remain separate. Invalid quality candidates are stored as `failed-output.obj`, `failed-mesh.json`, `quality.json` and a failed report; they do not become a successful `output.obj` or display result. Analytic square, skinny, concave and bow-tie controls calibrate the test. An explicitly injected known-bad620-face candidate proves the actual worker rejects it and retains diagnostic files; that is a negative control, not a successful remesh.

The former Topology check / Passed tile is now Mesh quality with actual minimum angle and worst edge ratio. Details add signed Jacobian, regular-valence fraction, count error and warnings. Backend labels identify Continuous quad grid. The initial hexagon preview is an actual rebuilt624-quad baseline. Old terrain/cylinder previews were reassessed; the cylinder's512faces against target400 is explicitly a quality warning rather than a green qualified result. Existing drawing, Reset and density controls were preserved. No browser storage or live user session was cleared and neither existing app service was restarted.

## Verification and retained failures

- 46 actual construction/export checks across seven cases: baseline, exact user stroke at450, low150, high1200, loop, crossings, and a newly generated rotated/scaled/translated octagonal annulus. Source-class recognition succeeds on that separate320-quad geometry without a cached mesh or model-specific lookup. Exact settings, original-input artifacts, measured outputs and source hashes are in `tests/quality-repair/validation-second/` and referenced `runs/` folders.
- 15 final real-browser checks: exact curve import, actual worker, correct rendered quality/backend, real export, both themes, actual new pointer stroke, stale-result indication and honest warning on an unqualified old example. The final source/preview cohort remained unchanged during that run. Browser errors: zero.
- 7 quality-calibration/rejection controls in `tests/quality-repair/rejection-controls/`. The negative worker result stays failed; the guard assertion passes because it was rejected.
- First prototype attempts exposed overly strict angular corner deduplication on decimal input; those did not construct a successful result. The first formal validation used the engine's triangle-only source OBJ reader on a quad export and failed in the harness. `validation-first/` retains its failed result and source. The corrected independent polygon reader and a fresh destination are used in `validation-second/`. A final browser Details predicate was tightened to require both angle and Jacobian rows; its earlier source remains in `browser-first/`. No failed result was promoted.

Reproduce with fresh destinations:

```text
python -X utf8 tests/quality-repair/verify_quality.py validation-new-name
python -X utf8 tests/quality-repair/verify_browser_quality.py browser-new-name
```

The tests use isolated localhost servers and browser contexts. Numerical dependencies are the existing pinned app environment; browser tests need Playwright/Chromium. Source hashes and actual job artifacts are recorded. `verify_rejection.py` intentionally reserves its existing destination; copy it with a fresh output name if rerunning the negative control. Original workbench research and Ghidra projects were not changed.

## Scope still unfinished

This repair is a reliable demonstrated improvement for the recognized prismatic-annulus class, not a general native-quality retopologizer. Arbitrary organic surfaces, nonconvex or multiple holes, intersecting/nonmonotone contour networks, topology-changing guide layouts, arbitrary feature graphs and exact native allocation remain unresolved. Other surface backends remain available only subject to the new common quality gate; a failed density/quality case is rejected rather than marketed as complete. The scalar checks and seven finite fixtures do not certify all self-intersections, all inputs or artistic mesh quality. Further work needs a general guide-directed field/patch layout strategy and a broader visually reviewed modeling corpus.
