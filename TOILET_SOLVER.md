# Curved-surface quad solver

The latest adaptive repair also solves the captured source-projected 0.001-unit
paired-guide perturbation: a fresh service request produces 1,845 quads in
462.75 seconds. Its exported OBJ passes the independent geometry and all-mixed
diagonal contact audits under the `surface-only` labels. If guide checks already
pass when joint repair starts, fitting doubles the guide-distance weight and
omits the extra tangent-tail penalty while repairing surface accuracy. The
ordinary tangent objective remains. Inputs with failing guide checks retain
the earlier settings. Sixty numerical checks reproduce the prior long/bowl/short
results and the perturbed candidate; thirteen acceptance controls pass on the
exact applied modules. Source geometry and acceptance limits are unchanged.
Browser verification is recorded separately from this service result.

The first adaptive browser run reached the unchanged 600-second service limit.
Its idle software renderer consumed about ten logical CPUs in the recorded
sample. The viewport now renders on geometry, guide, camera, display or size
changes and through camera damping, then stops when idle. Fourteen actual-draw
and viewport-pixel checks pass. This also exposed an error-dialog focus race:
the displayed incident is now removed from the pending queue before opening,
so closing it cannot re-display that same incident during focus restoration.
All 130 native toilet editing and 18 selection/repeated-use checks pass on the
final app. Both the timeout and intermediate dialog failures remain retained.
The new full generation run under `surface-only-demand` passes seven checks:
1,845 quads in 480.15 seconds, visible accepted geometry and a native OBJ download.
All ten sampled test processes exit. The browser adds one projected sample to a
0.04109-unit polyline segment while preserving all authored points. Its mesh
therefore differs from the service-only export. Both independent audits of this
actual browser download pass under `surface-only-browser`; the failed exact-
identity comparison is retained separately. The final rendering suite passes
eighteen checks, including navigator/dock resizing and ribbon collapse/expansion.

Coarse targets 150/600 and paired target 1,799 remain unsolved. Extra layout
seeds and a stronger edge-ratio objective still produce face overlaps. The raw
150-face-target layout also has two triangular boundary loops. Bridging all
three cyclic correspondences restores closed Euler-0 connectivity, but every
fitted candidate fails contacts. This experiment does not change production
connectivity. Failed candidates and preliminary harness errors are retained
under `tests/toilet-objective-controls/`, `tests/toilet-layout-failures/`,
`tests/toilet-layout-inventory/` and `tests/toilet-boundary-bridge/`.
The additional 1,799-target seed-5 experiment avoids contacts but still fails
guide/surface requirements after three joint passes; it is also rejected.

The exhaustive audit is still open. The captured bowl-only, shorter paired-guide
and longer paired-guide inputs now produce 1,845 quads at target 1,800 through
the real HTTP service and worker, under unchanged acceptance limits. The latest
long-guide request took 310 seconds; its result is retained in
`tests/toilet-sampled-worker/joint-integrated/`. Earlier bowl/short requests took
213/294 seconds in `tests/toilet-sampled-worker/integrated-fallback/`.
Every solve uses a fresh layout, the original source and submitted guides.
No saved candidate participates in production generation.

The joint repair fits guide alignment and surface accuracy together after the
ordinary sampled passes fail. Rejected full-surface witnesses become barycentric
triangle constraints in later local fits. Each proposal must preserve every
already-passing guide and directional surface check; shape and contact checks
always apply. Eight local passes bound this fallback. The final result still
requires the ordinary complete acceptance checks. The numerical module exactly
reproduces the independently audited experiment, while its default settings
reproduce the prior bowl/short candidates exactly. See `tests/surface-guide-joint/`
and `tests/surface-guide-refine/detached-joint-defaults/`.
The actual long-guide worker OBJ also passes both independent audits under
`tests/toilet-fresh-geometry/joint-integrated/` and
`tests/toilet-all-diagonal-audit/joint-integrated/`.
A fresh browser solve also displays the accepted long-guide mesh and downloads
the identical independently audited OBJ. The Circle control passes in the same
browser session. All thirteen workflow checks pass; the ten sampled test-owned
processes are gone after exit. See `tests/toilet-fallback-browser/joint-integrated/`.
The long browser job took about 494 seconds (488 seconds displayed for solving) with a CPU-intensive headless
software renderer; this is separate from the 310-second service-only observation.
Cancellation during actual joint repair passes eleven checks: the worker and
its descendants stop, unfinished exports remain unavailable, and the service
admits a fresh request. Evidence is in `tests/toilet-fallback-cancel/joint-integrated/`.

