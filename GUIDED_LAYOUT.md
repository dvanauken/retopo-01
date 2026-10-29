# Guided curved layout

Choose **Curved guide study** for the new route. Draw a freehand stroke on the
surface, or load a contour, open wave or closed wave from the examples. Generate
constructs a fresh mesh from the current curves. Export OBJ saves the accepted
mesh. Editing guides marks the previous result stale.

The source is an original synthetic 642-vertex ellipsoid with 1,280 triangles.
The existing online Kenney hard-surface example remains available. This new
control demonstrates general curved guide input; it is not a claim that every
complex mesh or guide network is solved. The retained toilet bowl regression
still fails, so the toilet keeps its previous solver route.

## Algorithm

`worker.py` selects `guided_layout.py` only for a surface mesh whose model record
sets `guidedLayout: true`, and only when curves are present. Without guides,
the existing Blender QuadriFlow route applies. No saved output geometry or
fixture identity is used to solve a job.

1. Embed actual surface curves into source triangles using shared edge points
   and constrained per-face triangulation. Independently verify parent-plane
   coverage, polygon union, overlap and connected guide chains.
2. Supply embedded edges and guide directions to the pinned independent
   QuadriFlow fork before field and integer layout construction. Hard guide
   anchors agree within integer vertex classes. High-valence guide poles are
   preserved to prevent duplicated hard anchors from collapsing added quads.
3. Select connected output paths and fit monotonic curve parameters, then refine
   surface support, shape and guide targets together.
4. Check actual count, quad angles and Jacobians, edge/area ratios, topology,
   guide distance and tangent error, all-diagonal face contacts, and adaptive
   whole-triangle distance bounds in both directions for both quad diagonals.
   Every check must pass before the worker writes an accepted output.

At most four layouts and two seeds are tried. Count feedback uses
`round(internal_budget * requested_target / actual_faces)` when the actual
count misses the existing 15% tolerance. The user's requested target and all
measurement tolerances stay fixed. All attempts, failed layouts, refinement
meshes, logs, input copies, source hashes and measurements are retained in the
job's `guided-layout/` directory.

## Runtime and reproduction

Install the pinned Python requirements. The Windows executable is
`engine/guided-quadriflow/quadriflow.exe`, build `size-caps-16`, SHA-256
`e94fd63321109573bf47d8e09704b648cbbf564ccb9321e70d6b71bde392c196`.
It differs from `travel-cap-09` in two files. `src/parametrizer-scale.cpp` adds
`ComputeSizeCaps` behind the new flags `-size-caps` and `-size-caps-exact`: the
recovered ZRemesher size rule (edge-tensor curvature with the admitted feature
edges marked out, caps 2·sin(π/16)/κ with floor 0.9·S/4, the mean/min diffusion
sequence and the ratio clamp) written into QuadriFlow's per-vertex scale field;
`-exact` also rescales the base size so the expected count meets the request.
`src/parametrizer-flip.cpp` keeps a short boundary loop open when its vertices
come from the source boundary (upstream filled every loop under 25 vertices,
which closed coarse open parts). Layouts without `-size-caps` are byte-identical
to `travel-cap-09`, which differed from `guide-valence-08` only in
`src/field-math.hpp` (the `-adaptive` surface walks stop after 4,096 face steps,
and a walk with no exit edge ends instead of terminating the process).
Its manifest records its source archive and three MinGW DLL identities. The
current machine's runtime directory is `C:/msys64/mingw64/bin`; another location
can be supplied with `RETOPO_MINGW_RUNTIME`. The executable and DLL hashes are
checked before execution. Changed or missing binaries produce a diagnostic.
The DLLs are external prerequisites and are not bundled here.

`source.zip` retains the modified upstream source, CMake configuration and
third-party source notices. `LICENSE.txt` retains the upstream license. Upstream
revision: `810b7a0967c35b0dc85b4464e3835e26a756c967`,
<https://github.com/hjwdzh/QuadriFlow>. The research workbench's
`work/retopo-guided-layout/build.py` and `build-records/size-caps-16/` retain
the exact compiler command, source hashes, executable and logs. This is an
independent implementation; native ZBrush algorithm equivalence is unqualified.

Research output controls are under the workbench's
`work/retopo-guided-layout/experiments/ellipsoid-{guide-20,open-23,wave-count-24}/`.
The app-stage integration reruns all three controls, exports them and remeasures
them under the same gates in `integration/controls-01/`. The initial wavy run's
725 faces for target 600 remains rejected. Its corrected 510-face output meets
the unchanged 15% count limit exactly; that boundary is not a tighter count
guarantee. Fresh UI input and rejection checks are recorded separately.

