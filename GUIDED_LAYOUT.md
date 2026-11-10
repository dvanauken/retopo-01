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
`engine/guided-quadriflow/quadriflow.exe`, build `constrained-edges-18`, SHA-256
`c8aa18231c3565fea8ed5fd341c0b9bd7dea7b4e90eb3df0e1b5a290fefc05de`.
It adds the `-constrained-edges` flag to `size-caps-16` (SHA-256 `e94fd633…c196`)
and is byte-identical to it when the flag is not used; see "Guides cut into
the source" below. `size-caps-16` differs from `travel-cap-09` in two files. `src/parametrizer-scale.cpp` adds
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
`work/retopo-guided-layout/build.py` and `build-records/constrained-edges-18/`
(and `size-caps-16/`) retain the exact compiler command, source hashes,
executable and logs. This is an
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


## Exact screenshot rim investigation (2026-10-28)

The pink rim is not currently a hard geometric guard rail. In screenshot job
`3029972da0174acd9845b6ec0df6e3ea`, none of the 283 pink crease edges or their
vertices belongs to the true open boundary. That boundary is an inner loop
underneath the folded lip. Its measured maximum error is 0.062 h and its
certified bounds pass 0.1 h. The visible outer fold is governed by weaker
feature and whole-surface checks.

At source edge [1308, 1309], the nearest output edge is 0.422 h away. The
crease-band allowance reduces that sample's measured error to 0.181 h.
Across all source feature samples, the raw 95th-percentile distance is
0.328 h; band subtraction reduces it to 0.199 h, below the 0.25 h limit.
A sequence of nearby unrelated edges can pass this check without forming a
connected row along the rim. This explains the accepted jagged outline;
it is not evidence that the visual result is satisfactory.

Fresh controlled ZBrush captures use the exact source and keep-creases at
30 degrees. A 200 request returns 374 faces (364 quads and 10 triangles).
At the same rim witness its edge distance is 0.011 h, and the long left-rim
branch has an ordered row. This is a local improvement at a substantially
larger output budget, not a claim of global quality or 200-quad feasibility.
The fully instrumented 200 output is byte-identical to the ordinary run.
The 300 capture returns 646 faces; its vertices and winding-preserving face
multiset match its ordinary control, with different face ordering.

Review of native `0x28fe70` against the actual 200-part capture found a missed
mixed guide/seed branch: after `cross < 2 * gap`, gaps below 4.5 can create a
soft separation candidate; the previous helper incorrectly also required
`cross < gap` for larger gaps. Soft gaps at or above 1.35 retain their original
target instead of being clamped to one. The shared policy-only helper now
expresses that rule. Native mode2 elimination (`0x288f50`) also skips a row
containing only the reserved constant, without consuming a pivot. General
nonunit scalar pivots remain explicitly unsupported.

The portable regression for this actual part reproduces all 129 geometric
residuals, 160 candidate constraints, 125 new dependencies, 21 nested integer
values and 71 outer fixes. An earlier ellipsoid callback remains exact.
These are tests at an explicit captured upstream field/chart boundary;
they do not reconstruct the complete source-to-output remesher. Nineteen
original candidate relations are not satisfied by the native final solution:
mode2 candidate elimination can discard inconsistent constant-only rows.
Those optional separation candidates must not be confused with mandatory
upstream guide equalities. Locking every candidate independently is not the
native global method.

The three recovered helper changes do not alter the default QuadriFlow route.
All 183 unit tests pass. The portable inputs, native hashes and reproduction
instructions are in `tests/fixtures/native_integer/README.md`; compact exact-job
measurements and provenance are in
`engine/guided-quadriflow/development/native-rim-verification.json`.
Full captures and comparison plots are retained under
`runs/native-rim-investigation/`. No improved application mesh is claimed.


The required adapter boundary is also narrower than the whole native remesher:
export the app's continuous field immediately before `ComputeIndexMap`, then
construct a cut/fan parameter chart, guide scalar groups, singular seeds and
seam periods. QuadriFlow's `mO` stores local 3D lattice origins, not globally
consistent UV coordinates; projecting `(V - O)` is insufficient. The current
recovered closed-surface wrappers explicitly reject open edge-angle/seed cases,
some closed or branching guide groups, and the actual candidate sentinel case.
Those producers need qualified open-part implementations before the tested
native callback can drive this mesh without captured upstream inputs. The next
milestone is an app-owned chart and coupled solve whose rim identities survive
extraction; successful replay alone does not reach that milestone.


