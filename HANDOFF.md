# Handoff: retopo-1 low-count open parts and the island 6 rim

Written 2026-11-09 for the next agent (Fable 5.2). It covers the state left on
the night of 2026-10-28. Read it fully before changing solver code.

**Update, 2026-11-09 evening:** the island 6 rim (section 4.1) is fixed for open
parts. Sections 3, 4.1, 4.2, 4.3, 5, 6 and 7 are updated for that work; the
rest is as first written.

**Update, 2026-11-10:** authored guides on open parts are now cut into the
source and followed by one continuous edge loop, as ZRemesher does at Curves
Strength 100 (new section 4.0). The layout engine was rebuilt
(`constrained-edges-18`). Island 6 at 150 is accepted for the first time.
Sections 3, 4, 5, 6 and 7 are updated for that work.

**Update, 2026-11-10 (later):** with "Add faces where the shape needs them"
checked, the faces at short crease chains are now sized so each chain carries
an edge row, and corner zones are measured (new section 4.00). Island 6 at
200 + guide returns 436 quads whose feet follow the source better than
ZBrush's 532 faces do. When no layout works at the target's face size the
base faces are made smaller in steps (750 + guide: 1,848 quads). The layout
engine was rebuilt (`constrained-sizes-19`).
The user committed the earlier work as `0ed67c2 WIP`; this work is uncommitted
on top of it.

## 1. What this project is

retopo-1 is a local retopology app: an HTML canvas UI (ES modules, vendored
Three.js) over a Python solver process (`server.py` → `worker.py`).
Topology comes from a modified QuadriFlow child process,
`engine/guided-quadriflow/quadriflow.exe`. The NumPy/PyTorch side fits,
repairs and checks the result. The goal is to match ZBrush ZRemesher's behavior.
The rules come from native code recovered in the Ghidra workbench
`C:\dbva\code\ghidra-workbench`. The test asset is the SketchUp toilet, split
into 11 original parts. Islands are addressed as part ids `skp-N`, loaded with
`mesh_parts.load_part`.