## Deferred cases

General crease and attribute transfer, complex intersecting networks, thin
nearby sheets, and robust pole/guide-turn placement remain research tasks.
Distinct curves sharing a collinear interval reject until ownership is defined.
Source routing has a 1,000-face local budget. Double-precision checks and bounded
surface subdivision do not establish exact-predicate robustness. No failed
candidate is offered as an accepted OBJ export.


## Registered feature experiment (2026-10-28)

The opt-in experiment has **not improved the toilet part**. The shipped engine
and default first-passing layout policy remain selected. All count, quad-only,
surface, boundary, feature and contact limits remain unchanged. Do not infer
that 150 or 200 quads are impossible from this implementation's failures.

`RETOPO_FEATURE_LAYOUT` selects `legacy` (default), `registered` (only the four
hard-registration layouts), `ranked` (rank the existing layout plan), or
`compare` (try both). For `registered` or `compare`, set
`RETOPO_REGISTERED_ENGINE` to `engine/guided-quadriflow/development` using an
absolute path. This affects open-surface construction; closed parts retain their
existing route. With no admitted creases and no user guides, registration is
explicitly skipped and the shipped solver is used; that pass is not counted as
registered-feature success. Restart the server to apply environment changes.

The experimental engine is `registered-features-experimental-3`, SHA-256
`f173c58cd0df34ea5e8857cbce45a176117d36ce0564a0751bf57c32ff7ffeaa`.
Its manifest, source archive, patch against the shipped archive, source hashes,
and rebuild script are retained in that directory. Runtime hash checks also
apply to this engine. The native evidence motivating the change is the recovered
embedded-guide, guide-field-constraint, integer-system/transfer and extraction
graph modules under `engine/targets/zbrush/experiments/python`. This is an
independent QuadriFlow implementation of that contract, not byte-exact native
arithmetic or qualified ZRemesher equivalence.

The implementation:

- Retains exact source vertex/edge identity for admitted crease paths. User
  curves cut the triangles, and both incident copies of crossed crease edges
  inherit their identity. Embedding is checked for coverage and ordered paths.
- Sets tags before normals/hierarchy construction, constrains the transverse
  integer component, and transports that component through subdivision. Several
  source samples may map to one output vertex; sample count is not output count.
- Carries path provenance through extraction and protects registered poles.
  Missing, repeated, disconnected, or unintentionally merged paths reject.
  Post-extraction topology repairs are skipped on registered candidates.
- Tests a signed one-cell bridge between distinct paths that would otherwise
  share an integer class. This separation pivot is explicitly engineering policy,
  inspired by native separation constraints. It is not the recovered global
  integer system. Subsequent integer changes are checked and rejected.
- Fits connected registered rows using the existing guide-fitting terms. The
  original geometry gates and the new connected-row assessment must both pass
  for a registered candidate to be accepted.

`feature_rows.py` measures ordered connected rows, distinct path ownership,
closure, source-sheet correspondence, tangent error, adjacent row-edge spacing,
junction consistency, and interior poles. Boundary valence is separate. It
reuses the existing half-spacing distance and eighth-spacing sampling policies;
conservative source-edge geodesics are supplemented only by verified connected
coplanar triangle coverage. This is not the recovered attachment surface walk.

Ranking is declared lexicographic engineering policy, in this order: unrealized
rows, merged path pairs, collapsed loop pairs, junction mismatches, tangent
error, normalized 95th-percentile distance, spacing variation, interior pole
excess, then relative count error. There are no scalar weighting constants.
It ranks the first passing fit of each layout admitted within the existing
420-second layout-admission budget; a fit already in progress can finish after
that deadline. Soft candidates retain the original acceptance gates;
the row assessment is diagnostic for them. A separate bool-count correction
allows two NumPy boolean marks to count as two in the existing relaxation rule;
the default freeze-near-marks policy remains.

The experimental sizing code still shares QuadriFlow sharp-edge flags with
registered smooth guides. Native radius marks use a separate mode-2/20-degree
condition. This distinction remains unported, so smooth-guide sizing must not
be described as native-equivalent. In `compare` mode, soft-layout flags also use
the experimental binary; registration-disabled byte parity has been checked on
two elementary controls only. The separately frozen baseline uses the shipped
binary throughout.

The accepted baseline 188-quad output at target 200 realizes 27 of 76 raw
crease paths, misses 49, merges 14 distinct path pairs, and has three junction
mismatches and eight interior poles (seven valence-three, one valence-five).
The metrics expose problems that per-face and distance gates did not catch.
Trying all 12 existing layouts took about 243 seconds; the same 188-quad output
was the only passing candidate. Ranking alone produced no improvement.