The isolated QuadriFlow diagnosis also found two mechanical defects. Flip
hierarchy contraction removed nonzero locked separation edges; protecting their
incident faces keeps the individual locks intact. Extraction then stalled in
`FixValence`: three faces shared edge [104, 105], and nonreciprocal adjacency
made the fan walk cycle. Requiring mutual unique opposite halfedges removes
that hang while retaining valid-manifold pairings. Three standalone adjacency
regressions pass. The unrelated polygon memoization hypothesis was discarded;
the final experiment uses the original `QuadEnergy` file unchanged.

The frozen isolated engine is
`9343e8a5196e9151af421b95cada226aa3f3a221b8255ca0a163d9784fbc71b8`.
Two selected, disjoint rim paths finish in 1.19 seconds at target 200 and
2.09 seconds at 300, but still reject: the first merges path ownership; the
second has ambiguous origins and broken row edges. Both diagnostic meshes
also fail geometry checks. The raw 76-path case finishes in 1.31 seconds with
327 diagnostic faces and 231 unintended path-merge incidences, and rejects.
These failures are retained, not presented as accepted results.

All six control OBJ files and registration reports are byte-identical to the
prior preservation-only experiment, including its close-cylinder100 rejection.
The frozen v3 engine passed that control, so the combined experiment is not
promoted. Current traces do not locate the precise stage that introduces every
final ownership conflict. Source archive, patch, compiler/build record and
executable are in `runs/native-rim-investigation/qf-locks/fan-fix/`; final runs
are in `fan-fix-clean/repro-and-controls.json`. Both packaged engines remain
unchanged. The corrected traversal makes the failure inspectable; it does not
supply the missing global chart and consistent rim-row layout.


## Crease rows (2026-11-09)

Island 6 at a request of 200 now generates with a continuous, ordered edge row
on its rim, and the crease check rejects a mesh without one. The screenshot
mesh of job `3029972da0174acd9845b6ec0df6e3ea` fails the new check on its rim
and on nothing else. Results and job ids are at the end of this section.

### Why the rim had no row

Three causes, in the order they act:

1. **The layout engine never treated the visible rim as a feature.** QuadriFlow's
   `-sharp` hardens edges whose dihedral exceeds a fixed 60°
   (`ComputeSharpEdges`, `cos(60°)` in `parametrizer-mesh.cpp`). The application
   admits creases at the native 30°. Island 6's upper rim crease measures 33° to
   54° along its length, so it only received soft orientation guidance. Its
   partner a quarter face below (35° to 95°, median 85°) was hardened and got
   partial rows. That is the edge line the screenshot shows wandering under the
   rim.
2. **The fit drew other edges onto the band.** The fit pinned every crease
   junction to its own output vertex and pulled any vertex within 0.45 h of a
   crease onto it. A band holding several short creases therefore attracted a
   second edge line, which pinched a strip of thin quads or dragged the row off.
3. **The check did not ask for a row.** It measured each crease sample to the
   nearest output edge of any kind and subtracted the local band width. Edges
   0.42 h from the rim passed.

### What native does, and where this differs

Native ZRemesher embeds admitted creases as guide edges and keeps them as rows
through extraction (recovered embedded-guide and extraction-graph modules). Its
integer policy (`0x28fe70`) proposes a separation of one cell for parallel
guides closer than 1.35 cells; these are candidates the solve may drop. On this
part it keeps both rim creases as rows, with a strip of thin quads between
them: the 374-face native capture has a row on each.

This application cannot copy that at 200 quads under its own quad-shape limits.
The rim wall is 0.24 h high; a row of about 40 quads with an edge ratio near 4.4
breaks the 3.5 limit on the 95th-percentile edge ratio. One row per band of
parallel creases is therefore **this application's existing band policy**
(`source_features.band_widths`: creases within half a face and 30° of parallel
form one band). It is not a native rule and is not claimed as one.

### The check (`crease_rows.py`, enforced through `source_features.measure`)

- **Representatives.** Within a band, the crease bordering the wider sheet
  represents the band. Sheet width is walked across the source triangles in the
  plane perpendicular to the crease edge, to the next crease or boundary. On
  island 6 this picks the upper rim crease (top sheet) over the lower one
  (underside, about one face wide). *Engineering choice.*
- **Chains.** Representative edges are joined into chains; a chain continues
  through a junction when it turns by less than 30° (the existing band angle).
  A chain needs a row when its extent is at least two requested faces: a row is
  at least two consecutive edges. *Engineering choices.*
- **The row.** One connected output edge path that runs forward along the
  chain, found with the cost already used for authored guide paths
  (`curved_quad._guide_path`). *Engineering choice.*
- **Distance.** From the path to the band span at each chain sample: the strip
  between the representative and the parallel creases it absorbs. A row anywhere
  across its band measures zero; a row beside the band is charged its whole gap.
  This replaces the scalar band allowance, which forgave a gap on either side.