Start the app with `.\start.cmd` (normally http://127.0.0.1:8741). Running
`start.cmd` again restarts this checkout's server. The user may already have it
open: keep their origin and browser storage.

## 2. How the user wants the work done

These preferences are firm. Each one came from a correction.

1. **Do the work, don't propose it.** For hard solver problems, investigate end
   to end: read workbench evidence, decompile or trace native code, run native
   ZBrush as a reference, implement, and verify in the real UI. Lead with
   results and evidence. Ask only about real product or policy decisions, never
   "which step should I start?". Native runs and Ghidra reading are authorized.
2. **No invented constants.** Before changing the solver, read the relevant
   recovery documents under the workbench's `targets/zbrush/understanding/**`
   and the `recovered_*.py` arithmetic. Then implement the native rule with its
   constants and evidence level. If no native rule exists, say so and label the
   constant as an engineering choice. Threshold patches drew the reaction
   "Are you creating hacks?".
3. **Tolerances are in faces.** Acceptance limits are measured in units of the
   requested face size h, and maxima stay at face scale (½–1 face). Never cap a
   limit by model size. The user's words: "The limit should be a single face…
   why can't the mesh reduce to the number of faces that we ask for. It can."
   Low counts must work.
4. **Report honestly.** Retain failed candidates as failures. Never present a
   diagnostic mesh as an accepted result. Say what is and is not claimed. The
   existing docs follow this style closely; keep it.
5. **Never delete `runs/` folders by time window.** The user generates jobs from
   the same UI while you work. Delete only job ids that your own scripts printed.
   List the deletion set before deleting. An earlier session deleted the user's
   job `e2a47eb8` and the island 6 source folder `runs/60e34fcd…` this way.
6. UI work follows `C:\dbva\code\web-component-II` for look and feel (see the
   user's global `CLAUDE.md`). The workbench has its own `AGENTS.md` and
   `DESIGN.md` for anything written there.

## 3. Current state of the repository

- Branch `crease-rows`. Last commit `0ed67c2 WIP` (by the user, 2026-11-10):
  the guide work (section 4.0) and the first "Add faces where the shape needs
  them" option. Git works now; a previous session reported a "dubious
  ownership" refusal. If it returns, use `git -c safe.directory=* …`.
- **Uncommitted:** the corner work of 2026-11-10 (section 4.00). The user asked
  that the agent not commit.
  - `corner_zones.py` (new): the corner-zone measure.
  - `crease_rows.py`: `local_sizes`, and `sizes` through the band rule, the
    row chains, `find_row`, `measure_path` and `measure`.
  - `source_features.py`: `measure(..., extra_faces=)`, `band_widths(..., sizes)`.
  - `open_surface.py`: local sizes, sized constrained edges, corner zones,
    fewest-faces-first search with extra faces, boundary early exit.
  - `registered_features.py` (`constrained(..., sizes)`), `feature_refine.py`
    (`feature_sizes`), `quad_connectivity.py` (`fill_triangle_holes` no longer
    loops), `worker.py`, `job_diagnostics.py`, `app.js`, `index.html`,
    `src/view/PartsWorkspace.js` (accepted outputs show mesh edges in the
    assembly view).
  - `open_surface.process_layout`: one layout from the engine's file to its
    outcome, run in three other processes for rows layouts.
  - `engine/guided-quadriflow/` (`quadriflow.exe`, `source.zip`,
    `manifest.json`): build `constrained-sizes-19`.
  - `tests/test_corner_zones.py`, `tests/render_corner_case.py`,
    `tests/fixtures/corner_zones/`, `tests/fixtures/quad_connectivity/`,
    additions to `tests/test_crease_rows.py` and `tests/test_quad_connectivity.py`,
    `tests/verify_registered_features.py` (corner zones in the result),
    `tests/verify_registered_features_ui.py` (`--extra-faces on|off`),
    `tests/audit_registered_features.py` (extra-faces jobs, corner zones),
    `tests/verify_assembly_output_edges.py` (new).
  - `GUIDED_LAYOUT.md`: section "Corner rows and corner zones with extra
    faces". `HANDOFF.md`. `tests/extra-faces/corners-1/` (evidence).
  - `engine/guided-quadriflow/development/corner-rows-verification.json`.
  - In the workbench (its own repository, also uncommitted):
    `work/retopo-guided-layout/QuadriFlow/src` now holds the
    `constrained-sizes-19` sources, `build-records/constrained-sizes-19` is
    new, and `work/retopo-lowcount/AUDIT.md` has a section 10.
- **Committed in `0ed67c2`:** the guide work of 2026-11-10 (section 4.0).
  - `native_guide_cut.py` (new): the recovered ZRemesher guide cut.
  - `guide_rows.py` (new): the guide check (one loop, no turns, corner rule).
  - `registered_features.py`: `constrained()` builds the cut source and the
    one constrained-edge list; the old `prepare()` cuts natively too.
  - `open_surface.py`: constrained-edge rows layouts, guide screening and
    fitting, 64 seeds; the 1e-6 lift (`write_row_guides`) is gone.
  - `worker.py`, `job_diagnostics.py`: the guide check enforced and reported.
  - `engine/guided-quadriflow/` (`quadriflow.exe`, `source.zip`,
    `manifest.json`): build `constrained-edges-18`.
  - `tests/test_native_guide_cut.py`, `tests/test_guide_rows.py`,
    `tests/render_guide_case.py`, `tests/fixtures/guide_rows/`,
    `tests/fixtures/island6-guide-483afe83.json`.
  - `tests/verify_registered_features.py` (case `island6-200-guide`),
    `tests/verify_registered_features_ui.py`, `tests/audit_registered_features.py`.
  - `GUIDED_LAYOUT.md`: section "Guides cut into the source". `HANDOFF.md`.
  - `engine/guided-quadriflow/development/guide-cut-verification.json`.
  - In the workbench (its own repository, also uncommitted):
    `work/retopo-guided-layout/QuadriFlow/src` now holds the
    `constrained-edges-18` sources, `build-records/constrained-edges-17` and
    `-18` are new, and `work/retopo-lowcount/AUDIT.md` has a section 9.
- Tests: run `python -X utf8 -m unittest discover -s tests -p "test_*.py"`. It
  runs 256 tests (228 before the corner work, plus 11 in
  `test_corner_zones.py`, 16 in `test_crease_rows.py` and 1 in
  `test_quad_connectivity.py`) and all pass.
  The old error, a Windows file-lock race in `test_server_startup` tearDown
  (`startup.log` still open), is fixed in the test's cleanup: it now retries
  the folder removal for up to ten seconds. `runs/startup test njeowui_` and
  `runs/startup test my8m2y14` are left over from before that fix.
- Packaged engine: build `constrained-sizes-19`, SHA-256 `a8c12832…cff6`
  (details in `GUIDED_LAYOUT.md` → "Corner rows and corner zones with extra
  faces" → "The engine build"). It is `constrained-edges-18` plus an optional
  face-size cap per constrained edge (fourth column of the list, read with
  `-size-caps`) and returns the same bytes as `constrained-edges-18` when no
  cap is listed (eight controls). `constrained-edges-18` (`c8aa1823…05de`) is
  `size-caps-16` plus the `-constrained-edges` flag (five controls).
  It needs MinGW DLLs from `C:/msys64/mingw64/bin` or `RETOPO_MINGW_RUNTIME`.
  Hashes are checked at run time. The previous packages are kept in
  `tests/extra-faces/corners-1/engine-constrained-edges-18/` and
  `tests/registered-features/guide-native-1/engine-size-caps-16/`, and in Git.
  The 2026-10-28 path-provenance engine in `development/` is still opt-in only.

## 4. Open issues, in priority order

### 4.00 Chunky corners with extra faces (fixed for island 6 at 150 to 750, 2026-11-10)

User-visible symptom: with "Add faces where the shape needs them" checked,
island 6 at 200 + guide came back with 380 quads and the two back corners
(where the lip turns down into a foot) as a few large folded faces. Corner
zone (source y > 0.05), source to output: 0.279 h at the 95th percentile and
0.407 h at most; ZBrush 0.246 / 0.304 h with 532 faces.

**Status.** The same case returns 436 quads, 0.116 / 0.257 h, 18 crease rows
(14 in the feet), one guide loop of 14 vertices without turns, in about 40 s
from the real UI (job `f7e5032ec7854a8a827d2183e2fdc4cc`). Full account, the native-rule
table, limits and evidence: `GUIDED_LAYOUT.md` → "Corner rows and corner zones
with extra faces". In short:

- **Local faces.** `crease_rows.local_sizes`: the face at a crease chain is
  its extent / 2, between a floor (1/4, and at least half the native minimum
  feature length S) and the requested face. Band rule, two-face minimum and row
  limits use that face. The sizes reach the engine as face-size caps on its
  constrained edges. This stands in for native's one-cell separation of
  constrained lines (`0x28fe70`), which this engine does not have.
- **Corner zones.** `corner_zones.py`: source vertices within one face of a
  cluster of crease junctions, measured to the output; 0.25 h at the 95th
  percentile, 0.5 h at most. Enforced with extra faces, reported (job log,
  toast, Checks tile, Details) at the strict count.
- **Until it works.** The user's rule: checking the box is permission to raise
  the count until the rows and corners work. When the layouts at the target's
  face size are used up, the base faces are made smaller in steps (1.5 and
  2.25 times the faces; the checks stay those of the target). Only when the
  steps run out of time does the result fall back to the rows of the strict
  count with the corners reported, so checking the box never returns less than
  leaving it unchecked.
- **Strict count.** It cannot follow the feet at 200. Its whole search with
  the corner check enforced (122 layouts, 21 candidates reaching the checks)
  has none under 0.32 h on the worse foot; the limit is 0.25 h. Every strict
  island 6 result from 150 to 750 is over the corner limits and says so.

What is still open here:

- **Time.** "Until it works" lives inside the 420 s solver budget: 200 s at
  the target's face size, then steps until 300 s, then the last resort. Island
  6 at 750 + authored guide takes about 150 s (second step, 1,125 base faces;
  230 s one layout at a time). A part that needs a third step ends in the last
  resort with coarse corners reported.
- **Speed.** Rows layouts are processed three at a time and taken in plan
  order, so results are the same bytes as one at a time. Gains are up to 1.8
  times on cases that go through several layouts and nothing on a case whose
  first fitted layout passes. What is left is mostly the engine laying out 64
  seeds per step and the fits of one layout following one another. The engine
  guaranteeing rows and loops (the native integer solve, section 4.1) would
  remove the search itself.
- **Counts.** With extra faces island 6 returns 421 / 466 / 436 / 655 / 1,848
  quads for 150 / 200 / 200 + guide / 300 / 750 + guide. ZBrush returns 374 and 532 for 200 and
  200 + guide. The faces go to the feet and the front lip.
- **Long parallel creases are still one band** (rim wall 0.24 h, back step
  0.3 h). ZBrush keeps both creases of each with thin quads between; its mesh
  fails this application's shape limits. Shape-policy question (section 4.5).
- **A chain exactly two local faces long is all end zone**, so only the
  one-local-face end limit applies to it. ZBrush passes the chain up the back
  of each foot at 0.24 h that way.
- **Seed search.** 14 layouts tried, one fitted, on the test case; 300 needs
  about 160 s. The engine still guarantees nothing.
- **Other parts were not run with extra faces.** Closed parts ignore the option.

### 4.01 Targets above 1,500 fail on island 6, in both modes (1,500 fixed 2026-11-13)

User-visible symptom: job `5a80a3ff627b4ceb95bf9534075a065c` (island 6, target
7,200, box checked): "The mesh calculation exceeded the ten-minute limit."

**Fixed:** the stall. With extra faces all 64 seeds were laid out before any
was tried; at 7,200 a layout takes 55 s, so nothing was ever tried. The
up-front layout now stops after 60 s and no batch is started that cannot
finish inside the budget. The case ends at about 430 s with a rejection.

**Fixed since (2026-11-13):** 1,500 passes in both modes and is a regular
verification case (`island6-1500`): 1,557 quads unchecked (a 3,000 layout
thinned by strip collapse), 2,998 quads with the box checked (first
smaller-base step, 28 of 28 rows, corners enforced). Three changes: the
boundary fit is repeated while the boundary check would fail
(`conform_boundaries`), the last resort with extra faces starts with the
thinned layouts, and a step starts no batch it cannot finish before its own
deadline. Island 10 at 500 now returns 442 quads instead of 559 (a layout that
failed only its boundary now passes and comes first).

**Not fixed:** 3,000 (box checked, 427 s) and 7,200 (both modes) are rejected.
Measured before these fixes: 1,500 and 7,200 rejected
with the box checked and unchecked; 150 to 750 pass. Full account:
`GUIDED_LAYOUT.md` → "High targets: what fails, and what was fixed". In short:

- Parallel creases that share a row at 200 (rim wall, back pair, step) are
  0.66 to 0.82 of a face apart at 1,500 and 1.45 to 1.8 at 7,200. Each then
  needs its own row, the gap is not a whole number of faces, and the engine
  gives the pair one row. Native separates such lines in its integer solve
  (`0x28fe70`); this engine has no such step. Same gap as section 4.1's
  "parameter chart and combined solve".
- The row direction limit failed short curved chains at 7,200 even with the row
  within 0.15 of a face of its crease. **Fixed 2026-11-13: that was the
  measure** (a chain corner charged to the row; `crease_rows.measure_path`).
  ZBrush's own meshes at 1,500 / 3,000 / 7,200 fail this application's row,
  corner and shape checks too (`GUIDED_LAYOUT.md` → "ZBrush at high counts").
  Island 6 at 200 with the box checked now returns 445 quads instead of 466.
- Unchecked at 1,500 is the nearest miss: a thinned 3,000 layout has all 20
  rows and fails only the boundary check, 0.119 h against 0.1 h.
- Sizing faces to the pair gap (extra faces) was tried and removed: it fixed
  the back pair, not the rim, and no case passed.
- **Decided by the user (2026-11-13): no stand-in.** Do not imitate the
  native separation inside QuadriFlow (pinned rows plus sizes). The plan is
  ZBrush's actual pipeline for open parts: the recovered parameter chart and
  integer solve (workbench `targets/zbrush/understanding/guided/`), extended
  to boundaries by recovering native's boundary branches (Ghidra project
  `ghidra-projects/zbrush/ZBrushengine.gpr`, tracer
  `runs/native-rim-investigation/native-captures/scripts/trace_native_rim_parameter_v3.py`).
  Expect weeks; the outcome is not promised.
- **Progress (2026-11-13):** stages 1 to 9 of 17 run on open sources and
  match ZBrush byte for byte on island 6 from the original packet alone:
  densification, hard edges from the packet's crease flags, locked
  conditioning, the 78 hard-edge guide paths and the adjacency cleanup, ending
  in the 11,332-vertex source ZBrush computes its field on; and stages 6 to 8,
  the field production and the angular solve, whose solved angles and quarter
  transitions are byte-identical to ZBrush's. New modules only (`recovered_open_*.py` in the workbench, entries
  `recovered_open_guided_source.prepare`, `recovered_open_guide_field.prepare`).
  Stage 9 (30 singular seeds) and the cut connector of stage 10 (166 cut
  edges) are exact too. Next: what ZBrush does to that cut before flattening
  (`0x304d40`; its final cut has 238 edges), then stages 11 to 17. Status,
  captures and recovered rules in workbench
  `targets/zbrush/understanding/guided/OPEN_SOURCE_PORT.md`.

### 4.0 Guides were not cut into the source (fixed for open parts, 2026-11-10)

User-visible symptom: job `483afe83c71d40d2858066813a3f553a` (island 6, target
200, one guide). The guide only steered the field; the fitter dragged a
zig-zag edge chain onto it (8 of 13 inner vertices turn onto another loop) and
the guide check accepted it.

**Status.** The same case now returns 204 quads with one 11-vertex loop on the
guide, no turns, 0.04 h from the guide at the 95th percentile, in 34 s from
the real UI (job `be18ae6f5795434e9ea92b2f38614854`). The old output fails the
new check on its turns alone. Native ZBrush with the same guide at strength
100 gives 532 faces (77 triangles) with a 14-vertex loop at 0.14 h. Full
account, the native-rule table, limits and evidence: `GUIDED_LAYOUT.md` →
"Guides cut into the source". In short:

- **Cut.** `native_guide_cut.py` ports the recovered chain: projection,
  classification, direct paths, walk, fallback, 5 % relocation (it moves
  source vertices), inward repair, constrained triangulation. Double
  precision, on the unconditioned source.
- **One list.** `registered_features.constrained` writes guide edges, then
  crease edges, with a mode each, for the engine flag `-constrained-edges`.
  Guides are native mode 2 (direction, lattice line, preserved edge).
- **Check.** `guide_rows.py`: one connected path per guide that never turns
  onto another loop, with the crease-row limits. One turn is excused at each
  corner of the guide itself (45° or more from one face to the next).
- **Default.** This is the route for every open part with creases or guides.
  The worker matrix is 8 of 8, with island 2 and island 7 byte-identical.

What is still open here:

- **Creases are not registered like guides.** They are engine mode 3
  (direction and preserved edge, no lattice line) plus the old 0.75 h
  orientation band. Native has one treatment for both. The choice rests on one
  64-seed search per alternative at 750 + guide; see the section.
- **The engine does not guarantee the loop.** Layouts are screened and seeds
  searched (64). On flat controls a registered loop leaves its guide up to two
  faces before a free end. A guide whose ends matter may be rejected.
- **Source conditioning.** Native cuts its densified source. Here a guide
  crossing a large flat triangle is cut as a straight chord (0.14 h from the
  drawn samples on the test case). The fit uses the drawn curve.
- **Closed parts** keep the old guide path and check (`curved_quad`,
  `feature_quad`). The four-guide toilet has not been measured with
  `guide_rows`.
- **Strength below 100** (native modes 0 and 1) is not implemented.
- **Not run:** guides that cross creases or each other, closed guides on open
  parts, more than one guide. The cut handles crossings (tests), the engine
  and the search were not exercised on them.

### 4.1 The island 6 rim was jagged but accepted (fixed for open parts, 2026-11-09)

User-visible symptom: screenshot job `3029972da0174acd9845b6ec0df6e3ea`
(island 6, target 200, 188 quads). The pink crease rim zig-zags.

**Status.** Island 6 at 200 now returns a continuous rim row (207 quads on
2026-11-09, 220 since the 2026-11-10 engine), and the crease check rejects the
screenshot mesh. Full account, limits and
evidence: `GUIDED_LAYOUT.md` → "Crease rows". In short:

- **Cause found in the layout, not only the check.** QuadriFlow's `-sharp`
  hardens edges above a fixed 60° dihedral. The upper rim crease is 33° to 54°,
  so the engine never treated it as a feature; only its sharper partner a
  quarter face below got rows.
- **Check.** `crease_rows.py` picks one representative crease per band of
  parallel creases (the one bordering the wider sheet) and requires one
  connected, forward-ordered output edge path for each representative chain of
  two faces or more. Distance is measured from the path to the band, without
  the scalar band allowance. Limits reuse existing numbers: 0.25 h at the 95th
  percentile, 0.5 h maximum, 1 h in the last face of an open end, 30° direction.
- **Generator.** The representative chains go to the engine as preserved
  constrained edges (since 2026-11-10 through `-constrained-edges`, mode 3;
  before that as embedded guide edges); the fit holds each row on its crease
  and fits its band through that row only. Layouts are screened before fitting
  and seeds are tried in order.
- **Witness edge [1308, 1309]:** 0.422 h before, 0.004 h after, 0.011 h native.

What is still open here:

- **Closed parts are not enforced.** `feature_quad.py` has no row fitting, so
  its crease check records rows without failing on them. Island 7's current
  339-quad output would fail one of five chains (source vertices 159 to 380).
  Port the row fitting there, then drop `enforce_rows=False`.
- **Seed search.** With the 2026-11-10 engine island 6 is accepted at seed 2
  (second pass) at 150, seed 28 at 200, seed 21 at 300, seed 52 at 200 + guide
  and seed 6 (second pass) at 750 + guide; 64 seeds are tried. Which seed wins
  changes with small input changes. The hinge lugs, about one face tall, use
  most of the 5 % budgets of the older checks, so few seeds pass. A layout
  that handles the lugs would make this robust.
- **Soft-guide encoding: resolved.** The 1e-6 lift is gone. Hardness comes
  from the engine's constrained-edge list; soft creases are mode-1 entries.
- **Self-approaching chains.** The row finder assumes a chain does not pass
  within a face of itself. Island 4's outline at 300 is one 94 h chain with a
  hairpin and never gets a path. Splitting chains at corners of 30° or more
  would address it and would not change island 6 (its chains have none).
- **Island 4 at 300 never returns**, before or after this work: an endless loop
  in the unchanged post-processing of its first size-caps layout
  (`open_surface.construct`, between reading the layout and the fit). Separate
  defect; found while checking other open parts for collateral damage. That
  check found no part that used to generate and now fails (table at the end of
  `GUIDED_LAYOUT.md` → "Crease rows").
- **The parameter chart and combined solve below were not built.** The rim did
  not need them. They remain the route to native-style two-row rims.

What the investigation of 2026-10-28 established (unchanged):

- The rim is **not protected by any hard check**. None of the 283 pink crease
  edges, and none of their vertices, lies on the true open boundary. That
  boundary is an inner loop under the folded lip, and it passes (max 0.062 h,
  limit 0.1 h). The visible outer fold is covered only by the crease and
  whole-surface checks.
- **Why the jagged rim passes:** at witness source edge [1308, 1309] the nearest
  output edge is 0.422 h away. The crease check subtracts a band allowance
  around each crease, which brings the 95th-percentile error from 0.328 h down
  to 0.199 h (limit 0.25 h). The check accepts nearby unrelated edges; it never
  requires a connected row along the rim.
- **Native ZBrush reference** (exact source, keep creases, 30°, request 200):
  374 faces (364 quads, 10 triangles). Its rim error at the same witness is
  0.011 h, and the left rim has an ordered edge row. This is evidence of what
  good looks like at about twice the budget. It is not proof that 200 quads
  can be reached.
- **Native integer-solve corrections** (in the `recovered_*` scripts, from
  `0x28fe70` and mode 2 elimination `0x288f50`):
  - Mixed guide/seed separation candidates were wrongly rejected when the
    gap was 4.5 or more.
  - Soft gaps of at least 1.35 now keep their target instead of being clamped
    to 1.
  - Constant-only rows are skipped without using up a pivot.
  The new test reproduces ZBrush's captured integer step exactly for this part
  (129 residuals, 160 constraints, 125 dependencies, 21 nested variables,
  71 outer fixes). The test starts from captured upstream data, so it does not
  rebuild the whole remesher. 19 optional candidates are legitimately left
  unsatisfied. Locking every candidate independently is **not** the native
  method.
- **QuadriFlow lock experiment (not promoted):** it fixed two engine bugs.
  Flip contraction removed locked separation edges, and `FixValence` cycled on
  non-reciprocal adjacency (three faces sharing edge [104, 105]). Engine
  `9343e8a5…` runs fast, but every rim-locking run still rejects because of
  path-ownership merges and broken rows. It also fails a control that the
  frozen v3 engine passes. Material is in `runs/native-rim-investigation/qf-locks/`.

**Milestone not taken:** an app-owned parameter chart plus a combined solve that
keeps the rim identities as continuous rows through extraction. Concretely:
1. Export the app's continuous field just before `ComputeIndexMap`.
2. Build a cut/fan parameter chart, guide scalar groups, singular seeds and
   seam periods.
3. Feed the tested native integer callback from those instead of from
   captures.

Two pitfalls:
- QuadriFlow's `mO` holds local 3D lattice origins, not consistent UVs, so
  projecting `(V - O)` does not give a chart.
- The recovered closed-surface wrappers reject open edge-angle/seed cases, some
  branching guide groups, and the candidate sentinel case. These producers need
  qualified open-part versions.

The ordered, connected row this section used to ask for is now in the check
(see Status above).

### 4.2 Island 6 at 150 quads with the native 30° crease angle

Accepted since 2026-11-10: 143 quads (seed 2, second pass), every existing
limit unchanged. Before that it was rejected at every attempt. It passes on
one seed of 64, so treat it as fragile, not solved.

### 4.3 Island 6 at 150 with a guide; island 5

Island 6 at 150 with a guide has not been run on the new route. Island 5 is
unsolved. Island 5 is closed and failed before any of the low-count
work. Islands 2, 7 and 10 pass (291, 339 and 545 quads). Island 2 has no
admitted creases and island 7 takes the closed-part route, so both outputs are
byte-identical to before; island 10 now carries six crease rows.

### 4.4 Native stages not yet ported

Listed largest expected effect first:
1. Five-radius valid-window selection by direction consistency.
2. The coupled least-squares sizing objective.
3. Source conditioning to the ≥ 3000-triangle budget before the field.
4. Guide embedding with integer registration: done for open parts on
   2026-11-10 (section 4.0), with an independent engine. The native integer
   system itself (parameter chart, combined solve) is still not built.
5. The attachment surface walk.

### 4.5 Policy decisions waiting on the user

Ask about these; do not decide them silently:
- **Count band ±15 %.** Native island 6 with creases kept lands +17 % to +35 %.
- **Quad-only output.** Native emits some triangles at low counts.
- **Surface 0.5 h and boundary 0.1 h at ≤ 300 faces.** These alone fail the
  caps layouts at 150.
- **Shape checks.**

## 5. Verification for any solver change

- Unit tests (section 3).
- For the extra-faces option: `tests/verify_registered_features.py --extra-faces
  --case island6-200-guide` (expect 436 quads, SHA-256 `af8c5381…8015`), the
  same with `--case island6-150 --case island6-200 --case island6-300`
  (421 / 466 / 655) and `--case island6-750-guide` (1,848, from the second
  base-size step), and `tests/verify_registered_features_ui.py --case
  island6-200-guide --extra-faces on`. `tests/render_corner_case.py` draws the
  corners of several meshes side by side and writes the corner-zone numbers.
  `tests/extra-faces/corners-1/strict-search.py` runs the strict search with
  the corner check enforced.
- `tests/verify_registered_features.py` runs island 6 at 150/200/300,
  200 + the guide of job `483afe83` (`tests/fixtures/island6-guide-483afe83.json`),
  750 + the authored guide (`tests/fixtures/island6-authored-guide.json`),
  island 2 at 300, island 7 at 300 and island 10 at 500, from the part sources
  in `runs/parts/`.
- `tests/verify_registered_features_ui.py` drives the real UI. The user expects
  verification there too.
- Re-measure the screenshot rim witness for any rim work. Record the job ids you
  create so they can be cleaned up safely.
- `tests/test_crease_rows.py` holds the rim regression: the screenshot mesh
  must fail on its rim row and the native mesh must pass. Keep both.
- `tests/test_guide_rows.py` holds the guide regression: the zig-zag mesh of
  job `483afe83` must fail on its turns, the native strength-100 mesh must
  pass, and the packaged engine must put a loop on a registered guide. Keep
  all three.
- `tests/render_guide_case.py` draws meshes side by side with a guide and
  writes the guide, rim and witness numbers beside the picture.
- The matrix compares code hashes before and after its run. Do not edit a root
  `.py` file while it runs, or it reports `codeStable False` and exits 1.
- Expected matrix result: 9 of 9 (run `75437044fa95`; `island6-1500` is new and
  island 10 returns 442 quads since 2026-11-13). Before that: 8 of 8 (run `2bdcf1f3e24d`, the same bytes as run
  `8a240b30812b`). Each strict island 6 result reports its corner zones as over
  the limits; that is expected and is not a failure. A run takes about 10
  minutes. Read the `RESULT` lines; times vary with machine load, bytes do
  not.

## 6. Where the evidence lives

| What | Where |
|---|---|
| Algorithm, runtime, rim investigation | `GUIDED_LAYOUT.md` |
| Errors-and-omissions audit against native rules (§8 = size caps) | `ghidra-workbench/work/retopo-lowcount/AUDIT.md` |
| Island 6 low-count study, native measurements ("Fourth round") | `ghidra-workbench/work/retopo-lowcount/FINDINGS.md` |
| Recovered native rules | `ghidra-workbench/targets/zbrush/understanding/**` |
| Recovered arithmetic (Python) | `engine/targets/zbrush/experiments/python/recovered_*.py` |
| Engine builds, compiler records | `ghidra-workbench/work/retopo-guided-layout/` (`build.py`, `build-records/`) |
| Rim measurements and provenance | `engine/guided-quadriflow/development/native-rim-verification.json` |
| Crease-row check and generator | `crease_rows.py`, `open_surface.py` (`row_plan`), `GUIDED_LAYOUT.md` → "Crease rows" |
| Crease-row results, job ids, hashes | `engine/guided-quadriflow/development/crease-rows-verification.json` |
| Local faces, corner zones, extra-faces generator | `crease_rows.py` (`local_sizes`), `corner_zones.py`, `open_surface.py`, `GUIDED_LAYOUT.md` → "Corner rows and corner zones with extra faces" |
| Corner results, job ids, hashes, engine parity | `engine/guided-quadriflow/development/corner-rows-verification.json` |
| Corner matrices, UI evidence, pictures, strict search, engine patch and packaging scripts | `tests/extra-faces/corners-1/` |
| Corner regression fixtures | `tests/fixtures/corner_zones/README.md`, `tests/fixtures/quad_connectivity/README.md` |
| Guide cut, constrained-edge list, guide check | `native_guide_cut.py`, `registered_features.py` (`constrained`), `guide_rows.py`, `GUIDED_LAYOUT.md` → "Guides cut into the source" |
| Guide results, job ids, hashes, engine parity | `engine/guided-quadriflow/development/guide-cut-verification.json` |
| Guide matrix, UI evidence, pictures, engine patch scripts (git-ignored) | `tests/registered-features/guide-native-1/` |
| Native ZBrush run with a guide (strength 100) | `runs/native-rim-investigation/native-captures/guide/`, scripts `run_native_island6_guide.py`, `island6_guide_payload.py` |
| Guide regression fixtures | `tests/fixtures/guide_rows/README.md` |
| Crease-row matrix and UI evidence (git-ignored) | `tests/registered-features/rimfix-rows-3/`, `tests/registered-features/rimfix-ui-200b/` |
| Rim regression fixtures | `tests/fixtures/crease_rows/README.md` |
| Native captures, tracers, ZBrush runner | `runs/native-rim-investigation/native-captures/` (input `inputs/island6-original.obj`) |
| QuadriFlow lock experiment | `runs/native-rim-investigation/qf-locks/` (`fan-fix/`, `fan-fix-clean/`) |
| Integer callback fixtures | `tests/fixtures/native_integer/README.md` |
| Parts workflow, older handoffs | `PARTS_WORKFLOW.md`, `REVIEW_HANDOFF.md`, `TOILET_SOLVER.md` |

## 7. Gotchas

- `ghidra-workbench/work/retopo-lowcount/run_native_island6.py` still points at
  the deleted `runs/60e34fcd…/source.obj`. Use the copy under
  `runs/native-rim-investigation/native-captures/scripts/` with
  `inputs/island6-original.obj`, or load the part with `mesh_parts.load_part`.
  Never point scripts at a run folder.
- Native ZBrush runs must use fresh, owned batch processes. Do not touch a
  `ZBrush.exe` that the user is running.
- When a heredoc patch through `python - <<'EOF'` writes C `printf("...\n")`,
  the backslash is lost. Use raw strings or `chr(92)+'n'`. In this shell a
  doubled backslash inside any quoted heredoc collapses to one, so Python
  text with `'\\n'` in it arrives broken. Write such scripts to a file with
  the editor tool and run the file.
- The engine sources in the workbench are Latin-1 with CRLF line ends
  (`loader.cpp`). Patch them as bytes.
- Rows layouts no longer use `-embedded-guides`. The engine reads
  `open-surface/constrained/constrained-edges.txt` (`a b mode`, input-file
  vertex ids) and, for creases, the band file `open-surface/crease-band.txt`.
  Modes: 1 direction, 2 direction + lattice line + preserved (guides),
  3 direction + preserved (creases), 4 preserved only (unused).
- A constrained-edge row may carry a fourth number, the largest face size at
  that edge as a fraction of the requested size. The engine uses it only with
  `-size-caps`. The application writes it only when extra faces are allowed.
- With extra faces allowed `open_surface.construct` lays out all 64 seeds
  first (about 8 s at 200, 30 s at 750) and tries them fewest faces first.
  At the strict count, and in the steps with smaller base faces, the seeds are
  laid out a batch at a time in order.
- `open_surface.construct(workers=N)` processes rows layouts in N other
  processes; the default is 1 and `worker.py` passes 3 (`RETOPO_ROW_WORKERS`
  overrides). A script that calls `construct` itself with more than one
  worker needs an `if __name__ == '__main__':` guard, and anything it patches
  in `open_surface` or its checks does not reach the other processes: use one
  worker for experiments that change a check (`strict-search.py` does).
- `worker.py` sets `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS` and
  `MKL_NUM_THREADS` to 1 unless they are already set. Without that the low
  bits of a result differ from the verified ones (the user's UI job
  `cfaf2c05…` and the matrix differ by a few 1e-4 h for this reason).
- A rows layout whose `-f` differs from the target is a smaller-base step, not
  a layout to coarsen. Its folders are `open-surface/constrained-<faces>/` and
  `row-layouts-<faces>/`; the last resort uses `constrained-requested/` and
  `row-layouts-requested/`.
- The UI's "Add faces where the shape needs them" box is checked by default
  for open parts. `tests/verify_registered_features_ui.py` leaves it as the
  page shows it unless `--extra-faces on|off` is given, so pass `off` when a
  strict-count result is expected.
- The guide check excuses one turn at each corner of the guide. A drawn
  stroke is stair-stepped at sub-face scale; corners are measured with
  one-face chords so those steps do not count.
- `tests/verify_registered_features_ui.py` can fail before Generate with
  `net::ERR_NETWORK_CHANGED` when the host's network changes. Run it again.
- Line ends are part of the tracked bytes here (`-text`): some files are LF,
  some CRLF. Python's `read_text`/`write_text` rewrites LF as CRLF on this
  machine. Edit as bytes, and check `git ls-files --eol -m` before a long
  verification, or the recorded code hashes will not match the tree.
- Do not modify sealed workbench records or Ghidra databases.
- `open_surface.construct` tries 2 caps layouts (`-size-caps-exact`, with the
  request corrected up to twice from actual counts), then 3 constrained,
  4 adaptive and 3 coarsened. `weld_pinched_quads` and `fill_triangle_holes`
  repair engine extraction artifacts before the fit. When a part has creases
  that need rows, two passes over 32 seeds of rows layouts come first
  (`ROW_STYLES`), and every layout is screened for row paths before fitting.
- Rows layouts are deterministic: the engine always runs with four threads and
  the fit with one, and eight seeds laid out together give the same files as
  one at a time (checked by output hash).
- The row check accepts a row anywhere across its band. If a result's rim row
  sits on the lower rim crease, the check is working as written; the generator
  aims at the representative (upper) crease.
