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