- **Limits**, all numbers the application already used, in requested faces:

  | Measure | Limit | Existing meaning it reuses |
  |---|---|---|
  | `rowP95` | 0.25 h | "95 % of each crease within a quarter face of an edge loop" |
  | `rowMax` | 0.5 h | "no crease point runs through the middle of a face" |
  | `rowEndMax` | 1 h | "a vertex within one face of every junction"; last face of arc at each open end |
  | `rowTangentP95Degrees` | 30° | connected-path limit for authored guides |

  The first, second and fourth leave out the end zones the third covers.
  `rowsMissing` counts representative chains without an accepted row; the limit
  is zero. The older nearest-edge measures are unchanged and still apply.

Native measurement on the same check (island 6, request 200, 364 quads): rim
0.103 h at the 95th percentile, 0.387 h maximum, 12.5° direction; both hinge
chains under 0.01 h. Native passes. It is reference evidence, not a standard.

### The generator (`open_surface.py`, `feature_refine.py`)

*Superseded on 2026-11-10 in two respects: the row chains now reach the engine
through its constrained-edge list instead of `-embedded-guides`, and the
soft-guide encoding below is removed. See "Guides cut into the source". The
rest of this section stands.*

- **Rows layouts.** Chains that need a row are handed to the unmodified engine
  as embedded guide edges (`-embedded-guides`), which enter its integer and
  extraction constraints exactly as sharp edges do. Their band partners are left
  out. Other creases keep the old treatment: hard at QuadriFlow's 60° or more,
  soft orientation guides below. No engine binary changed; both packaged hashes
  are as before.
- **Soft-guide encoding.** With `-embedded-guides` the engine hardens every
  source edge, or piece of one after its own subdivision, whose ends lie on a
  guide segment to within 1e-8 of the model's half extent
  (`guide-constraints.hpp`). Soft creases are therefore written a millionth of
  the model extent off the surface along their normal. They orient the field
  over the same support and are never embedded: the engine logs 366 embedded
  oriented edges for island 6 at 200, exactly the hard list after subdivision.
  This is a transport encoding for the existing engine, not a geometric
  tolerance. A dedicated engine flag for a hard-edge list would be cleaner.
- **Fit.** Each row is fit like an authored guide: its connected path is held on
  the representative crease. A row band is fit through that row only: its
  samples attach to row edges, and its junction and vertex pulls are dropped.
- **Search.** Most seeds do not put a row on every chain, so layouts are
  screened before fitting. The first pass fits seeds whose rows already meet the
  quarter-face limit unfitted; the second fits the rest within half a face. A
  layout whose quad shape or rows still fail after two fits is dropped. Engine
  layouts run eight seeds at a time. Budget: 32 seeds, 360 s for rows layouts,
  the existing 420 s admission budget overall. The older layouts follow and are
  held to the same check. *All of this is search policy, not acceptance.*

### What is and is not claimed

- Enforced for open parts, which is the route island 6 uses. The closed-part
  solver (`feature_quad.py`) has no row fitting yet, so there the row report is
  recorded and not enforced. Island 7's current 339-quad output would fail one
  of its five chains (source vertices 159 to 380: 0.30 h, 63°).
- The check accepts a row anywhere across its band. The generator aims at the
  representative; a mesh whose row sits on the band partner also passes.
- Acceptance at 200 still depends on a seed search. The hinge lugs, which are
  about one face tall, use most of the 5 % budgets of the older checks, so few
  seeds pass everything. This is unchanged behaviour: the previous 188-quad
  result was the only passing candidate of twelve layouts.
- Island 6 at 150 is still rejected. It was rejected before this work.
- Nothing here is recovered native arithmetic. The parameter chart and combined
  integer solve named as the next milestone were not needed for the rim and
  were not built.

### Results (2026-11-09, final code)

Witness source edge [1308, 1309], island 6, request 200, h = 0.0823. Distances
are to the nearest output edge of any kind, as in the investigation.

| Mesh | Faces | Witness point | Largest along the edge | Rim row (95th percentile / maximum / direction) |
|---|---|---|---|---|
| Before: job `3029972da0174acd9845b6ec0df6e3ea` | 188 | 0.422 h | 0.422 h | 0.323 h / 0.384 h / 17°, rejected (also 1.16 h at one end) |
| Native ZRemesher, keep creases 30° | 374 | 0.011 h | 0.027 h | 0.103 h / 0.387 h / 13°, passes |
| After: job `70df0003c0e141499bb504b661ef8f9b` | 207 | 0.004 h | 0.018 h | 0.044 h / 0.311 h / 12°, passes |