Engine controls preserve an open planar row and a closed cylindrical row at
100 and 200 requests. Two nearby cylindrical loops also remain distinct at
both counts. These are graph-contract tests, not full application acceptance.
A separate complete planar application run requests 200 and returns 196 quads;
all four registered layouts pass all original gates and the connected-row gate.
Evidence is under `runs/registered-plane-pipeline-v3-final`; its source and
engine snapshots are stable throughout the run.

On island 6, the raw 76-path graph and a diagnostic branch-pruned 27-path graph
both reject at `integer-registration`: `Integer solve changed a registered
separation bridge`. The branchwise admission-length probe is policy, not a
recovered admission rule for this open/junction network; it is not enabled in
the application. Neither probe establishes feasibility or infeasibility at the
requested count. The next unresolved work is a global integer solve that keeps
path separation, junction identities and loop periods consistent through every
subdivision and correction stage, together with qualified open/junction feature
admission. More positional fitting cannot repair a missing topological row.

Regression inputs, original authored guide, requests, source/code/engine hashes,
failed layouts and browser traces are retained under
`tests/registered-features/2026-10-28/` and `runs/`. These generated directories
are ignored by Git; the verification scripts are source controlled. The frozen
baseline is the current 30-degree implementation, rather than the older
205-quad/45-degree result described in the initial review request.


Reproduce the isolated controls and full application control from the project
root (each output directory must be new):

```powershell
python engine/guided-quadriflow/development/validate_experiment.py
python tests/verify_registered_plane.py --out runs/registered-plane-review
python tests/verify_registered_features.py --out tests/registered-features/review-run --env RETOPO_FEATURE_LAYOUT=registered --env RETOPO_REGISTERED_ENGINE=C:/dbva/code/retopo-1/engine/guided-quadriflow/development
```

The worker matrix uses the app's cached source parts and the exact original guide
now retained in `tests/fixtures/island6-authored-guide.json` (SHA-256
`a0d6cf3967c194ee6770df57e54b373517be418a82dedfe284f2baacac841c3c`).
`tests/verify_registered_features_ui.py` exercises real part selection, generation,
export/reload or expected rejection through an owned server and Chromium.
`tests/audit_registered_features.py` independently audits the exported geometry.
`build_experiment.py` rebuilds the pinned archive in a separate directory and
records compiler identities without replacing the packaged executable. A fresh
archive rebuild and all six mechanism controls passed.


The final worker matrix below ran with stable source and engine hashes at a
30-degree crease threshold. Every rejected registered case failed before fitting
with the separation-bridge diagnostic above. A rejected worker is an experimental
failure, not a passing geometry result.

| Case / requested quads | Frozen shipped baseline | Registered experiment |
| --- | --- | --- |
| Island 6 / 150 | Rejected | Rejected |
| Island 6 / 200 | Accepted, 188 quads | Rejected |
| Island 6 / 300 | Accepted, 268 quads | Rejected |
| Island 6 / 750 + authored guide | Accepted, 839 quads | Rejected |
| Island 2 / 300 | Accepted, 291 quads | Accepted, 291; no-feature fallback |
| Island 7 / 300 | Accepted, 339 quads | Accepted, 339; existing closed-part route |
| Island 10 / 500 | Accepted, 456 quads | Rejected |

Detailed records: `baseline30-summary.json` and
`registered-v3-final-corrected/result.json` under the evidence directory. The two
accepted comparison cases do not exercise hard registration. All 179 unit tests
pass, including exact crease embedding across user-curve cuts, connected rows,
nearby sheets, distinct open paths, closed-loop junctions independent of cycle
start, and the marked-relaxation boolean correction.


Real browser verification passed for both final outcomes: the default route
produced 188 quads, its OBJ download matched the accepted file exactly, and
reload restored the result and requested target; the registered route displayed
its failure without promoting an output mesh. Both runs had stable source and
engine identities and no page or network errors. The default source and output
bytes match the independently export-audited frozen baseline exactly. The known
irregular rows are unchanged. Screenshots and detailed records are in
`ui-legacy-final-200/` and `ui-registered-v3-200/` under the evidence directory.

A compact hash-bound summary is retained in
`engine/guided-quadriflow/development/application-verification.json`, alongside
`evidence-digest.json` and `feature-row-evidence.json`. Earlier failed integration
runs are retained, including the transient initial UI source-load failure and
the corrected empty-feature adapter rejection; they are not counted as final
solver evidence.