Before joint integration, guide reversal, order changes, densification and a
rotated closed-guide start all generated independently qualified results.
A small paired-guide perturbation failed surface accuracy, and target 1,799
failed contacts. Unguided targets 150/600 remain unsolved. These failures are
retained as failures; passing rejection checks does not qualify their geometry.
At the earlier `b63828f` checkpoint, the small perturbation still failed, reaching
the existing 600-second service limit during joint pass seven. Its retained
trial history shows a surface-bound/guide-distance tradeoff. This is a runtime
and robustness failure retained as historical evidence. The adaptive service
result above now resolves this specific input.
The paired-guide target 1,799 rerun still rejects face overlaps after about
265 seconds. Joint repair refuses that intersecting starting mesh. Neither
failed request leaves a live worker/Blender process or a downloadable result.

Both actual worker exports pass the independent reference/dense/LP/BVH/path
audit and all mixed-diagonal contact checks under the `integrated-fallback`
labels in `tests/toilet-fresh-geometry/` and `tests/toilet-all-diagonal-audit/`.
A fresh browser generation of the short case displays the mesh and downloads
the exact same OBJ. Its 500-second solve ran with heavy headless software-renderer
CPU load, recorded separately in `tests/toilet-fallback-browser/integrated-fallback/`.
This is a successful workflow observation, not an interactive performance benchmark.
The Circle browser control also reproduces its existing qualified export.
Cancellation during actual sampled fitting passes all 11 scoped checks under
`tests/toilet-fallback-cancel/worker-owned/`, including worker/descendant cleanup
and unavailable result downloads.

Earlier, the warpage correction produced
three fresh, independently checked toilet results at target 1,800: unguided
(1,923 quads), lid guide (1,782), and a Circle guide on the lid (1,782). Each
export passes the unchanged shape/topology limits, adaptive surface bounds for
both diagonals, dense independent proximity checks, and separate face-contact
tests. See `tests/toilet-fresh-geometry/unguided-warpage/result.json` and
`tests/toilet-fresh-geometry/guided-warpage/result.json`. This qualifies these
specific inputs; the later bowl/short-case improvement is recorded above.

An isolated fresh-source pipeline now qualifies the captured **shorter two-guide
case** at 1,800: a newly generated seed-2 layout, distributed guide fitting and
local repair around measured surface failures produce 1,845 quads. The actual
export passes independent reference, dense surface, topology, shape, guide,
LP/BVH and all-mixed-diagonal audits. Its OBJ exactly matches the earlier
retained-layout repair (`4c0c434ecbb80901851e5edc72d69f4a68660c253a92adf667bca3540712b9c9`).
See `tests/toilet-fresh-witness/fresh-short-seed2/` and the
`fresh-short-seed2-export` independent audits. This is an experimental pipeline,
not the production worker. The new production fallback reproduces its exact
coordinates and faces; its OBJ header differs because it uses the ordinary
worker exporter. Input-variation regressions remain required; the final lid-guide
distance has only about 1.3% margin.

Fresh Circle, reversed-lid and perturbed-Circle runs under the final mixed-
diagonal gate also pass independent exported-geometry checks in
`tests/toilet-fresh-geometry/all-diagonal-generations/` and
`tests/toilet-all-diagonal-audit/fresh-new-gate/`. The earlier perturbed Circle
export is explicitly disqualified; the corrected gate allows the solver to
continue to a valid candidate. Unguided targets 1,200 and 1,799 pass the retained
audits, while 150 and 600 fail. These are finite tested cases.

Additional isolated fresh-layout experiments with seeds 2/3 fail all three
captured complex-guide inputs for both seeds. Their initially contact-free layouts
fold during fitting. Pin-target assignment requires substantial movement along
the curve, so a separate experiment replaces fixed pins with nearest-curve
residuals plus a weak positional anchor. Four passes avoid contacts, but all five
miss guide-fit limits and the last intersects. Neither experiment is integrated.
See `tests/toilet-layout-seeds/` and `tests/toilet-sliding-pins/`. More layout seeds
alone have not solved the reported bowl/combined-guide failure.

An isolated tangent-alignment residual added to sliding pins now produces a
bowl-only candidate on retained seed 2 that passes the unchanged gates after
four passes. Its exported OBJ also passes the independent surface, guide,
topology, quality, LP/BVH and all-mixed-diagonal checks. This is experimental
output, explicitly labeled separately from a service-generated result. Production
at that checkpoint used its existing fitter and seeds 0/1. Both captured combined-guide inputs
were also tested: all ten refinement passes fail guide alignment. The last long
case reaches tangent p95 values of 30.75 and 31.31 degrees, above the unchanged
30-degree limit. Some shorter-case passes also fail surface checks. None is
accepted by that experimental fitter. See
`tests/toilet-tangent-pins/bowl-seed-2-weight-8/` and the `tangent-bowl-seed2`
independent audit reports.