The after mesh passes every existing check: minimum angle 35.1°, edge ratio
2.86 at the 95th percentile and 5.56 at most, scaled Jacobian 0.57, count +3.5 %.
Its rim row runs from lug to lug in 30 vertices. Near the left lug, where the
crease leaves the rim, the row is 0.31 h off for about one face; that is inside
the limits and is the largest deviation.

Real UI (`tests/verify_registered_features_ui.py --case island6-200`, owned
server and Chromium, no stubs): job `70df0003c0e141499bb504b661ef8f9b`, 207
quads, accepted in 46.8 s, export downloaded and identical to the accepted
file, reload restored the result, no page or network errors. The worker matrix
produced the same bytes for the same case (SHA-256 `b7e18406…1a66`).
`tests/audit_registered_features.py` re-read the exported OBJ and passed it.

Worker matrix (`tests/verify_registered_features.py`, run `182fbe2cc53e`, code
stable), against the same matrix run on the unchanged code earlier the same day
(run `e9a14a0f873d`):

| Case | Before | After | Rows required / realized | Job |
|---|---|---|---|---|
| Island 6 / 150 | Rejected, 285 s | Rejected, 377 s | 3 | `registered-182fbe2cc53e-island6-150` |
| Island 6 / 200 | 188 quads, 60 s | 207 quads, 44 s | 3 / 3 | `registered-182fbe2cc53e-island6-200` |
| Island 6 / 300 | 268 quads, 114 s | 331 quads, 86 s | 4 / 4 | `registered-182fbe2cc53e-island6-300` |
| Island 6 / 750 + guide | 839 quads, 48 s | 751 quads, 150 s | 5 / 5 | `registered-182fbe2cc53e-island6-750-guide` |
| Island 2 / 300 | 291 quads | 291 quads, same bytes | none admitted | `registered-182fbe2cc53e-island2-300` |
| Island 7 / 300 (closed) | 339 quads | 339 quads, same bytes | 5 / 4, not enforced | `registered-182fbe2cc53e-island7-300` |
| Island 10 / 500 | 456 quads, 28 s | 545 quads, 118 s | 6 / 6 | `registered-182fbe2cc53e-island10-500` |

Six of seven pass, the same six as before. Island 6 at 150 fails the surface
check on its best candidate, as it did before. The three "before" outputs for
island 6 at 300, 750 + guide and island 10 fail the new row check, which is why
their results changed. All 197 unit tests pass.

The search is deterministic but sensitive: which seed is accepted changes with
small input changes. Island 6 at 200 is accepted at seed 13 in the first pass,
750 + guide at seed 22 in the second. While the soft-guide encoding was being
settled, the same case was accepted at seed 25 with 218 quads.

Other open parts were not worked on. They were run once each to look for
collateral damage, old pipeline against new in the same process (old = no row
plan, rows not enforced):

| Part / request | Old pipeline | New pipeline |
|---|---|---|
| Island 1 / 1,500 | Rejected (crease, surface, contacts), 737 s | Rejected: 69 chains need rows, no layout has all of them, 261 s |
| Island 3 / 300 | 321 quads | 321 quads; no chain needs a row |
| Island 4 / 300 | Does not finish: the size-caps layout post-processing loops | Same loop, reached after the rows layouts |
| Island 8 / 300 | 274 quads, one of three rows missing | 315 quads, three of three rows |
| Island 9 / 300 | 315 quads, one of three rows missing | 295 quads, three of three rows |
| Island 11 / 300 | Rejected (surface) | Rejected (surface) |

No part that generated before fails now at these requests. Two limits showed:

- The row finder assumes a chain does not pass within a face of itself. Island
  4's outline is one 94 h chain with a hairpin; no layout got a path for it.
  Splitting chains at sharp corners would address it. Island 6's chains have no
  corner of 30° or more at 150, 200, 300 or 750, so that change would not touch
  it; it was left out to keep this work on one problem.
- Island 4 at 300 never returns, before or after: an endless loop in the
  unchanged post-processing of its first size-caps layout. It is a separate
  defect.

Compact record with hashes: `engine/guided-quadriflow/development/crease-rows-verification.json`.
Evidence folders (git-ignored): `tests/registered-features/rimfix-rows-3/`,
`tests/registered-features/rimfix-ui-200b/` (UI screenshot `island6-200/result.png`,
comparison plot `rim-before-native-after.png`), baseline matrix
`tests/registered-features/rimfix-baseline/`.


## Guides cut into the source (2026-11-10)

