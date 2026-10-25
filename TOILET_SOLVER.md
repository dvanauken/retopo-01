# Curved-surface quad solver

The exhaustive audit is still open. Dense testing of all five unique previously
accepted exports found surface-distance errors using the validator's ear
triangulation. With the viewer's fan triangulation, two exceed the same limit;
the other three pass that dense proximity test. A separate shared-vertex face audit found
two overlapping face pairs in each of the shorter two-guide, bowl-only and
unguided outputs. Independent linear programs confirmed points strictly inside
both triangles for all six reported pairs. The previous non-adjacent crossing
screen excluded these pairs. See `tests/toilet-dense-surface/`,
`tests/toilet-adjacent-contacts/` and `TOILET_TEST_PLAN.md`.

The longer captured bowl-plus-lid guide network also remains a failing regression
at 1,800 quads. Rejecting its candidate is correct failure handling, not a solved
retopology case. The implementation still needs stronger fitting and acceptance
checks; old green checks and the UI's quality label are not exhaustive geometry
qualification.

Acceptance now checks adjacent contacts, permitting only the actual shared
topological boundary. Adaptive subdivision also bounds distance over entire
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

The original bowl guide at target 1,800 generates 1,923 quads. Its independently
measured guide distance and tangent mismatch improve over an unguided solve.
Current measurements and independently reread OBJ evidence are retained in
`tests/toilet-retopology/result.json`. These results do not promise that every
guide or requested density will succeed.

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
Only shared topological vertices/edges permit contact. It uses the renderer's fan
triangulation and floating-point tolerances, not exact symbolic predicates.
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
failure persistence and a Circle drawn on the lid. The longer guide regression
currently makes this suite exit nonzero. Historical candidates accepted before
the crossing check are retained under `tests/toilet-stress/pre-intersection-check/`
and are explicitly superseded. Run `python tests/test_surface_intersections.py`
for the geometric detector controls.