Repeating the isolated experiment at tangent weight 12 also qualifies the bowl
candidate independently (p95 distance 0.00901, tangent angle 27.77 degrees).
Both combined-guide cases still fail all five passes each. Their final tangent
values remain above 30 degrees, and the shorter case also misses the surface
screen. These outputs are retained in `tests/toilet-tangent-pins/` and the
`tangent-captured-seed2-weight12` independent reports. Neither midpoint-based
experimental variant is used by the production fitter.

An isolated distributed-path objective replaces midpoint alignment with 401
arc-spaced point-to-edge and tangent residuals. The ordinary 257-sample acceptance
metric remains unchanged. Bowl-only passes after two refinement passes. Both
guides in the shorter combined case now align, but full surface bounds reject
the resulting distortion. The longer combined case still misses its lid tangent
limit. See `tests/toilet-sampled-paths/captured-seed2-401/`. This isolates surface
support as a remaining issue for the shorter case; it does not make that mesh a
qualified result or change the production fitter.
The distributed-path bowl export also passes the independent surface, guide,
quality, topology and LP/BVH checks and the all-mixed-diagonal contact audit in
the `sampled-path-401` reports. It remains an isolated experiment.

Fitting additional source triangle-centroid support independently against both
quad diagonals introduces contacts in all 15 captured-case attempts. Excluding
support pairs with opposing normals also leaves contacts in all 15 attempts.
These experiments are rejected, including candidates whose sparse distance
screen passes. More support points and this normal filter alone do not solve
the combined-guide cases. See `tests/toilet-both-diagonal-support/` and
`tests/toilet-oriented-support/`.

The successful local repair moves only the two face rings around actual full-
surface failure witnesses. Four full steps are rejected because they exceed the
lid-guide distance limit; each half step preserves shape, contacts and both guide
limits while reducing the observed surface error. The fourth half step also
passes complete adaptive bounds. The earlier global-support experiments remain
rejected. Before the joint correction, the longer guide had tangent p95 32.47 degrees and full surface
failures under both diagonals. Re-selecting paths at its fitted positions returns
the same chains. Independent per-edge direction fits suggest remaining tangent
freedom, but those directions need not be realizable by shared mesh vertices;
they are diagnostics, not a qualified mesh.

Dense testing of all five unique previously
accepted exports found surface-distance errors using the validator's ear
triangulation. With the viewer's fan triangulation, two exceed the same limit;
the other three pass that dense proximity test. A separate shared-vertex face audit found
two overlapping face pairs in each of the shorter two-guide, bowl-only and
unguided outputs. Independent linear programs confirmed points strictly inside
both triangles for all six reported pairs. The previous non-adjacent crossing
screen excluded these pairs. See `tests/toilet-dense-surface/`,
`tests/toilet-adjacent-contacts/` and `TOILET_TEST_PLAN.md`.

The longer captured bowl-plus-lid guide network was also a failing regression
at that checkpoint. Its later accepted result is described at the top of this
document and has new independent export audits. The old rejection records and
UI quality labels are not evidence that those earlier candidates were valid.

Acceptance now checks adjacent contacts, permitting only the actual shared
topological boundary. It tests every triangle pairing from either quad diagonal,
including mixed choices on neighboring quads. A perturbed Circle exposed contacts
that were absent under the renderer's fan; independent LP witnesses and a mixed-
diagonal analytic control are retained. Adaptive subdivision also bounds distance over entire
triangles, in both directions and with either quad diagonal. Unresolved work or
depth budgets reject. All five historical exports fail these combined checks;
`tests/toilet-acceptance-audit/result.json` retains the individual witnesses.
These changes prevent false acceptance; they do not repair the fitted mesh.
Fresh-solve outcomes are recorded separately in `tests/toilet-strict-generation/`.

The shorter captured two-guide network and the bowl-only example generated
1,923-quad results accepted by the earlier bounded checks. Their denser audits
now fail as described above. The two-guide density sweep also records rejected
1,200-, 600- and 150-quad requests. A successful failure-handling assertion is not
a successful mesh solve.

The original toilet import was valid, but the recovered reference route failed.
Its second coalesced subdivision created a triangle whose three distinct vertices
were exactly collinear. The retained failing run is under
`tests/toilet-source/solver-attempt/`. Source validation alone never established
that the toilet could be remeshed.