Open parts now treat an authored guide the way ZRemesher does at Curves
Strength 100: the guide is cut into the source triangles, its cut edges join
the admitted crease edges in one constrained-edge list, the layout engine
registers the guide edges, and the guide check asks for one continuous edge
loop. Island 6 at a request of 200 with the guide of job
`483afe83c71d40d2858066813a3f553a` returns 204 quads with one loop of
11 vertices on the guide and no turns. That job's earlier output, a
zig-zag chain that turned onto another loop at 8 of its 13 inner vertices, now
fails the check on those turns and on nothing else. Results, pictures and job
ids are at the end of this section.

### What was wrong

- The guide never entered the source. `open_surface.py` wrote the drawn
  polyline as soft orientation segments (`-guides`, a band 0.75 h wide,
  position weight 0). The engine had no edges to keep, so no edge loop was
  promised.
- After the layout, `curved_quad._guide_path` chose the cheapest connected
  edge path near the curve and the fit dragged its vertices onto the curve.
  The path could step sideways from loop to loop.
- `guides_pass` measured only that path's distance (0.20 h at the 95th
  percentile) and direction (30°). The dragged chain measured 0.08 h and 26°,
  and passed.

### The native rule, and what is ported

Sources: `ghidra-workbench/work/retopo-lowcount/AUDIT.md` §2 (items 2, 5, 6, 8, 9)
and the recovery documents it cites. Addresses are RVAs of `xremeshlib2.dll`.

| Native stage | Port | Where |
|---|---|---|
| Projection `0x2e9730`: nearest triangle within 0.025 of the bbox diagonal; snap to a vertex of that triangle within a squared distance of 1.1111111e-7 × diagonal² | Ported. The nearest-triangle search is trimesh's; native's tie order among equal triangles is not reproduced. | `native_guide_cut._Cutter.project` |
| Classification `0x10bdd0`: face point to vertex, else to edge (infinite supporting line), within diagonal × 1e-6 (floor 1e-8); the last qualifying one wins | Ported | `classify` |
| Direct paths `0x10c0a0`: two points of one face keep no sample; faces sharing an edge get one crossing; vertex and edge neighbours append | Ported. A crossing outside the shared edge goes to the walk instead of being appended unclamped. Two samples on one edge have no recovered branch and are appended directly. | `direct` |
| Walk `0x10d2e0`: per candidate face the direction to the next sample is projected into that face; the farthest forward crossing wins; reversal above t = 0.98; tolerance 1e-5, expanded retry ×10; 1,000-step guard | Ported in double precision (native uses float32 determinants). Native's endpoint repair is replaced by the fallback below. | `walk`, `_line_edge` |
| Fallback `0x0fd6f0`: source-vertex path with the 20× span-length limit | Ported | `fallback` |
| Prepass `0x255b10`: a cut point within 5 % of an edge end becomes that source vertex and **the vertex moves to the cut point**; runs on one edge fold; endpoint propagation, up to 5 sweeps | Ported for open paths. Closed paths take the same policy; the native wrap handling is not ported. | `prepare` |
| Triangulation `0x2567b0`: chords split their faces; `0x252e50` uses Triangle `pzQ`; free end points are repaired inward by `0x253d80` (0.001 toward the opposite corner, 3 passes) | Every cut face goes through Triangle (`pQ`). Native splits edge-to-edge chords at `0x254210` and converts later; the guide edges are the same, the diagonals inside a cut face may differ. Inward repair ported. | `cut`, `_inward` |
| Collector `0x2889c0/0x28e230`: feature edges and mode-1/2 curve edges in one vector with a mode byte | One list, guides first, then creases, a mode per edge | `registered_features.constrained`, engine `-constrained-edges` |
| Directions `0x2fc0c0`: each embedded edge writes its normalized direction to its incident faces; later writes win; nothing is locked by distance | The engine's field lives on vertices, so the direction goes to the edge's two end vertices, in list order, later writes winning. Guides have no orientation band any more. | `guide-constraints.hpp: attach_constrained_edges` |
| Mode-2 integer registration `0x28b920` (flag and denominator 1): the guide lies on an integer iso-line | In this engine's terms: the lattice origin of each vertex on a mode-2 edge is constrained to the edge line, and the edge enters the integer solve and extraction as a preserved edge. Applied to guides. | same |
| Mode-2 marks `0x2706a0`: ends of embedded edges that turn 20° or more take no curvature | Applied to listed mode-1 and mode-2 edges in the size-caps estimate (used by the `caps` layouts only) | `parametrizer-scale.cpp` |

Not native, and labelled so in the code:

- **Arithmetic and source.** Double precision, not byte-identical. Native cuts
  its conditioned (densified) source; here the part's own triangles are cut,
  so inside a large flat triangle the cut path is the straight chord between
  the entry and exit crossings. On the test case the drawn samples lie up to
  0.14 h from that chord. The fit and the check use the drawn curve.
