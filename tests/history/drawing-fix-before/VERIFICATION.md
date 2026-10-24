# Demo verification

Standalone verification in `C:\dbva\code\retopo-1` passes all37 browser/API checks. These are actual headless Chromium interactions and live original-input calculations, including a pointer-drawn closed curve, two density settings, independent geometry rereading, real downloads, erase/undo/redo, split/overlay, source switching, both color themes and narrow/laptop layouts. Browser JavaScript errors:0. Runtime browser requests use only local assets.

The manually drawn guide's sampled edge-distance p95 improves from0.0878856576812 in the baseline to0.00381958671141 in the generated mesh. This is measured in the prepared source coordinate units against actual output edges, using the retained guide samples. It is not a native-equivalence or arbitrary-input guarantee. Bidirectional exported-surface samples meet2e-6, and the closed genus-one topology retains the through-hole.

Actual successful density runs:

| Target | Vertices | Quads | Euler |
|---:|---:|---:|---:|
| 600 | 936 | 936 | 0 |
| 450 | 690 | 690 | 0 |


`tests/verification/result.json` records individual terminal checks and exact code/source hashes. `drawn-output-measurement.json` records independent methods and tolerances. `downloaded-output.obj` is hash-equal to the actual worker export; `downloaded-guides.json` preserves the actual drawn coordinates. Original current job records remain under `runs/`. The third verification job tests owned-worker cancellation and is not a successful mesh.

`tests/candidate/geometry-measurements.json` separately measures the online asset's baseline, preset loop and preset crossings. They retain closed Euler0 and100%quads, with source-unit sampled surface tolerance2e-6. All source/preparation/online license information remains under `assets/`. Initial startup examples are labeled Example and are not the live generator.

The first deployment manifest is retained as `tests/verification/deployment-manifest.json`; `BUILD_MANIFEST.json` is refreshed after standalone verification to bind the final code/assets and test results. Runtime jobs, automatic .codestring metadata and Python caches are intentionally excluded from the static build manifest. No original workbench research, installed program or Ghidra database was changed by this application task.