The toilet now explicitly selects the engineering `surface-quads` solver.
`curved_quad.py` accepts actual closed source geometry and submitted guides; it
contains no model IDs, saved output lookup or toilet-specific shape construction.
The recovered engine files remain unchanged.

The historical bowl result in `tests/toilet-retopology/result.json` is superseded
by the stronger audits. Its earlier guide-fit improvement does not qualify that
mesh under the current surface and intersection requirements.

1. An owned Blender subprocess runs QuadriFlow on the current original mesh.
   Blender supplies quad connectivity, and does not receive a claimed guide API.
2. The adapter selects connected output-edge paths near the authored curves.
   Closed curves require simple cycles; open curves retain open paths. Conflicting
   guide ownership or unresolved paths reject explicitly.
3. A sparse local solve fits path vertices, neighboring quads and source-surface
   support points together. Significant curve corners survive target sampling.
   Signed corner Jacobians and edge ratios penalize folded or stretched quads.
   Local movement barriers in both surface directions prevent tangent-plane
   fitting from drifting too far sideways off curved areas.
   A signed quad-warpage residual reduces the surface difference between the
   two triangulations of a nonplanar quad; it does not loosen their final bounds.
4. Both directions of surface error, topology, vertex links, winding, quad shape,
   target count, face contacts and each tracked guide path must
   pass before output is accepted.

The existing acceptance limits remain: at most 15% target-count error, minimum
30-degree corner angle, minimum 0.45 signed scaled Jacobian, maximum 6 edge ratio,
and the existing distribution limits. Surface error uses the same half-target-edge
length tolerance as the reference validator. Its deterministic samples remain
an inexpensive rejection screen, followed by adaptive whole-triangle bounds for
both quad diagonals. R-tree indexing accelerates nearest-triangle queries. The regression also calls
the unmodified reference validator against the downloaded OBJ.

Guide paths are measured at 257 uniform arc-length positions on the submitted
polyline, rather than weighting small source triangles more heavily because they
contributed more vertices. Their p95 distance must remain below 0.20 target edge
lengths and their p95 unsigned tangent mismatch below 30 degrees. The full
original submitted samples remain in `curves.json`. Both source and output are in
the existing source coordinate frame.

This route approximates curved detail; it does not freeze every sharp edge or
transfer arbitrary source attributes. Topology and surface proximity are separate
from self-intersection. Coarse targets and
overlapping or unresolved guides can still reject. Such candidates remain failed
and are never promoted to the result panel. The new intersection screen uses
indexed polygon bounds and triangle contacts, including shared-vertex face pairs.
Only shared topological vertices/edges permit contact. Curved-surface acceptance
uses both possible quad diagonals and every mixed triangle pairing; the detector's
default mode remains the renderer's fan for other callers. Predicates use
floating-point tolerances, not exact symbolic arithmetic.
An additional Blender BVH check independently checks candidate pairs. The
original imported source itself has four detected non-adjacent triangle contacts;
its geometry has not been silently rewritten to remove them.

Failures and cancellations remain visible in the result area, including after
switching views or reloading. A failed replacement keeps the previous accepted
mesh and labels it explicitly. An empty result pane has no floating guide
overlay. Unsupported source-relative target buttons are disabled; out-of-range
typed or persisted targets cannot silently change the request to 1,800.

Blender is already installed on this host. On another machine install Blender,
place `blender` on PATH, or set `RETOPO_BLENDER` to its executable before starting
the server. The standard Windows installation directory is also discovered.
Python dependencies include the pinned R-tree package in `requirements.txt`.
Blender runs hidden and is a descendant of the owned worker; cancellation and
timeouts terminate that process tree.

Run `python -X utf8 tests/verify_toilet_retopology.py` for real Chromium Generate,
OBJ download and independent geometry validation, an unguided comparison, a
different open-guide solve, rejected input and child-process cancellation.
Evidence, output geometry and screenshots are in `tests/toilet-retopology/`.
`python -X utf8 tests/verify_toilet_source.py` independently checks the unchanged
physical source against the original decoded Draco asset.

Run `python -X utf8 tests/verify_toilet_stress.py` for both captured guide sets,
repeatability, density changes, real browser retry/cancel/export, guide save/load,
failure persistence and a Circle drawn on the lid. Its retained historical run
exited nonzero for the longer guide; the new joint-worker/browser reports cover
the corrected input separately. Historical candidates accepted before
the crossing check are retained under `tests/toilet-stress/pre-intersection-check/`
and are explicitly superseded. Run `python tests/test_surface_intersections.py`
for the geometric detector controls.