- **Creases are not registered like guides.** Native lists its kept features
  as mode 2. Here crease rows and other creases of 60° or more are *preserved
  edges with the direction write and no lattice line* (engine mode 3, not a
  native mode); gentle short creases are direction only (mode 1); band
  partners are left out. The listed creases also keep the 0.75 h orientation
  band from the crease-row work, now written at exact source coordinates.
  Measured reason, island 6 at 750 with the authored guide, one search of 64
  seeds per treatment: creases as mode 2, nine layouts reached the fit and
  none passed (the front crease runs half a face from the rim row and seldom
  got its own row); mode 3 without the band, six reached the fit, none
  passed; preserved edges without the direction write, with the band, four,
  none passed; mode 3 with the band, accepted at the second fitted layout
  (seed 6). Admission and the one-row-per-band rule are the application's
  (`source_features`, `crease_rows`); native has neither.
- **Engine.** The guided QuadriFlow fork is an independent implementation of
  the contract above. Registration there is strong but not a guarantee: the
  integer and extraction stages can still break a loop, mostly within two
  faces of a guide's free end, so layouts are screened and seeds searched.
- **Search budget.** 64 seeds in two blocks of 32 (`ROW_LAYOUT_SEEDS`,
  `ROW_SEED_BLOCK`), inside the existing 360 s. Policy, not acceptance.
- **Limits of the guide check**, including the 45° corner rule. See below.

Curves Strength below 100, closed parts, Adaptive Size, PolyGroups, density
paint and symmetry were not touched. Metadata still records `guideMode: 2`;
for open parts that is now what is implemented.

### The engine build

`engine/guided-quadriflow/quadriflow.exe` is now build `constrained-edges-18`,
SHA-256 `c8aa18231c3565fea8ed5fd341c0b9bd7dea7b4e90eb3df0e1b5a290fefc05de`
(source archive `ef8a5e0b…e60e`). It adds one flag to `size-caps-16`:

    -constrained-edges <file>     first line: count; then `a b mode` per edge,
                                  0-based vertices of the input OBJ

| Mode | Direction write | Lattice line | Preserved edge | |
|---|---|---|---|---|
| 1 | yes | no | no | native mode 1 |
| 2 | yes | yes | yes | native mode 2 |
| 3 | yes | no | yes | engine only |
| 4 | no | no | yes | engine only; not used by the application |

The list is read after loading and before the engine subdivides its source, and
each half of a split edge keeps its identity (`subdivide.cpp`), so no geometric
coincidence test is involved. Without the flag the build is byte-identical to
`size-caps-16` on five controls (caps, sharp, adaptive, the old
`-embedded-guides` rows layout, plain): `guide-cut-verification.json` →
`engineParity`. Build records: workbench
`work/retopo-guided-layout/build-records/constrained-edges-17/` (two modes,
superseded the same day) and `constrained-edges-18/`.

The 1e-6 "lift soft creases off the surface" encoding is removed
(`open_surface.write_row_guides` is gone). Hardness comes from the list alone;
the crease band file holds exact source coordinates.

### The guide check (`guide_rows.py`)

A path **turns** at a vertex when the edge it arrives by and the edge it leaves
by border the same face. Through a regular vertex that is leaving the loop; an
interior vertex of valence three cannot be passed without a turn.

Each guide needs one connected, forward-ordered output edge path with no
turns. Distances are from the drawn guide to that path, in requested faces,
with the crease-row limits and their meaning: 0.25 h at the 95th percentile,
0.5 h maximum, 1 h in the last face of arc at each open end, 30° direction
over one face. The search for the path runs over directed edges so a step may
only follow another when the two do not border one face
(`guide_rows.find_loop`). When no such path meets the limits, the cheapest
connected path is reported with its turns, so a zig-zag shows as turns.

**Corners.** A loop cannot bend at a sharp corner of the guide, and native does
not ask it to: a guide's parameter edges fall into groups with one field axis
each (`0x28b920`), and at a corner the guide passes from one axis to the
other. In the mesh that is one turn at the corner vertex. One turn is
therefore excused at each corner of the guide itself, where the guide's
direction changes by 45° or more from the face before a point to the face
after it. The 45° is an engineering choice (half the quarter turn of a cross
field; native has no angle, its groups come out of the solved field). The
test guide is a smooth arc and has no corner at any request. The authored
guide of the 750 case has two; its old accepted mesh had seven turns and fails
on the six that are not at a corner.

The older connected-path limits (0.20 h, 30°/35°) still apply as well. The
check is enforced in `open_surface.construct`, again in `worker.py` from the
finished mesh, and in `tests/audit_registered_features.py` from the exported
OBJ. Closed parts are not changed.

