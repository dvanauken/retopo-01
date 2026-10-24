# Curved-surface quad solver

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
measured p95 guide distance is 0.01372 and tangent mismatch is 26.62 degrees;
the same-target unguided result measures 0.02988 and 89.31 degrees. The guided
mesh has a minimum corner angle of 42.31 degrees and minimum signed scaled
Jacobian of 0.588. These measurements refer to the retained regression output,
not a promise that every guide or requested density will succeed.

1. An owned Blender subprocess runs QuadriFlow on the current original mesh.
   Blender supplies quad connectivity, and does not receive a claimed guide API.
2. The adapter selects connected output-edge paths near the authored curves.
   Closed curves require simple cycles; open curves retain open paths. Conflicting
   guide ownership or unresolved paths reject explicitly.
3. A sparse local solve fits path vertices, neighboring quads and source-surface
   support points together. Significant curve corners survive target sampling.
   Signed corner Jacobians and edge ratios penalize folded or stretched quads.
4. Both directions of surface error, topology, vertex links, winding, quad shape,
   target count and each tracked guide path must pass before output is accepted.

The existing acceptance limits remain: at most 15% target-count error, minimum
30-degree corner angle, minimum 0.45 signed scaled Jacobian, maximum 6 edge ratio,
and the existing distribution limits. Surface error uses the same half-target-edge
length tolerance and deterministic bounded samples as the reference validator.
R-tree indexing accelerates nearest-triangle queries. The regression also calls
the unmodified reference validator against the downloaded OBJ.

Guide paths are measured at 257 uniform arc-length positions on the submitted
polyline, rather than weighting small source triangles more heavily because they
contributed more vertices. Their p95 distance must remain below 0.20 target edge
lengths and their p95 unsigned tangent mismatch below 30 degrees. The full
original submitted samples remain in `curves.json`. Both source and output are in
the existing source coordinate frame.

This route approximates curved detail; it does not freeze every sharp edge or
transfer arbitrary source attributes. Topology and bounded surface measurements
are not a complete self-intersection or Hausdorff certificate. Coarse targets and
overlapping or unresolved guides can still reject. Such candidates remain failed
and are never promoted to the result panel.

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