The limits are this application's numbers, not native ones; native applies no
acceptance test. Native's own output passes them (table below).

### The generator

- `registered_features.constrained` cuts the guides, writes the cut source and
  `constrained-edges.txt`, and records the cut (`open-surface/constrained/`).
- Rows layouts run on the cut source with `-constrained-edges`. They are
  screened before fitting for crease rows, as before, and now also for a
  no-turn loop within reach of every guide.
- The fit holds the loop on the drawn guide with the existing guide terms. The
  path it holds is the no-turn loop (`open_surface.guide_paths`); a rows layout
  without one is dropped.
- The older layouts (`caps`, `constrained`, `adaptive`, coarsened) remain as
  the fallback and answer to the same guide check.
- `RETOPO_FEATURE_LAYOUT` defaults to `default` (the former name `legacy` is
  accepted). The opt-in `registered`, `compare` and `ranked` policies still
  select the 2026-10-28 path-provenance engine; their cut is now the native
  one as well. They were not re-qualified.

### What is and is not claimed

- Open parts only. Closed parts keep their route and their guide check.
- The cut follows the recovered native rules; the layout engine does not. A
  loop on the guide is found by screening seeds, not guaranteed by
  construction. On the test case 53 layouts were tried: 51 were screened out
  (50 for a crease row, 1 for the guide), one was fitted and rejected, and
  seed 52 was accepted.
- On flat controls the engine holds the loop on a registered guide along its
  length and lets go of it up to two faces before a free end (a slanted line
  at a request of 300: the last 1.9 h at each end). The one-face end limit
  rejects such layouts. Native covers its guide to 0.54 h of the ends here.
- The app's result is not native's mesh. Native returns 532 faces for a
  request of 200 with 77 triangles; the app returns 204 quads inside its
  ±15 % count band. What is matched is the behaviour asked for: one edge loop
  on the guide, rim rows kept.
- The crease treatment (mode 3 plus band) rests on one 64-seed search per
  alternative on one case. It is a measured choice, not an established ranking.
- A cornered guide on a short run can fail the 30° direction limit near its
  corner, because the one-face chord there points along neither leg. Not seen
  on the cases run; noted because the corner rule is new.

### Results (2026-11-10, final code)

Test case: island 6 (`skp-6`), request 200, keep creases at 30°, the guide of
job `483afe83…` (`tests/fixtures/island6-guide-483afe83.json`), h = 0.0823.
Guide and rim numbers are measured by `tests/render_guide_case.py` from each
mesh alone; the rim row is the 34.3 h upper rim chain; the witness is source
edge [1308, 1309] from the rim investigation.

| | ZBrush ZRemesher, Curves Strength 100 | App before: job `483afe83…` | App now: job `be18ae6f5795434e9ea92b2f38614854` (real UI) |
|---|---|---|---|
| Faces | 532 (455 quads, 77 triangles) | 209 quads | 204 quads |
| Guide path | 14 vertices, 0 turns | 15 vertices, **8 turns** | 11 vertices, 0 turns |
| Guide check | passes | **fails (turns)** | passes |
| Guide distance, 95th percentile / maximum / open ends | 0.141 / 0.192 / 0.537 h | 0.081 / 0.124 / 0.083 h | 0.043 / 0.064 / 0.134 h |
| Guide direction, 95th percentile | 14.5° | 26.7° | 12.7° |
| Old connected-path check (0.20 h, 30°) | passes | passes | passes |
| Rim row, 95th percentile / maximum / direction | 0.141 / 0.214 h / 9.9° | 0.047 / 0.076 h / 10.4° | 0.024 / 0.066 h / 7.7° |
| Crease rows realized | 3 of 3 | 3 of 3 | 3 of 3 |
| Rim witness point / largest along the edge | 0.001 / 0.016 h | 0.006 / 0.015 h | 0.008 / 0.010 h |
| Time | 1.1 s remesh | 141 s | 34 s |

Picture: `tests/registered-features/guide-native-1/zbrush-before-after.png`
(numbers beside it in `zbrush-before-after.json`). Native run:
`runs/native-rim-investigation/native-captures/guide/island6-guide-keep-creases-0.2k-guide100-b1/`
(owned batch process; `remeshsettings.txt` records `NumQuad=200`,
`CurvesStrength=100`, `KeepHardEdges=TRUE`; curve transfer code 0; scripts
`scripts/run_native_island6_guide.py` and `island6_guide_payload.py`).

The app's mesh passes every existing check: minimum angle 35.6°, edge ratio
3.06 at the 95th percentile and 4.60 at most, scaled Jacobian 0.55, count +2 %,
crease check 0.18 h and 0.20 h at the 95th percentile against 0.25 h. The cut
added 21 vertices and 42 triangles to the source, listed 22 guide edges, and
moved two source vertices onto the guide (0.003 h and 0.07 h).

Real UI (`tests/verify_registered_features_ui.py --case island6-200-guide`,
owned server and Chromium, no stubs): job `be18ae6f5795434e9ea92b2f38614854`,
204 quads, 45 s from Generate to done, export downloaded and identical to the
accepted file, reload restored the result, no page or network errors.
Screenshot `tests/registered-features/guide-native-1/ui-200-guide/island6-200-guide/result.png`.
`tests/audit_registered_features.py` re-read the exported OBJ and passed it,
guide loop included. The worker matrix produced the same bytes for the same
case (SHA-256 `48c6cea3…3d4c`). Two other UI attempts are retained: one failed
while loading the page with `net::ERR_NETWORK_CHANGED` and never reached
Generate (`ui-200-guide-network-changed/`); one passed with the same bytes
before five tracked files were restored to their LF line ends
(`ui-200-guide-before-line-ending-fix/`, job `69053ee1…`).

Worker matrix (`tests/verify_registered_features.py`, run `8a240b30812b`, code
stable, 8 of 8), against the crease-row matrix of 2026-11-09 (run
`182fbe2cc53e`):

| Case | Before | Now | Guide loop | Rows | Job |
|---|---|---|---|---|---|
| Island 6 / 150 | Rejected, 377 s | **143 quads**, 172 s | | 3 / 3 | `registered-8a240b30812b-island6-150` |
| Island 6 / 200 | 207 quads, 44 s | 220 quads, 94 s | | 3 / 3 | `registered-8a240b30812b-island6-200` |
| Island 6 / 200 + guide `483afe83` | 209 quads, 8 turns (job `483afe83…`, 141 s) | 204 quads, 38 s | 11 vertices, 0 turns | 3 / 3 | `registered-8a240b30812b-island6-200-guide` |
| Island 6 / 300 | 331 quads, 86 s | 308 quads, 84 s | | 4 / 4 | `registered-8a240b30812b-island6-300` |
| Island 6 / 750 + authored guide | 751 quads, 7 turns, 150 s | 798 quads, 84 s | 24 vertices, 0 turns, 2 at the guide's corners | 5 / 5 | `registered-8a240b30812b-island6-750-guide` |
| Island 2 / 300 | 291 quads | 291 quads, same bytes | | none admitted | `registered-8a240b30812b-island2-300` |
| Island 7 / 300 (closed) | 339 quads | 339 quads, same bytes | | 5 / 4, not enforced | `registered-8a240b30812b-island7-300` |
| Island 10 / 500 | 545 quads, 118 s | 559 quads, 68 s | | 6 / 6 | `registered-8a240b30812b-island10-500` |

Notes on the table:

- Island 6 at 150 is accepted for the first time (rows-wide pass, seed 2). No
  limit changed; the layouts did.
- The 750 case was accepted before with a guide path of seven turns. Its guide
  has two corners; the new mesh turns at those two and nowhere else.
- The same eight outputs, byte for byte, came from three runs: `8a240b30812b`
  (`matrix-4/`, the final tree), `98e1e95a0afe` (`matrix-3/`, before five
  tracked files were restored from CRLF to LF line ends; under other machine
  load, so slower) and `6cdbd2f8b7b4` (`matrix-2/`, seeds tried in two blocks
  of 32). Trying all 64 seeds in the first pass brought the test case from
  203 s to 38 s and island 6 at 150 from 88 s to 172 s.
- Unguided layouts are slower to find than on 2026-11-09 (island 6 at 200:
  seed 28 instead of seed 13). The search is deterministic and remains
  sensitive to small input changes.
- Run `22da534b1e62` (`matrix-1/`) is an intermediate state, kept as a failure:
  creases registered as mode 2, no corner rule, 6 of 8 (150 and 750 + guide
  rejected).

All 228 unit tests pass (197 before; 14 in `tests/test_native_guide_cut.py`,
17 in `tests/test_guide_rows.py`). `test_guide_rows.py` holds the regression:
the zig-zag mesh must fail on its turns, the native mesh must pass, and the
packaged engine must put a loop on a registered guide on a flat control.

Compact record with hashes: `engine/guided-quadriflow/development/guide-cut-verification.json`.
Evidence folder (git-ignored): `tests/registered-features/guide-native-1/`
(`matrix-4/` to `matrix-1/`, `ui-200-guide/`,
`crease-mode-trials/`, the engine patch and packaging scripts, the engine
parity record and a copy of the `size-caps-16` package).
